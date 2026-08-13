from __future__ import annotations

from PySide6.QtWidgets import QComboBox


class WideComboBox(QComboBox):
    """QComboBox, dessen Popup-Liste mindestens so breit wie die Box selbst aufklappt.

    Qt sizt das Popup standardmäßig nach dem breitesten Eintragstext — bei einer Combo, die
    per Layout breiter gezogen wurde als ihr Inhalt (hier: alle Combos in `SettingsPanel`,
    die volle Kartenbreite einnehmen), klappt das Popup dadurch sichtbar schmaler auf als der
    Auslöser darüber.
    """

    def showPopup(self) -> None:
        self.view().setMinimumWidth(self.width())
        super().showPopup()
