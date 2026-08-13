from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication

from scanner_app.ui import icons

# Farbwerte 1:1 aus dem vorgegebenen Design-Mockup (Dokumentenscanner-UI.html) übernommen —
# dort als c(light, dark) Paare je UI-Element definiert. Damit das Ergebnis auf Windows und
# Linux exakt gleich aussieht, wird bewusst NICHT auf systemnahe Qt-Paletten/-Stile
# zurückgegriffen, sondern die App zeichnet sich komplett selbst (siehe main_window.py).
LIGHT_PALETTE = {
    "window_bg": "#f3f3f3",
    "titlebar_bg": "rgba(255,255,255,.75)",
    "titlebar_border": "rgba(0,0,0,.06)",
    "text_primary": "#1b1b1b",
    "text_label": "rgba(0,0,0,.5)",
    "text_secondary": "rgba(0,0,0,.6)",
    "text_hint": "rgba(0,0,0,.4)",
    # Anders als bei den QSS-Farben oben braucht es hier deckende Hex-Werte statt rgba():
    # QtSvg (für die selbstgezeichneten Icons, siehe icons.py) ignoriert `rgba()` in
    # Stroke-/Fill-Attributen stillschweigend (Icon bleibt unsichtbar) — nur Qt-Stylesheets
    # unterstützen die CSS-Funktionsschreibweise.
    "winbtn_color": "#4d4d4d",
    "winbtn_hover": "rgba(0,0,0,.06)",
    "rail_bg": "#f3f3f3",
    "rail_border": "rgba(0,0,0,.06)",
    "rail_icon": "#666666",
    "popover_bg": "#ffffff",
    "popover_border": "rgba(0,0,0,.08)",
    "left_panel_bg": "#fafafa",
    "left_panel_border": "rgba(0,0,0,.06)",
    "card_bg": "#ffffff",
    "card_border": "rgba(0,0,0,.08)",
    "segmented_bg": "rgba(0,0,0,.04)",
    "segment_selected_bg": "#ffffff",
    "segment_unselected_text": "rgba(0,0,0,.6)",
    "input_bg": "#ffffff",
    "input_border": "rgba(0,0,0,.12)",
    "toggle_off": "rgba(0,0,0,.2)",
    "preview_bg": "#ebedf0",
    "thumb_strip_bg": "rgba(255,255,255,.5)",
    "toast_bg": "#1b1b1b",
    "chip_border": "rgba(0,0,0,.15)",
    "shadow": "rgba(0,0,0,.35)",
    "menu_row_hover_alpha": 0.06,
}

