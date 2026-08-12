from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication

DARK_PALETTE = {
    "window_bg": "#18181b",
    "panel_bg": "#1c1d20",
    "card_bg": "#232428",
    "input_bg": "#28292d",
    "input_hover": "#2f3035",
    "border": "#34353a",
    "text_primary": "#f2f2f3",
    "text_secondary": "#9a9ba3",
    "text_label": "#8b8c94",
    "track_off": "#3a3b40",
}

LIGHT_PALETTE = {
    "window_bg": "#f5f5f7",
    "panel_bg": "#ffffff",
    "card_bg": "#f0f0f2",
    "input_bg": "#ffffff",
    "input_hover": "#ececee",
    "border": "#d8d8dc",
    "text_primary": "#1a1a1c",
    "text_secondary": "#6b6c72",
    "text_label": "#6b6c72",
    "track_off": "#c7c7cc",
}


def resolve_theme_mode(theme_setting: str) -> str:
    """'light'/'dark' bleiben wie angegeben, 'system' folgt der OS-Einstellung."""
    if theme_setting in ("light", "dark"):
        return theme_setting
    hints = QGuiApplication.styleHints()
    try:
        return "dark" if hints.colorScheme() == Qt.ColorScheme.Dark else "light"
    except AttributeError:
        return "dark"


def _shade(hex_color: str, factor: float) -> str:
    color = QColor(hex_color)
    if factor >= 1:
        return color.lighter(int(factor * 100)).name()
    return color.darker(int(100 / factor)).name()


def build_stylesheet(mode: str, accent: str) -> str:
    palette = DARK_PALETTE if mode == "dark" else LIGHT_PALETTE
    accent_hover = _shade(accent, 1.15)
    disabled_text = palette["text_secondary"]

    return f"""
    QWidget {{
        background-color: {palette['window_bg']};
        color: {palette['text_primary']};
        font-size: 13px;
    }}
    QMainWindow {{ background-color: {palette['window_bg']}; }}

    #leftPanel {{ background-color: {palette['panel_bg']}; }}
    #rightPanel {{ background-color: {palette['window_bg']}; }}

    QLabel[role="sectionLabel"] {{
        color: {palette['text_label']};
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.5px;
    }}
    QLabel[role="deviceName"] {{ font-size: 14px; font-weight: 600; }}
    QLabel[role="hint"] {{ color: {palette['text_secondary']}; }}

    QComboBox, QLineEdit {{
        background-color: {palette['input_bg']};
        border: 1px solid {palette['border']};
        border-radius: 6px;
        padding: 6px 10px;
        min-height: 22px;
    }}
    QComboBox:hover, QLineEdit:hover {{ background-color: {palette['input_hover']}; }}
    QComboBox::drop-down {{ border: none; width: 24px; }}
    QComboBox QAbstractItemView {{
        background-color: {palette['input_bg']};
        border: 1px solid {palette['border']};
        selection-background-color: {accent};
        outline: none;
    }}

    QPushButton {{
        background-color: {palette['input_bg']};
        border: 1px solid {palette['border']};
        border-radius: 6px;
        padding: 8px 14px;
    }}
    QPushButton:hover {{ background-color: {palette['input_hover']}; }}
    QPushButton:disabled {{ color: {disabled_text}; }}

    QPushButton[role="primary"] {{
        background-color: {accent};
        color: white;
        border: none;
        font-weight: 600;
        padding: 10px 16px;
    }}
    QPushButton[role="primary"]:hover {{ background-color: {accent_hover}; }}
    QPushButton[role="primary"]:disabled {{ background-color: {palette['border']}; color: {disabled_text}; }}

    QPushButton[role="icon"] {{
        background-color: transparent;
        border: none;
        border-radius: 6px;
        padding: 6px;
        font-size: 15px;
    }}
    QPushButton[role="icon"]:hover {{ background-color: {palette['input_hover']}; }}
    QPushButton[role="icon"]:disabled {{ color: {disabled_text}; }}

    #segmentedControl {{
        background-color: {palette['input_bg']};
        border: 1px solid {palette['border']};
        border-radius: 8px;
    }}
    #segmentButton {{
        background-color: transparent;
        border: none;
        border-radius: 6px;
        padding: 6px 2px;
        font-size: 12px;
        color: {palette['text_secondary']};
    }}
    #segmentButton:checked {{
        background-color: {palette['card_bg']};
        color: {palette['text_primary']};
        font-weight: 600;
    }}

    QSlider::groove:horizontal {{
        height: 4px;
        background: {palette['track_off']};
        border-radius: 2px;
    }}
    QSlider::sub-page:horizontal {{ background: {accent}; border-radius: 2px; }}
    QSlider::handle:horizontal {{
        background: {accent};
        width: 14px;
        height: 14px;
        margin: -5px 0;
        border-radius: 7px;
    }}
    QSlider:disabled::sub-page:horizontal {{ background: {palette['border']}; }}
    QSlider:disabled::handle:horizontal {{ background: {palette['border']}; }}

    #previewArea {{
        background-color: {palette['panel_bg']};
        border: 1px solid {palette['border']};
        border-radius: 10px;
        color: {palette['text_secondary']};
        font-size: 14px;
    }}

    #thumbnailStrip {{ background-color: transparent; border: none; }}
    #thumbnailTile {{
        background-color: {palette['card_bg']};
        border: 1px solid {palette['border']};
        border-radius: 8px;
    }}
    #thumbnailTile[selected="true"] {{ border: 2px solid {accent}; }}
    #deleteChip {{
        background-color: rgba(0, 0, 0, 0.55);
        color: white;
        border: none;
        border-radius: 10px;
        font-weight: 700;
        padding: 0px;
        font-size: 13px;
    }}
    #deleteChip:hover {{ background-color: rgba(200, 40, 40, 0.85); }}

    #languageChip {{
        border-radius: 14px;
        padding: 5px 12px;
        border: 1px solid {palette['border']};
        background-color: {palette['input_bg']};
    }}
    #languageChip:checked {{
        background-color: {accent};
        color: white;
        border-color: {accent};
    }}

    QDialog {{ background-color: {palette['panel_bg']}; }}

    #settingsScrollArea, #settingsScrollArea > QWidget > QWidget {{
        background-color: {palette['panel_bg']};
        border: none;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {palette['border']};
        border-radius: 4px;
        min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {palette['text_secondary']}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
    """
