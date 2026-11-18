import logging
import os
import tempfile
from pathlib import Path

from PyQt6.QtCore import QThread
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QFileDialog
from PyQt6.QtWidgets import QFrame
from PyQt6.QtWidgets import QHBoxLayout
from PyQt6.QtWidgets import QLabel
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtWidgets import QVBoxLayout

from followthelyrics.addons.catalogue import Catalogue
from followthelyrics.addons.catalogue import CatalogueAddon
from followthelyrics.addons.catalogue import is_newer

logger = logging.getLogger(__name__)


class CatalogueTask(QThread):
    completed = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, client, addon=None, destination=None, parent=None):
        super().__init__(parent)
        self.client = client
        self.addon = addon
        self.destination = destination

    def run(self):
        try:
            if self.addon is None:
                self.completed.emit(self.client.fetch())
            else:
                self.client.download(self.addon, self.destination)
                self.completed.emit(self.destination)
        except Exception as exc:
            logger.exception("Add-on catalogue operation failed")
            self.failed.emit(str(exc))


class AddonsPage(QFrame):
    def __init__(self, app):
        super().__init__()
        self.setProperty("role", "card")
        self.app = app
        self.catalogue = Catalogue()
        self.catalogue_loaded = False
        self.entries: list[CatalogueAddon] = []
        self.task = None

        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(24, 22, 24, 22)
        self.lay.setSpacing(14)

        title = QLabel("Add-on catalogue")
        title.setProperty("role", "cardtitle")
        self.lay.addWidget(title)
        note = QLabel(
            "Browse integrations approved by the FollowTheLyrics developer. "
            "Game-side mods may also require installation in the game."
        )
        note.setProperty("role", "hint")
        note.setWordWrap(True)
        self.lay.addWidget(note)

        actions = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh catalogue")
        self.refresh_btn.clicked.connect(self.refresh_catalogue)
        actions.addWidget(self.refresh_btn)
        self.manual_btn = QPushButton("Install ZIP manually")
        self.manual_btn.clicked.connect(self.install_zip)
        actions.addWidget(self.manual_btn)
        actions.addStretch(1)
        self.lay.addLayout(actions)

        self.status = QLabel("Catalogue has not been loaded yet.")
        self.status.setProperty("role", "hint")
        self.status.setWordWrap(True)
        self.lay.addWidget(self.status)

        self.catalogue_layout = QVBoxLayout()
        self.lay.addLayout(self.catalogue_layout)

        installed = QLabel("Installed add-ons")
        installed.setProperty("role", "cardtitle")
        self.lay.addWidget(installed)
        self.installed_layout = QVBoxLayout()
        self.lay.addLayout(self.installed_layout)
        self.render_installed()

    def load_catalogue_once(self):
        if not self.catalogue_loaded:
            self.catalogue_loaded = True
            self.refresh_catalogue()

    @staticmethod
    def clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            child = item.widget()
            if child is not None:
                child.deleteLater()

    def start_task(self, task, on_success):
        if self.task is not None:
            return
        self.task = task
        self.refresh_btn.setEnabled(False)
        task.completed.connect(on_success)
        task.failed.connect(self.task_failed)
        task.finished.connect(self.task_finished)
        task.start()

    def task_finished(self):
        self.refresh_btn.setEnabled(True)
        old = self.task
        self.task = None
        if old is not None:
            old.deleteLater()

    def task_failed(self, message):
        self.status.setText(f"Could not complete operation: {message}")

    def refresh_catalogue(self):
        self.status.setText("Checking approved add-ons...")
        self.start_task(
            CatalogueTask(self.catalogue, parent=self), self.show_catalogue
        )

    def show_catalogue(self, entries):
        self.entries = entries
        self.clear_layout(self.catalogue_layout)
        self.status.setText(
            f"{len(entries)} approved add-on(s) available."
            if entries
            else "No approved add-ons are published yet."
        )
        installed = {a.id: a for a in self.app.addons.list_addons()}
        for addon in entries:
            local = installed.get(addon.id) if addon.kind == "ftl" else None
            earlier = (
                local.version
                if local
                else self.app.addons.external_version(addon.id)
            )
            update_available = earlier is not None and is_newer(
                earlier, addon.version
            )
            row = QFrame()
            row.setProperty("role", "card")
            line = QHBoxLayout(row)
            details = QVBoxLayout()
            title = QLabel(f"{addon.name}  ·  v{addon.version}")
            details.addWidget(title)
            desc = QLabel(addon.description)
            desc.setWordWrap(True)
            desc.setProperty("role", "hint")
            details.addWidget(desc)
            kind = "FTL plug-in" if addon.kind == "ftl" else "Game mod"
            badge = QLabel(f"Approved  ·  {kind}")
            badge.setProperty("role", "hint")
            details.addWidget(badge)
            if earlier:
                note = QLabel(
                    f"{'Installed' if local else 'Downloaded'}: v{earlier}"
                    + ("  ·  Update available" if update_available else "")
                )
                note.setProperty("role", "hint")
                details.addWidget(note)
            line.addLayout(details, 1)
            if local:
                label = "Update" if update_available else "Installed"
            elif addon.kind == "external":
                label = (
                    "Download update" if update_available else "Download ZIP"
                )
            else:
                label = "Install"
            btn = QPushButton(label)
            btn.setEnabled(local is None or update_available)
            btn.clicked.connect(
                lambda checked=False, a=addon: self.get_approved(a)
            )
            line.addWidget(btn)
            self.catalogue_layout.addWidget(row)

    def get_approved(self, addon):
        if self.task is not None:
            return
        if addon.kind == "external":
            name = f"{addon.id}-{addon.version}.zip"
            chosen, _ = QFileDialog.getSaveFileName(
                self,
                "Save approved game integration",
                name,
                "ZIP archives (*.zip)",
            )
            if not chosen:
                return
            destination = Path(chosen)
        else:
            fd, name = tempfile.mkstemp(prefix="ftl-addon-", suffix=".zip")
            os.close(fd)
            os.unlink(name)
            destination = Path(name)
        self.status.setText(f"Downloading {addon.name}...")
        self.start_task(
            CatalogueTask(self.catalogue, addon, destination, self),
            lambda path, a=addon: self.approved_downloaded(a, path),
        )

    def approved_downloaded(self, addon, path):
        if addon.kind == "external":
            self.app.addons.mark_external_download(addon.id, addon.version)
            QMessageBox.information(
                self,
                "Download complete",
                f"Saved {addon.name} to:\n{path}\n\n"
                "Installation instructions:\n"
                f"{addon.instructions or 'See the mod author.'}",
            )
            self.status.setText(f"Downloaded {addon.name}.")
            self.show_catalogue(self.entries)
            return
        try:
            current = {a.id for a in self.app.addons.list_addons()}
            if addon.id in current:
                installed = self.app.addons.update(
                    addon.id, path, approved=True
                )
            else:
                installed = self.app.addons.install(path, approved=True)
            if installed.id != addon.id:
                self.app.addons.uninstall(installed.id)
                raise ValueError("Downloaded package ID differs from catalogue")
            self.status.setText(
                f"Installed {addon.name}. Enable it below to use it."
            )
        except Exception as exc:  # noqa: BLE001
            self.task_failed(str(exc))
        finally:
            Path(path).unlink(missing_ok=True)
        self.render_installed()
        self.show_catalogue(self.entries)

    def install_zip(self):
        chosen, _ = QFileDialog.getOpenFileName(
            self, "Install an add-on ZIP", "", "ZIP archives (*.zip)"
        )
        if not chosen:
            return
        confirm = QMessageBox.warning(
            self,
            "Unverified add-on",
            "This ZIP has not been approved by the FollowTheLyrics developer. "
            "Python add-ons can access files and the network with your "
            "account's permissions. Only install trusted add-ons. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            addon = self.app.addons.install(chosen)
            self.status.setText(
                f"Installed {addon.name}. It is disabled by default."
            )
            self.render_installed()
            self.show_catalogue(self.entries)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Install failed", str(exc))

    def render_installed(self):
        self.clear_layout(self.installed_layout)
        installed = self.app.addons.list_addons()
        if not installed:
            hint = QLabel(
                "Nothing installed yet. Choose an add-on or import a ZIP."
            )
            hint.setProperty("role", "hint")
            hint.setWordWrap(True)
            self.installed_layout.addWidget(hint)
            return
        for addon in installed:
            row = QFrame()
            line = QHBoxLayout(row)
            detail = QLabel(
                f"{addon.name}  ·  v{addon.version}\n"
                f"{'Approved' if addon.approved else 'Unverified'}"
                f"  ·  {'Enabled' if addon.enabled else 'Disabled'}"
                + (f"\nError: {addon.error}" if addon.error else "")
            )
            detail.setWordWrap(True)
            line.addWidget(detail, 1)
            toggle = QPushButton("Disable" if addon.enabled else "Enable")
            toggle.clicked.connect(
                lambda checked=False, name=addon.id, on=not addon.enabled: (
                    self.toggle_addon(name, on)
                )
            )
            line.addWidget(toggle)
            remove = QPushButton("Remove")
            remove.clicked.connect(
                lambda checked=False, name=addon.id: self.remove_addon(name)
            )
            line.addWidget(remove)
            self.installed_layout.addWidget(row)

    def toggle_addon(self, addon_id, enable):
        if enable:
            accepted = QMessageBox.warning(
                self,
                "Enable third-party code",
                "Enabling an add-on runs its Python code with your account's "
                "permissions. Only enable add-ons you trust.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if accepted != QMessageBox.StandardButton.Yes:
                return
        try:
            if enable:
                self.app.addons.enable(addon_id)
            else:
                self.app.addons.disable(addon_id)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Add-on error", str(exc))
        self.render_installed()

    def remove_addon(self, addon_id):
        answer = QMessageBox.question(
            self,
            "Remove add-on",
            f"Remove {addon_id} from FollowTheLyrics?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.app.addons.uninstall(addon_id)
            self.render_installed()
            self.show_catalogue(self.entries)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Remove failed", str(exc))