DARK_PALETTE = {
    "window_bg": "#202020",
    "titlebar_bg": "rgba(40,40,40,.75)",
    "titlebar_border": "rgba(255,255,255,.08)",
    "text_primary": "#f2f2f2",
    "text_label": "rgba(255,255,255,.5)",
    "text_secondary": "rgba(255,255,255,.6)",
    "text_hint": "rgba(255,255,255,.4)",
    "winbtn_color": "#bfbfbf",
    "winbtn_hover": "rgba(255,255,255,.1)",
    "rail_bg": "#202020",
    "rail_border": "rgba(255,255,255,.08)",
    "rail_icon": "#a6a6a6",
    "popover_bg": "#2d2d2d",
    "popover_border": "rgba(255,255,255,.1)",
    "left_panel_bg": "#242424",
    "left_panel_border": "rgba(255,255,255,.08)",
    "card_bg": "#2d2d2d",
    "card_border": "rgba(255,255,255,.1)",
    "segmented_bg": "rgba(255,255,255,.06)",
    "segment_selected_bg": "#3a3a3a",
    "segment_unselected_text": "rgba(255,255,255,.55)",
    "input_bg": "#2d2d2d",
    "input_border": "rgba(255,255,255,.14)",
    "toggle_off": "rgba(255,255,255,.22)",
    "preview_bg": "#171717",
    "thumb_strip_bg": "rgba(255,255,255,.04)",
    "toast_bg": "#3a3a3a",
    "chip_border": "rgba(255,255,255,.16)",
    "shadow": "rgba(0,0,0,.5)",
    "menu_row_hover_alpha": 0.15,
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


def _accent_rgba(accent: str, alpha: float) -> str:
    color = QColor(accent)
    return f"rgba({color.red()},{color.green()},{color.blue()},{alpha})"


def build_stylesheet(mode: str, accent: str) -> str:
    p = DARK_PALETTE if mode == "dark" else LIGHT_PALETTE
    accent_hover = _shade(accent, 1.15)
    accent_wash_strong = _accent_rgba(accent, 0.2 if mode == "dark" else 0.1)
    accent_wash_soft = _accent_rgba(accent, 0.18 if mode == "dark" else 0.08)
    menu_selected = _accent_rgba(accent, 0.15 if mode == "dark" else 0.06)

    return f"""
    QWidget {{
        background-color: {p['window_bg']};
        color: {p['text_primary']};
        font-size: 13px;
        font-family: "Segoe UI", -apple-system, sans-serif;
    }}
    QMainWindow {{ background-color: transparent; }}
    #outerRoot {{ background-color: transparent; }}
    QLabel {{ background: transparent; }}
    #scanSpinner {{ background: transparent; }}
    QToolTip {{
        background-color: {p['popover_bg']};
        color: {p['text_primary']};
        border: 1px solid {p['popover_border']};
        padding: 6px 8px;
        border-radius: 4px;
    }}

    #windowFrame {{ background-color: {p['window_bg']}; border-radius: 8px; }}
    #windowFrame[maximized="true"] {{ border-radius: 0px; }}

    #titleBar {{ background-color: {p['titlebar_bg']}; border-bottom: 1px solid {p['titlebar_border']}; }}
    #titleLabel {{ font-size: 13px; font-weight: 600; color: {p['text_primary']}; background: transparent; }}
    #winButton {{ background-color: transparent; border: none; border-radius: 0; }}
    #winButton:hover {{ background-color: {p['winbtn_hover']}; }}
    #winButton[close="true"]:hover {{ background-color: #c42b1c; }}

    #iconRail {{ background-color: {p['rail_bg']}; border-right: 1px solid {p['rail_border']}; }}
    #railScanButton {{ background-color: {accent}; border: none; border-radius: 6px; }}
    #railScanButton:hover {{ background-color: {accent_hover}; }}
    #railIconButton {{ background-color: transparent; border: none; border-radius: 6px; color: {p['rail_icon']}; }}
    #railIconButton:hover {{ background-color: {p['winbtn_hover']}; }}
    #railIconButton[active="true"] {{ background-color: {accent_wash_strong}; }}
    #pathPopover {{
        background-color: {p['popover_bg']};
        border: 1px solid {p['popover_border']};
        border-radius: 6px;
        color: {p['text_primary']};
    }}
    #pathPopoverLabel {{ font-size: 11px; color: {p['text_label']}; background: transparent; }}
    #pathPopoverValue {{ font-size: 12px; color: {p['text_primary']}; font-family: monospace; background: transparent; }}

    #leftPanel {{ background-color: {p['left_panel_bg']}; border-right: 1px solid {p['left_panel_border']}; }}
    #rightPanel {{ background-color: {p['preview_bg']}; }}

    #scannerCard {{
        background-color: {p['card_bg']};
        border: 1px solid {p['card_border']};
        border-radius: 6px;
    }}
    #scannerCard:hover {{ background-color: {p['card_bg']}; }}
    #scannerLabel {{ font-size: 11px; color: {p['text_label']}; background: transparent; }}
    #scannerName {{ font-size: 13px; font-weight: 600; color: {p['text_primary']}; background: transparent; }}
    QComboBox#scannerCombo {{
        border: none;
        background: transparent;
        padding: 0px;
        font-size: 13px;
        font-weight: 600;
        color: {p['text_primary']};
        min-height: 0px;
    }}
    QComboBox#scannerCombo:disabled {{ color: {p['text_hint']}; }}

    QLabel[role="sectionLabel"] {{
        color: {p['text_label']};
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.5px;
        background: transparent;
    }}
    QLabel[role="hint"] {{ color: {p['text_hint']}; background: transparent; font-size: 12px; }}
    #resolutionHint {{ color: {p['text_hint']}; background: transparent; font-size: 11px; margin-top: -2px; }}
    QLabel[role="sliderValue"] {{ color: {p['text_label']}; background: transparent; }}

    QComboBox, QLineEdit {{
        background-color: {p['input_bg']};
        border: 1px solid {p['input_border']};
        border-radius: 6px;
        padding: 6px 10px;
        min-height: 22px;
        color: {p['text_primary']};
    }}
    QComboBox:disabled {{ color: {p['text_hint']}; }}
    QComboBox::drop-down {{ border: none; width: 26px; }}
    QComboBox::down-arrow {{
        image: url({icons.icon_file_path(icons.CHEVRON_DOWN, p['rail_icon'], size=11)});
        width: 11px;
        height: 11px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {p['popover_bg']};
        border: 1px solid {p['popover_border']};
        selection-background-color: {menu_selected};
        selection-color: {p['text_primary']};
        outline: none;
        padding: 2px;
    }}

    QPushButton {{
        background-color: {p['input_bg']};
        border: 1px solid {p['input_border']};
        border-radius: 6px;
        padding: 8px 14px;
        color: {p['text_primary']};
    }}
    QPushButton:hover {{ background-color: {p['popover_bg']}; }}
    QPushButton:disabled {{ color: {p['text_hint']}; }}

    QPushButton[role="primary"] {{
        background-color: {accent};
        color: white;
        border: none;
        font-weight: 600;
        padding: 10px 16px;
    }}
    QPushButton[role="primary"]:hover {{ background-color: {accent_hover}; }}
    QPushButton[role="primary"]:disabled {{ background-color: {p['input_border']}; color: {p['text_hint']}; }}
    QPushButton[role="primaryLeft"], QPushButton[role="primaryRight"] {{
        background-color: {accent};
        color: white;
        border: none;
        font-weight: 600;
        font-size: 14px;
        padding: 10px 16px;
    }}
    QPushButton[role="primaryLeft"]:hover, QPushButton[role="primaryRight"]:hover {{ background-color: {accent_hover}; }}
    QPushButton[role="primaryLeft"]:disabled, QPushButton[role="primaryRight"]:disabled {{
        background-color: {p['input_border']}; color: {p['text_hint']};
    }}
    QPushButton[role="primaryLeft"] {{ border-radius: 6px 0 0 6px; }}
    QPushButton[role="primaryRight"] {{ border-radius: 0 6px 6px 0; }}
    #scanActiveRow {{ background-color: {accent}; border-radius: 6px; padding: 9px 12px; }}

    QPushButton[role="icon"] {{
        background-color: transparent;
        border: none;
        border-radius: 6px;
        padding: 6px;
    }}
    QPushButton[role="icon"]:hover {{ background-color: {p['winbtn_hover']}; }}
    QPushButton[role="icon"]:disabled {{ color: {p['text_hint']}; }}

    QPushButton[role="secondary"] {{
        background-color: {p['input_bg']};
        border: 1px solid {p['input_border']};
        border-radius: 6px;
        font-size: 12px;
        padding: 8px 12px;
    }}

    QMenu#scanMenu {{
        background-color: {p['popover_bg']};
        border: 1px solid {p['popover_border']};
        border-radius: 8px;
        padding: 4px;
        color: {p['text_primary']};
    }}
    QMenu#scanMenu::item {{
        padding: 9px 10px;
        border-radius: 5px;
        font-size: 13px;
    }}
    QMenu#scanMenu::item:selected {{ background-color: {menu_selected}; }}

    #segmentedControl {{
        background-color: {p['segmented_bg']};
        border: none;
        border-radius: 6px;
    }}
    #segmentButton {{
        background-color: transparent;
        border: none;
        border-radius: 5px;
        padding: 7px 2px;
        font-size: 12px;
        color: {p['segment_unselected_text']};
    }}
    #segmentButton:checked {{
        background-color: {p['segment_selected_bg']};
        color: {p['text_primary']};
        font-weight: 600;
    }}

    QSlider::groove:horizontal {{
        height: 4px;
        background: {p['toggle_off']};
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
    QSlider:disabled::sub-page:horizontal {{ background: {p['input_border']}; }}
    QSlider:disabled::handle:horizontal {{ background: {p['input_border']}; }}

    #previewTopBar {{ border-bottom: 1px solid {p['left_panel_border']}; background: transparent; }}
    #previewTitle {{ font-weight: 600; color: {p['text_primary']}; background: transparent; }}
    #previewCounter {{ color: {p['text_secondary']}; font-size: 13px; background: transparent; }}
    #paperCard {{ background-color: #ffffff; border-radius: 4px; }}
    #emptyStateLabel {{ color: {p['text_hint']}; font-size: 13px; background: transparent; }}

    #thumbStrip {{ background-color: {p['thumb_strip_bg']}; border-top: 1px solid {p['left_panel_border']}; }}
    #thumbnailTile {{ background-color: #ffffff; border-radius: 4px; border: 2px solid transparent; }}
    #thumbnailTile[selected="true"] {{ border: 2px solid {accent}; }}
    #thumbPageBadge {{ color: rgba(0,0,0,.4); font-size: 10px; background: transparent; }}
    #deleteChip {{
        background-color: #ffffff;
        color: rgba(0,0,0,.5);
        border: 1px solid rgba(0,0,0,.15);
        border-radius: 9px;
        font-weight: 700;
        padding: 0px;
        font-size: 12px;
    }}
    #deleteChip:hover {{ background-color: #c42b1c; color: white; border-color: #c42b1c; }}

    #toast {{
        background-color: {p['toast_bg']};
        color: white;
        border-radius: 6px;
        font-size: 13px;
    }}

    #languageChip {{
        border-radius: 14px;
        padding: 5px 12px;
        border: 1px solid {p['chip_border']};
        background-color: transparent;
        color: {p['text_primary']};
        font-size: 12px;
    }}
    #languageChip:checked {{
        background-color: {accent_wash_soft};
        color: {p['text_primary']};
        border-color: {accent};
    }}

    QDialog, QMessageBox {{ background-color: {p['left_panel_bg']}; }}

    #settingsPage {{ background-color: {p['left_panel_bg']}; }}
    #settingsHeader {{
        background-color: {p['card_bg']};
        border-bottom: 1px solid {p['left_panel_border']};
    }}
    #settingsHeaderLabel {{ font-size: 15px; font-weight: 600; color: {p['text_primary']}; background: transparent; }}
    #settingsScrollArea, #settingsScrollArea > QWidget > QWidget,
    #settingsScrollArea > QWidget > QWidget > QWidget {{
        background-color: {p['left_panel_bg']};
        border: none;
    }}
    #settingsDivider {{ background-color: {p['left_panel_border']}; max-height: 1px; min-height: 1px; border: none; }}
    #footerCredit {{ color: {p['text_hint']}; font-size: 12px; background: transparent; }}
    #footerLink {{ color: {accent}; font-size: 12px; background: transparent; }}

    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {p['input_border']};
        border-radius: 4px;
        min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {p['text_secondary']}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
    """


def palette_for(mode: str) -> dict[str, str]:
    return DARK_PALETTE if mode == "dark" else LIGHT_PALETTE
