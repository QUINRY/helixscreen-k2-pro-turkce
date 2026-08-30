"""Tests for the reversible K2 Pro Turkish overlay migration."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANAGER_PATH = PROJECT_ROOT / "installer" / "k2_turkish_overlay.py"


def load_manager():
    spec = importlib.util.spec_from_file_location("k2_turkish_overlay", MANAGER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def configure_tree(module, tmp_path: Path, *, marker_version: str, stock_version: str):
    root = tmp_path / "opt" / "helixscreen"
    config = root / "config"
    config.mkdir(parents=True)
    backups = tmp_path / "backups"
    old_backup = backups / "pre-turkish-old"
    old_backup.mkdir(parents=True)

    module.INSTALL_ROOT = str(root)
    module.SETTINGS_PATH = str(config / "settings.json")
    module.RELEASE_INFO_PATH = str(root / "release_info.json")
    module.MARKER_PATH = str(config / "quinry-turkish-package.json")
    module.MANAGER_PATH = str(config / "quinry-turkish-manager.py")
    module.BACKUP_ROOT = str(backups)
    module.POINTER_PATH = str(backups / "current")

    relatives = (
        "bin/helix-screen",
        "release_info.json",
        "ui_xml/translations/tr.xml",
        "ui_xml/translations/translations.xml",
        "ui_xml/wizard_language_chooser.xml",
        "assets/images/flags/flag_tr.bin",
        "assets/images/flags/flag_tr.png",
    )
    module.FILES = {relative: str(root / relative) for relative in relatives}
    for relative, destination in module.FILES.items():
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(("official-" + relative).encode())

    settings = {
        "language": "tr",
        "display": {"rotate": 270},
        "input": {"touch_range": {"max_x": 479, "max_y": 799}},
        "printers": {"default": {"hardware": {"cfs": True}}},
    }
    Path(module.SETTINGS_PATH).write_text(json.dumps(settings), encoding="utf-8")
    Path(module.RELEASE_INFO_PATH).write_text(
        json.dumps(
            {
                "project_name": "helixscreen",
                "project_owner": "prestonbrown",
                "version": stock_version,
            }
        ),
        encoding="utf-8",
    )
    Path(module.MARKER_PATH).write_text(
        json.dumps(
            {
                "mode": "overlay",
                "version": marker_version,
                "backup_dir": str(old_backup),
            }
        ),
        encoding="utf-8",
    )
    Path(module.MANAGER_PATH).write_text("old-manager", encoding="utf-8")
    return settings, old_backup


def test_stock_update_creates_clean_new_backup(tmp_path, monkeypatch):
    manager = load_manager()
    if not hasattr(manager.os, "chown"):
        monkeypatch.setattr(manager.os, "chown", lambda *_: None, raising=False)
    settings, old_backup = configure_tree(
        manager,
        tmp_path,
        marker_version="v0.99.117-tr.1",
        stock_version="v0.99.118",
    )

    backup = Path(manager.create_original_backup())

    assert backup != old_backup
    saved = json.loads((backup / "settings.json").read_text(encoding="utf-8"))
    assert saved["language"] == "en"
    for protected in ("display", "input", "printers"):
        assert saved[protected] == settings[protected]

    absent = json.loads((backup / "absent.json").read_text(encoding="utf-8"))
    assert "config/quinry-turkish-package.json" in absent
    assert "config/quinry-turkish-manager.py" in absent
    assert "ui_xml/translations/tr.xml" in absent
    assert "assets/images/flags/flag_tr.bin" in absent
    assert "assets/images/flags/flag_tr.png" in absent
    assert not (backup / "quinry-turkish-package.json").exists()
    assert not (backup / "quinry-turkish-manager.py").exists()
    assert not (backup / "files/ui_xml/translations/tr.xml").exists()
    assert not (backup / "files/assets/images/flags/flag_tr.bin").exists()
    assert not (backup / "files/assets/images/flags/flag_tr.png").exists()

    manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["superseded_overlay"] == "v0.99.117-tr.1"
    assert (backup / "files/bin/helix-screen").read_bytes() == b"official-bin/helix-screen"


def test_same_release_reuses_original_backup(tmp_path, monkeypatch):
    manager = load_manager()
    if not hasattr(manager.os, "chown"):
        monkeypatch.setattr(manager.os, "chown", lambda *_: None, raising=False)
    _, old_backup = configure_tree(
        manager,
        tmp_path,
        marker_version=manager.PACKAGE_VERSION,
        stock_version="v0.99.118",
    )

    assert Path(manager.create_original_backup()) == old_backup


@pytest.mark.parametrize("stock_version", ["v0.99.119", "v10.99.118"])
def test_stale_marker_rejects_wrong_stock_version(
    tmp_path, monkeypatch, stock_version
):
    manager = load_manager()
    if not hasattr(manager.os, "chown"):
        monkeypatch.setattr(manager.os, "chown", lambda *_: None, raising=False)
    configure_tree(
        manager,
        tmp_path,
        marker_version="v0.99.117-tr.1",
        stock_version=stock_version,
    )

    with pytest.raises(RuntimeError, match="not the supported stock version"):
        manager.create_original_backup()
