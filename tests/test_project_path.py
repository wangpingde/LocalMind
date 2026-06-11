"""项目路径匹配测试."""

from app.core.project.project_manager import ProjectManager


def test_path_in_scope_relative() -> None:
    assert ProjectManager.path_in_scope(
        "projects/localmind/readme.md", "projects/localmind"
    )
    assert not ProjectManager.path_in_scope(
        "projects/other/readme.md", "projects/localmind"
    )
    assert not ProjectManager.path_in_scope("inbox/notes.txt", "projects/localmind")


def test_path_in_scope_absolute_legacy() -> None:
    doc = "D:/data/knowledge/projects/demo/a.pdf".replace("/", "\\")
    assert ProjectManager.path_in_scope(doc, "projects/demo")
