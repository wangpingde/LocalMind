"""v0.2 功能单元测试."""

from app.core.rag.parser import DocParser
from app.security.permission_checker import PermissionChecker


class _Audit:
    def log_permission_denied(self, **kwargs):
        pass


class _Workspace:
    root = __import__("pathlib").Path("/tmp/localmind-test")


class _Settings:
    skill_network_enabled = False
    shell_tool_enabled = False
    local_only_mode = True


class _Skill:
    def __init__(self, permissions: dict):
        self.id = "test"
        self.name = "Test"
        self.permissions = permissions


def test_parser_supported_formats_include_v02() -> None:
    for ext in (".csv", ".xlsx", ".pptx", ".html", ".json", ".py"):
        assert ext in DocParser.SUPPORTED


def test_permission_checker_blocks_network() -> None:
    checker = PermissionChecker(_Workspace(), _Audit())  # type: ignore[arg-type]
    skill = _Skill({"network": {"enabled": True}})
    assert checker.is_skill_allowed(skill, _Settings(), write_audit=False) is False


def test_permission_checker_allows_prompt_only() -> None:
    checker = PermissionChecker(_Workspace(), _Audit())  # type: ignore[arg-type]
    skill = _Skill({})
    assert checker.is_skill_allowed(skill, _Settings(), write_audit=False) is True
