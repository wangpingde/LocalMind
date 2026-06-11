"""LocalMind 酷黑主题."""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

# ── 色板 ──────────────────────────────────────────
BG_VOID = "#030305"
BG_DEEP = "#08080c"
BG_MAIN = "#0e0e14"
BG_CARD = "#14141c"
BG_ELEVATED = "#1a1a24"
BG_INPUT = "#0a0a10"
BG_HOVER = "#22222e"

BORDER = "#1e1e2a"
BORDER_LIGHT = "#2a2a38"

TEXT_PRIMARY = "#ececf4"
TEXT_SECONDARY = "#8888a0"
TEXT_MUTED = "#505060"

ACCENT = "#00e5ff"
ACCENT_HOVER = "#33ecff"
ACCENT_DIM = "#0099b3"
ACCENT_GLOW = "rgba(0, 229, 255, 0.12)"

USER_MSG = "#6ec8ff"
AGENT_MSG = "#c8c8d8"
REASONING_MSG = "#a89fd8"
DANGER = "#ff3d6a"


def get_stylesheet() -> str:
    return f"""
/* ── 全局 ── */
QMainWindow, QWidget {{
    background-color: {BG_MAIN};
    color: {TEXT_PRIMARY};
    font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
    font-size: 13px;
}}

/* ── 侧栏 ── */
#sidebar {{
    background-color: {BG_DEEP};
    border-right: 1px solid {BORDER};
}}

#brandTitle {{
    font-size: 17px;
    font-weight: 700;
    color: {TEXT_PRIMARY};
    letter-spacing: 1px;
}}

#brandSubtitle {{
    font-size: 11px;
    color: {TEXT_MUTED};
    letter-spacing: 2px;
}}

#sectionLabel {{
    font-size: 10px;
    font-weight: 600;
    color: {TEXT_MUTED};
    letter-spacing: 1.5px;
    padding: 4px 8px;
}}

/* ── 导航列表 ── */
#navList {{
    background-color: transparent;
    border: none;
    outline: none;
    padding: 4px;
}}

#navList::item {{
    color: {TEXT_SECONDARY};
    padding: 10px 14px;
    border-radius: 8px;
    margin: 2px 4px;
    border-left: 3px solid transparent;
}}

#navList::item:hover {{
    background-color: {BG_HOVER};
    color: {TEXT_PRIMARY};
}}

#navList::item:selected {{
    background-color: {ACCENT_GLOW};
    color: {ACCENT};
    border-left: 3px solid {ACCENT};
    font-weight: 600;
}}

#historyList {{
    background-color: transparent;
    border: none;
    outline: none;
    padding: 4px;
}}

#historyList::item {{
    color: {TEXT_MUTED};
    padding: 8px 12px;
    border-radius: 6px;
    margin: 1px 4px;
    font-size: 12px;
}}

#historyList::item:hover {{
    background-color: {BG_HOVER};
    color: {TEXT_SECONDARY};
}}

#historyList::item:selected {{
    background-color: {BG_ELEVATED};
    color: {TEXT_PRIMARY};
}}

/* ── 侧栏分隔拖拽条 ── */
QSplitter::handle:horizontal {{
    background-color: {BORDER};
    width: 6px;
}}

QSplitter::handle:horizontal:hover {{
    background-color: {ACCENT_DIM};
}}

/* ── 面板标题 ── */
#panelTitle {{
    font-size: 15px;
    font-weight: 700;
    color: {TEXT_PRIMARY};
    letter-spacing: 0.5px;
}}

#panelSubtitle {{
    font-size: 11px;
    color: {TEXT_MUTED};
}}

/* ── 分组框 ── */
QGroupBox {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
    margin-top: 14px;
    padding: 16px 12px 12px 12px;
    font-weight: 600;
    color: {TEXT_SECONDARY};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 8px;
    color: {ACCENT_DIM};
    font-size: 11px;
    letter-spacing: 1px;
}}

/* ── 输入控件 ── */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {{
    background-color: {BG_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 12px;
    selection-background-color: {ACCENT_DIM};
    selection-color: {BG_VOID};
}}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border: 1px solid {ACCENT_DIM};
}}

QLineEdit:hover, QTextEdit:hover {{
    border: 1px solid {BORDER_LIGHT};
}}

/* ── 设置页 ── */
#settingsScroll {{
    background: transparent;
    border: none;
}}

#settingsFormLabel {{
    color: {TEXT_SECONDARY};
    font-size: 13px;
    padding-right: 4px;
}}

QLineEdit#settingsField,
QComboBox#settingsField {{
    background-color: {BG_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 0 14px;
    font-size: 13px;
}}

QLineEdit#settingsField:focus,
QComboBox#settingsField:focus {{
    border: 1px solid {ACCENT_DIM};
}}

QLineEdit#settingsField:hover,
QComboBox#settingsField:hover {{
    border: 1px solid {BORDER_LIGHT};
}}

QComboBox#settingsField::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 32px;
    border: none;
}}

QComboBox#settingsField::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {TEXT_SECONDARY};
    margin-right: 6px;
}}

QComboBox#settingsField QAbstractItemView {{
    background-color: {BG_ELEVATED};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_LIGHT};
    selection-background-color: {ACCENT_GLOW};
    selection-color: {ACCENT};
    outline: none;
    padding: 4px;
}}

#settingsCheckBox {{
    color: {TEXT_PRIMARY};
    font-size: 13px;
    spacing: 8px;
    padding: 4px 0;
}}

#settingsCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid {BORDER_LIGHT};
    background: {BG_INPUT};
}}

#settingsCheckBox::indicator:checked {{
    background: {ACCENT_DIM};
    border: 1px solid {ACCENT};
}}

#chatInput {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER_LIGHT};
    border-radius: 12px;
    padding: 12px 16px;
    font-size: 14px;
}}

#chatInput:focus {{
    border: 1px solid {ACCENT};
}}

#chatMessages {{
    background-color: {BG_DEEP};
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 16px 20px;
}}

#chatMessages .chat-content p {{
    margin: 6px 0;
}}

#chatMessages .chat-content ul,
#chatMessages .chat-content ol {{
    margin: 8px 0 8px 20px;
    padding: 0;
}}

#chatMessages .chat-content li {{
    margin: 4px 0;
}}

#contextView {{
    background-color: {BG_DEEP};
    border: none;
    border-radius: 6px;
    padding: 10px;
    font-size: 12px;
    color: {TEXT_SECONDARY};
}}

/* ── 下拉框 ── */
QComboBox {{
    background-color: {BG_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px 12px;
    min-width: 100px;
}}

QComboBox:hover {{
    border: 1px solid {BORDER_LIGHT};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {TEXT_SECONDARY};
    margin-right: 8px;
}}

QComboBox QAbstractItemView {{
    background-color: {BG_ELEVATED};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_LIGHT};
    selection-background-color: {ACCENT_GLOW};
    selection-color: {ACCENT};
    outline: none;
}}

/* ── 按钮 ── */
QPushButton {{
    background-color: {BG_ELEVATED};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_LIGHT};
    border-radius: 8px;
    padding: 8px 18px;
    font-weight: 500;
}}

QPushButton:hover {{
    background-color: {BG_HOVER};
    border: 1px solid {TEXT_MUTED};
}}

QPushButton:pressed {{
    background-color: {BG_CARD};
}}

QPushButton:disabled {{
    background-color: {BG_CARD};
    color: {TEXT_MUTED};
    border: 1px solid {BORDER};
}}

#primaryButton {{
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {ACCENT_DIM}, stop:1 #0066aa);
    color: {BG_VOID};
    border: none;
    font-weight: 700;
    padding: 9px 24px;
}}

#primaryButton:hover {{
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {ACCENT}, stop:1 {ACCENT_DIM});
    color: {BG_VOID};
}}

#primaryButton:pressed {{
    background-color: {ACCENT_DIM};
}}

#ghostButton {{
    background-color: transparent;
    color: {TEXT_SECONDARY};
    border: 1px solid {BORDER};
}}

#ghostButton:hover {{
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_LIGHT};
    background-color: {BG_HOVER};
}}

/* ── 标签页 ── */
QTabWidget::pane {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    top: -1px;
}}

QTabBar::tab {{
    background-color: transparent;
    color: {TEXT_MUTED};
    padding: 8px 16px;
    border: none;
    border-bottom: 2px solid transparent;
    font-size: 12px;
}}

QTabBar::tab:hover {{
    color: {TEXT_SECONDARY};
}}

QTabBar::tab:selected {{
    color: {ACCENT};
    border-bottom: 2px solid {ACCENT};
    font-weight: 600;
}}

/* ── 表格 ── */
QTableWidget {{
    background-color: {BG_DEEP};
    alternate-background-color: {BG_CARD};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 8px;
    gridline-color: {BORDER};
    selection-background-color: {ACCENT_GLOW};
    selection-color: {ACCENT};
}}

QTableWidget::item {{
    padding: 6px 8px;
    border: none;
}}

QHeaderView::section {{
    background-color: {BG_ELEVATED};
    color: {TEXT_MUTED};
    border: none;
    border-bottom: 1px solid {BORDER_LIGHT};
    border-right: 1px solid {BORDER};
    padding: 8px 10px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
}}

/* ── 复选框 ── */
QCheckBox {{
    color: {TEXT_SECONDARY};
    spacing: 8px;
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid {BORDER_LIGHT};
    background-color: {BG_INPUT};
}}

QCheckBox::indicator:checked {{
    background-color: {ACCENT_DIM};
    border: 1px solid {ACCENT};
}}

QCheckBox:hover {{
    color: {TEXT_PRIMARY};
}}

/* ── 分割条 ── */
QSplitter::handle {{
    background-color: {BORDER};
    width: 1px;
}}

QSplitter::handle:hover {{
    background-color: {ACCENT_DIM};
}}

/* ── 滚动条 ── */
QScrollBar:vertical {{
    background: {BG_DEEP};
    width: 8px;
    margin: 0;
    border: none;
}}

QScrollBar::handle:vertical {{
    background: {BORDER_LIGHT};
    border-radius: 4px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background: {TEXT_MUTED};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background: {BG_DEEP};
    height: 8px;
}}

QScrollBar::handle:horizontal {{
    background: {BORDER_LIGHT};
    border-radius: 4px;
    min-width: 30px;
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ── 标签 ── */
QLabel {{
    color: {TEXT_PRIMARY};
    background: transparent;
}}

#fieldLabel {{
    color: {TEXT_SECONDARY};
    font-size: 12px;
}}

#statsLabel {{
    color: {TEXT_SECONDARY};
    font-size: 12px;
    padding: 8px;
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}

/* ── 工具提示 ── */
QToolTip {{
    background-color: {BG_ELEVATED};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_LIGHT};
    padding: 6px 10px;
    border-radius: 6px;
}}

/* ── 消息框 ── */
QMessageBox {{
    background-color: {BG_MAIN};
}}

QMessageBox QLabel {{
    color: {TEXT_PRIMARY};
}}

QMessageBox QPushButton {{
    min-width: 80px;
}}
"""


def apply_theme(app: QApplication) -> None:
    """应用酷黑主题到整个应用."""
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(BG_MAIN))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Base, QColor(BG_INPUT))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(BG_CARD))
    palette.setColor(QPalette.ColorRole.Text, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Button, QColor(BG_ELEVATED))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT_DIM))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(BG_VOID))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(BG_ELEVATED))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(TEXT_PRIMARY))
    app.setPalette(palette)

    font = QFont("Segoe UI", 10)
    font.setStyleHint(QFont.StyleHint.SansSerif)
    app.setFont(font)

    app.setStyleSheet(get_stylesheet())
