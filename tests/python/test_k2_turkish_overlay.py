"""Tests for the reversible K2 Pro Turkish overlay migration."""

from __future__ import annotations

import importlib.util
import json
import zipfile
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
        marker_version="v0.99.118-tr.1",
        stock_version="v1.0.0",
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
    assert manifest["superseded_overlay"] == "v0.99.118-tr.1"
    assert (backup / "files/bin/helix-screen").read_bytes() == b"official-bin/helix-screen"


def test_same_release_reuses_original_backup(tmp_path, monkeypatch):
    manager = load_manager()
    if not hasattr(manager.os, "chown"):
        monkeypatch.setattr(manager.os, "chown", lambda *_: None, raising=False)
    _, old_backup = configure_tree(
        manager,
        tmp_path,
        marker_version=manager.PACKAGE_VERSION,
        stock_version="v1.0.0",
    )

    assert Path(manager.create_original_backup()) == old_backup


@pytest.mark.parametrize("stock_version", ["v0.99.118", "v11.0.0", "v1.0.01"])
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


def prepared_install(tmp_path, monkeypatch):
    manager = load_manager()
    monkeypatch.setattr(manager.os, "chown", lambda *_: None, raising=False)
    settings, _ = configure_tree(manager, tmp_path,
                                 marker_version="v0.99.118-tr.1", stock_version="v1.0.0")
    Path(manager.MARKER_PATH).unlink()
    Path(manager.MANAGER_PATH).unlink()
    settings['language'] = 'en'
    Path(manager.SETTINGS_PATH).write_text(json.dumps(settings), encoding='utf-8')
    monkeypatch.setattr(manager, 'stop_service', lambda: None)
    monkeypatch.setattr(manager, 'start_and_verify_service', lambda: None)
    payloads = {name: ('turkish-' + name).encode() for name in manager.FILES}
    payloads['release_info.json'] = json.dumps({'version': manager.PACKAGE_VERSION,
                                               'project_owner': 'QUINRY'}).encode()
    payloads[manager.MANAGER_MEMBER] = b'# test manager\n'
    manifest = {'package_version': manager.PACKAGE_VERSION,
                'files': {k: {'sha256': manager.sha256_bytes(v)} for k, v in payloads.items()}}
    archive = tmp_path / 'overlay.zip'
    with zipfile.ZipFile(archive, 'w') as z:
        z.writestr('manifest.json', json.dumps(manifest))
        for name, data in payloads.items():
            z.writestr(name, data)
    work = tmp_path / 'work'
    work.mkdir()
    return manager, settings, archive, work


def test_install_remove_preserves_touch_and_cfs(tmp_path, monkeypatch):
    manager, before, archive, work = prepared_install(tmp_path, monkeypatch)
    originals = {name: Path(path).read_bytes() for name, path in manager.FILES.items()}
    manager.install_overlay(str(archive), str(work))
    assert manager.read_json(manager.SETTINGS_PATH) == dict(before, language='tr')
    assert manager.read_json(manager.MARKER_PATH)['version'] == 'v1.0.0-tr.1'
    assert Path(manager.FILES['bin/helix-screen']).read_bytes() != originals['bin/helix-screen']
    manager.remove_overlay()
    assert manager.read_json(manager.SETTINGS_PATH) == before
    assert not Path(manager.MARKER_PATH).exists()
    assert all(Path(manager.FILES[name]).read_bytes() == data for name, data in originals.items())


def test_start_failure_restores_previous_files(tmp_path, monkeypatch):
    manager, before, archive, work = prepared_install(tmp_path, monkeypatch)
    originals = {name: Path(path).read_bytes() for name, path in manager.FILES.items()}
    attempts = []
    def start():
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError('simulated startup failure')
    monkeypatch.setattr(manager, 'start_and_verify_service', start)
    with pytest.raises(RuntimeError, match='simulated startup failure'):
        manager.install_overlay(str(archive), str(work))
    assert len(attempts) == 2
    assert manager.read_json(manager.SETTINGS_PATH) == before
    assert all(Path(manager.FILES[name]).read_bytes() == data for name, data in originals.items())


def test_rejects_corrupt_payload_before_writes(tmp_path, monkeypatch):
    manager, before, archive, work = prepared_install(tmp_path, monkeypatch)
    with zipfile.ZipFile(archive) as z:
        payloads = {n: z.read(n) for n in z.namelist()}
    payloads['bin/helix-screen'] = b'corrupt binary'
    with zipfile.ZipFile(archive, 'w') as z:
        for name, data in payloads.items():
            z.writestr(name, data)
    original = Path(manager.FILES['bin/helix-screen']).read_bytes()
    with pytest.raises(RuntimeError, match='hash mismatch'):
        manager.install_overlay(str(archive), str(work))
    assert Path(manager.FILES['bin/helix-screen']).read_bytes() == original
    assert manager.read_json(manager.SETTINGS_PATH) == before


@pytest.mark.parametrize('version', ['v0.99.118', 'v0.99.118-tr.1', 'v11.0.0', 'v1.0.01'])
def test_direct_overlay_rejects_mismatched_base(tmp_path, monkeypatch, version):
    manager, before, archive, work = prepared_install(tmp_path, monkeypatch)
    Path(manager.RELEASE_INFO_PATH).write_text(
        json.dumps({'version': version, 'project_owner': 'prestonbrown'}), encoding='utf-8')
    original = Path(manager.FILES['bin/helix-screen']).read_bytes()
    with pytest.raises(RuntimeError, match='requires HelixScreen 1.0.0'):
        manager.install_overlay(str(archive), str(work))
    assert Path(manager.FILES['bin/helix-screen']).read_bytes() == original
    assert manager.read_json(manager.SETTINGS_PATH) == before


def test_remove_refuses_stale_backup_after_upstream_update(tmp_path, monkeypatch):
    manager, _, archive, work = prepared_install(tmp_path, monkeypatch)
    manager.install_overlay(str(archive), str(work))
    Path(manager.RELEASE_INFO_PATH).write_text(
        json.dumps({'version': 'v1.0.1', 'project_owner': 'prestonbrown'}), encoding='utf-8')
    Path(manager.FILES['bin/helix-screen']).write_bytes(b'new upstream binary')
    with pytest.raises(RuntimeError, match='refusing stale rollback'):
        manager.remove_overlay()
    assert Path(manager.FILES['bin/helix-screen']).read_bytes() == b'new upstream binary'
    assert manager.read_json(manager.RELEASE_INFO_PATH)['version'] == 'v1.0.1'
