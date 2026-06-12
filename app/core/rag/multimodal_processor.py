"""多模态媒体描述处理器."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from loguru import logger

from app.core.llm.model_gateway import ModelGateway
from app.core.rag.media_extractor import MediaAsset
from app.core.rag.media_refs import format_media_tags
from app.core.rag.media_store import MediaStore
from app.security.audit_logger import AuditLogger


class MultimodalProcessor:
    def __init__(
        self,
        model_gateway: ModelGateway,
        audit: AuditLogger,
        *,
        knowledge_dir,
        max_images: int = 30,
        concurrency: int = 3,
    ) -> None:
        self.model_gateway = model_gateway
        self.audit = audit
        self.knowledge_dir = Path(knowledge_dir)
        self.media_store = MediaStore(self.knowledge_dir)
        self.max_images = max_images
        self.concurrency = concurrency

    def describe_all(
        self,
        assets: list[MediaAsset],
        *,
        document_id: str = "",
        document_path: str = "",
    ) -> list[dict[str, Any]]:
        """将 MediaAsset 转为可索引的 sections（含 media_ref 供回答展示图片）."""
        if not assets:
            return []

        settings = self.model_gateway.config.load_settings()
        if not settings.multimodal_index_enabled:
            return self._image_only_sections(assets, document_id, document_path)

        if self.model_gateway.vision_explicitly_disabled():
            logger.info("视觉能力已显式关闭，仅保存图片引用: {}", document_path)
            self.audit.log(
                "multimodal_skipped",
                {"path": document_path, "reason": "vision_disabled", "assets": len(assets)},
            )
            return self._image_only_sections(assets, document_id, document_path)

        can_vision = self.model_gateway.supports_vision()
        if not can_vision:
            logger.warning(
                "当前对话模型可能不支持视觉，仍将尝试多模态描述: {}（可在设置中填写 vision_model）",
                document_path,
            )

        started = time.monotonic()
        sections: list[dict[str, Any]] = []
        seen_hashes: set[str] = set()
        image_items: list[MediaAsset] = []
        failures = 0

        for asset in assets:
            if asset.kind == "video_frame" and not asset.data:
                sec = self._metadata_section(asset, document_id, document_path)
                if sec:
                    sections.append(sec)
                continue
            if asset.kind == "image" and not asset.data:
                sec = self._metadata_section(asset, document_id, document_path)
                if sec:
                    sections.append(sec)
                continue
            dedup_key = asset.dedup_key
            if dedup_key in seen_hashes:
                continue
            seen_hashes.add(dedup_key)
            if len(image_items) >= self.max_images:
                logger.info("已达单文档图片上限 {}: {}", self.max_images, document_path)
                break
            image_items.append(asset)

        if image_items:
            batch_input = [
                (asset.data, asset.mime, asset.context_hint) for asset in image_items
            ]
            descriptions = self.model_gateway.describe_images_batch(
                batch_input, concurrency=self.concurrency
            )

            for asset, description in zip(image_items, descriptions, strict=True):
                media_ref = self._persist_media_ref(document_id, document_path, asset)
                if description.strip():
                    prefix = "[视频画面]" if asset.kind == "video_frame" else "[图片描述]"
                    content = f"{prefix} {asset.heading_path}\n\n{description.strip()}"
                    kind = "video" if asset.kind == "video_frame" else "image"
                    sections.append(
                        self._make_section(
                            content=content,
                            asset=asset,
                            media_ref=media_ref,
                            kind=kind,
                        )
                    )
                else:
                    failures += 1
                    logger.warning("媒体描述为空: {} {}", document_path, asset.heading_path)
                    sections.append(
                        self._failed_section(asset, media_ref=media_ref)
                    )

        elapsed = time.monotonic() - started
        self.audit.log(
            "multimodal_indexed",
            {
                "path": document_path,
                "assets": len(assets),
                "described": sum(
                    1
                    for s in sections
                    if s.get("media_ref") and "[图片处理失败]" not in s.get("content", "")
                ),
                "failures": failures,
                "elapsed_sec": round(elapsed, 2),
            },
        )
        logger.info(
            "多模态索引 {}: {} 张媒体, {} 段, {} 失败",
            document_path,
            len(image_items),
            len(sections),
            failures,
        )
        return sections

    def _persist_media_ref(
        self, document_id: str, document_path: str, asset: MediaAsset
    ) -> str | None:
        if (
            document_path
            and asset.source_path.replace("\\", "/") == document_path.replace("\\", "/")
            and self.media_store.is_standalone_image_doc(document_path)
        ):
            return document_path.replace("\\", "/")
        if not asset.data or not document_id:
            return None
        try:
            return self.media_store.save_image(document_id, asset.data, asset.mime)
        except Exception as e:
            logger.warning("保存提取图片失败 {}: {}", document_path, e)
            return None

    def _make_section(
        self,
        *,
        content: str,
        asset: MediaAsset,
        media_ref: str | None,
        kind: str,
    ) -> dict[str, Any]:
        tags = format_media_tags(kind, media_ref) if media_ref else f"media:{kind}"
        return {
            "content": content,
            "page_no": asset.page_no,
            "heading_path": asset.heading_path,
            "tags": tags,
            "media_ref": media_ref,
        }

    def _image_only_sections(
        self,
        assets: list[MediaAsset],
        document_id: str,
        document_path: str,
    ) -> list[dict[str, Any]]:
        sections: list[dict[str, Any]] = []
        for asset in assets:
            if asset.kind != "image" or not asset.data:
                continue
            media_ref = self._persist_media_ref(document_id, document_path, asset)
            if not media_ref:
                continue
            sections.append(
                {
                    "content": f"[图片] {asset.heading_path}\n（已提取图片，视觉描述未启用）",
                    "page_no": asset.page_no,
                    "heading_path": asset.heading_path,
                    "tags": format_media_tags("image", media_ref),
                    "media_ref": media_ref,
                }
            )
        return sections

    def _metadata_section(
        self, asset: MediaAsset, document_id: str, document_path: str
    ) -> dict[str, Any] | None:
        hint = asset.context_hint or asset.heading_path
        media_ref = None
        if asset.data and document_id:
            media_ref = self._persist_media_ref(document_id, document_path, asset)
        return {
            "content": f"[媒体元数据] {hint}",
            "page_no": asset.page_no,
            "heading_path": asset.heading_path,
            "tags": format_media_tags("metadata", media_ref or ""),
            "media_ref": media_ref,
        } if hint else None

    def _failed_section(
        self, asset: MediaAsset, *, media_ref: str | None = None
    ) -> dict[str, Any]:
        hint = asset.context_hint or asset.heading_path
        tags = format_media_tags("failed", media_ref) if media_ref else "media:failed"
        return {
            "content": (
                f"[图片处理失败] {asset.heading_path}\n"
                f"文件: {hint}\n"
                "视觉模型未返回描述；图片已保存，回答时仍可展示配图。"
            ),
            "page_no": asset.page_no,
            "heading_path": asset.heading_path,
            "tags": tags,
            "media_ref": media_ref,
        }

    def _metadata_only_sections(self, assets: list[MediaAsset]) -> list[dict[str, Any]]:
        return [
            s
            for a in assets
            if (s := self._metadata_section(a, "", ""))
        ]
