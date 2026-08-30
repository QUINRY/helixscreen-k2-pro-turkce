#!/usr/bin/env python3
"""Atomically install or remove the Turkish HelixScreen K2 Pro overlay.

This helper runs locally on the printer.  It touches only the HelixScreen
binary, Turkish translation/selector assets, and the top-level language value.
All other settings (including touch calibration and CFS configuration) are
preserved semantically and verified before the service is restarted.
"""

from __future__ import print_function

import argparse
import copy
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import time
import zipfile


PACKAGE_VERSION = "v0.99.118-tr.1"
HELIXSCREEN_VERSION = "0.99.118"
INSTALL_ROOT = "/opt/helixscreen"
SETTINGS_PATH = INSTALL_ROOT + "/config/settings.json"
RELEASE_INFO_PATH = INSTALL_ROOT + "/release_info.json"
MARKER_PATH = INSTALL_ROOT + "/config/quinry-turkish-package.json"
MANAGER_PATH = INSTALL_ROOT + "/config/quinry-turkish-manager.py"
BACKUP_ROOT = "/mnt/UDISK/helixscreen-turkish-backups"
POINTER_PATH = BACKUP_ROOT + "/current"

FILES = {
    "bin/helix-screen": INSTALL_ROOT + "/bin/helix-screen",
    "release_info.json": INSTALL_ROOT + "/release_info.json",
    "ui_xml/translations/tr.xml": INSTALL_ROOT + "/ui_xml/translations/tr.xml",
    "ui_xml/translations/translations.xml": (
        INSTALL_ROOT + "/ui_xml/translations/translations.xml"
    ),
    "ui_xml/wizard_language_chooser.xml": (
        INSTALL_ROOT + "/ui_xml/wizard_language_chooser.xml"
    ),
    "assets/images/flags/flag_tr.bin": (
        INSTALL_ROOT + "/assets/images/flags/flag_tr.bin"
    ),
    "assets/images/flags/flag_tr.png": (
        INSTALL_ROOT + "/assets/images/flags/flag_tr.png"
    ),
}

MANAGER_MEMBER = "installer/k2_turkish_overlay.py"
EXPECTED_MEMBERS = set(["manifest.json", MANAGER_MEMBER] + list(FILES.keys()))


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def read_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def write_atomic(path, data, mode=None, uid=None, gid=None):
    directory = os.path.dirname(path)
    if not os.path.isdir(directory):
        os.makedirs(directory)
    temporary = path + ".turkish-new"
    with open(temporary, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    if mode is not None:
        os.chmod(temporary, mode)
    if uid is not None and gid is not None:
        try:
            os.chown(temporary, uid, gid)
        except PermissionError:
            pass
    os.replace(temporary, path)


def copy_atomic(source, destination, mode=None, uid=None, gid=None):
    with open(source, "rb") as handle:
        write_atomic(destination, handle.read(), mode, uid, gid)


def target_metadata(path, default_mode):
    try:
        metadata = os.stat(path)
        return stat.S_IMODE(metadata.st_mode), metadata.st_uid, metadata.st_gid
    except OSError:
        return default_mode, 0, 0


def service_script():
    for candidate in ("/etc/init.d/helixscreen", "/etc/init.d/S99helixscreen"):
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    raise RuntimeError("HelixScreen service script was not found")


def stop_service():
    subprocess.call([service_script(), "stop"])
    time.sleep(2)
    try:
        os.unlink("/tmp/helix-screen.lock")
    except OSError:
        pass


def start_and_verify_service():
    subprocess.check_call([service_script(), "start"])
    time.sleep(8)
    if subprocess.call(
        ["sh", "-c", "ps w | grep '[h]elix-screen' >/dev/null 2>&1"]
    ) != 0:
        raise RuntimeError("HelixScreen did not remain running")


def safe_backup_dir(path):
    root = os.path.realpath(BACKUP_ROOT)
    candidate = os.path.realpath(path)
    return candidate.startswith(root + os.sep) and candidate != root


def load_overlay(archive_path):
    with zipfile.ZipFile(archive_path, "r") as archive:
        bad = archive.testzip()
        if bad is not None:
            raise RuntimeError("Overlay ZIP CRC failure: " + bad)
        names = archive.namelist()
        if len(names) != len(set(names)) or set(names) != EXPECTED_MEMBERS:
            raise RuntimeError("Overlay ZIP member list is not exact")
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        if manifest.get("package_version") != PACKAGE_VERSION:
            raise RuntimeError("Overlay package version does not match manager")
        payloads = {}
        for name in FILES:
            data = archive.read(name)
            expected = manifest["files"][name]["sha256"]
            if sha256_bytes(data) != expected:
                raise RuntimeError("Overlay member hash mismatch: " + name)
            payloads[name] = data
        manager_data = archive.read(MANAGER_MEMBER)
        manager_expected = manifest["files"][MANAGER_MEMBER]["sha256"]
        if sha256_bytes(manager_data) != manager_expected:
            raise RuntimeError("Overlay manager hash mismatch")
    return manifest, payloads, manager_data


def snapshot_targets(root):
    if os.path.isdir(root):
        shutil.rmtree(root)
    os.makedirs(os.path.join(root, "files"))
    absent = []
    for relative, destination in FILES.items():
        backup = os.path.join(root, "files", relative.replace("/", os.sep))
        if os.path.exists(destination):
            parent = os.path.dirname(backup)
            if not os.path.isdir(parent):
                os.makedirs(parent)
            shutil.copy2(destination, backup)
        else:
            absent.append(relative)
    shutil.copy2(os.path.realpath(SETTINGS_PATH), os.path.join(root, "settings.json"))
    for extra in (MARKER_PATH, MANAGER_PATH):
        name = os.path.basename(extra)
        if os.path.exists(extra):
            shutil.copy2(extra, os.path.join(root, name))
        else:
            absent.append("config/" + name)
    with open(os.path.join(root, "absent.json"), "w", encoding="utf-8") as handle:
        json.dump(absent, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return absent


def restore_snapshot(root):
    absent = read_json(os.path.join(root, "absent.json"))
    for relative, destination in FILES.items():
        backup = os.path.join(root, "files", relative.replace("/", os.sep))
        if relative in absent:
            try:
                os.unlink(destination)
            except OSError:
                pass
        else:
            mode, uid, gid = target_metadata(destination, 0o755 if relative == "bin/helix-screen" else 0o644)
            copy_atomic(backup, destination, mode, uid, gid)

    settings_target = os.path.realpath(SETTINGS_PATH)
    mode, uid, gid = target_metadata(settings_target, 0o600)
    copy_atomic(os.path.join(root, "settings.json"), settings_target, mode, uid, gid)

    for extra in (MARKER_PATH, MANAGER_PATH):
        name = os.path.basename(extra)
        relative = "config/" + name
        backup = os.path.join(root, name)
        if relative in absent:
            try:
                os.unlink(extra)
            except OSError:
                pass
        elif os.path.isfile(backup):
            mode, uid, gid = target_metadata(extra, 0o644)
            copy_atomic(backup, extra, mode, uid, gid)


def create_original_backup():
    superseded_overlay = ""
    if os.path.isfile(MARKER_PATH):
        try:
            marker = read_json(MARKER_PATH)
            existing = marker.get("backup_dir", "")
            if marker.get("mode") == "overlay":
                if (
                    marker.get("version") == PACKAGE_VERSION
                    and safe_backup_dir(existing)
                    and os.path.isdir(existing)
                ):
                    return existing

                # The stock updater replaces the HelixScreen files but leaves
                # this project's marker behind.  A new Turkish release must
                # therefore back up the newly installed stock version, not
                # reuse a backup from the previous release.
                release = read_json(RELEASE_INFO_PATH)
                release_version = str(release.get("version", ""))
                if (
                    release.get("project_owner") != "prestonbrown"
                    or release_version.lstrip("v") != HELIXSCREEN_VERSION
                ):
                    raise RuntimeError(
                        "A superseded Turkish marker exists, but the current "
                        "HelixScreen installation is not the supported stock version"
                    )
                superseded_overlay = str(marker.get("version", "unknown"))
        except RuntimeError:
            raise
        except Exception as error:
            raise RuntimeError("Existing Turkish installation metadata is invalid: {}".format(error))

    if not os.path.isdir(BACKUP_ROOT):
        os.makedirs(BACKUP_ROOT)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup = os.path.join(BACKUP_ROOT, "pre-turkish-{}-{}".format(stamp, os.getpid()))
    snapshot_targets(backup)

    if superseded_overlay:
        # The stale marker and manager belong to the previous Turkish release,
        # not to the newly installed stock HelixScreen.  Treat them as absent
        # so removing this release restores a clean stock installation.
        absent_path = os.path.join(backup, "absent.json")
        absent = read_json(absent_path)
        stale_custom_files = (
            (
                "config/quinry-turkish-package.json",
                os.path.join(backup, os.path.basename(MARKER_PATH)),
            ),
            (
                "config/quinry-turkish-manager.py",
                os.path.join(backup, os.path.basename(MANAGER_PATH)),
            ),
            (
                "ui_xml/translations/tr.xml",
                os.path.join(backup, "files", "ui_xml", "translations", "tr.xml"),
            ),
            (
                "assets/images/flags/flag_tr.bin",
                os.path.join(backup, "files", "assets", "images", "flags", "flag_tr.bin"),
            ),
            (
                "assets/images/flags/flag_tr.png",
                os.path.join(backup, "files", "assets", "images", "flags", "flag_tr.png"),
            ),
        )
        for relative, saved in stale_custom_files:
            if relative not in absent:
                absent.append(relative)
            if os.path.isfile(saved):
                os.unlink(saved)
        with open(absent_path, "w", encoding="utf-8") as handle:
            json.dump(sorted(absent), handle, ensure_ascii=False, indent=2)
            handle.write("\n")

        # The stock updater may leave language=tr even though it removed the
        # Turkish assets.  The clean rollback language is English; all other
        # settings, including touch calibration and CFS data, stay unchanged.
        saved_settings = os.path.join(backup, "settings.json")
        settings = read_json(saved_settings)
        if settings.get("language") == "tr":
            settings["language"] = "en"
            with open(saved_settings, "w", encoding="utf-8") as handle:
                json.dump(settings, handle, ensure_ascii=False, indent=2)
                handle.write("\n")

    manifest = {
        "created": stamp,
        "mode": "overlay",
        "package_version": PACKAGE_VERSION,
        "superseded_overlay": superseded_overlay or None,
        "settings_sha256": sha256_file(os.path.join(backup, "settings.json")),
        "files": {},
    }
    for relative in FILES:
        path = os.path.join(backup, "files", relative.replace("/", os.sep))
        if os.path.isfile(path):
            manifest["files"][relative] = sha256_file(path)
    with open(os.path.join(backup, "manifest.json"), "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    write_atomic(POINTER_PATH, (backup + "\n").encode("utf-8"), 0o600, 0, 0)
    return backup


def settings_with_turkish():
    target = os.path.realpath(SETTINGS_PATH)
    with open(target, "rb") as handle:
        original_bytes = handle.read()
    old = json.loads(original_bytes.decode("utf-8"))
    new = copy.deepcopy(old)
    new["language"] = "tr"
    expected = copy.deepcopy(old)
    expected["language"] = "tr"
    if new != expected:
        raise RuntimeError("Settings would change beyond the language value")
    encoded = (json.dumps(new, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    mode, uid, gid = target_metadata(target, 0o600)
    write_atomic(target, encoded, mode, uid, gid)
    installed = read_json(target)
    if installed != expected:
        raise RuntimeError("Installed settings do not match the validated settings")
    for protected in ("display", "input", "printers"):
        if old.get(protected) != installed.get(protected):
            raise RuntimeError("Protected settings changed: " + protected)


def install_overlay(archive_path, work_dir):
    if not os.path.isfile(SETTINGS_PATH):
        raise RuntimeError("Existing HelixScreen settings.json was not found")
    manifest, payloads, manager_data = load_overlay(archive_path)
    backup_dir = create_original_backup()
    transaction = os.path.join(work_dir, "transaction")
    snapshot_targets(transaction)

    deployment_started = False
    try:
        stop_service()
        deployment_started = True
        for relative, destination in FILES.items():
            default_mode = 0o755 if relative == "bin/helix-screen" else 0o644
            mode, uid, gid = target_metadata(destination, default_mode)
            if relative == "bin/helix-screen":
                mode = 0o755
            write_atomic(destination, payloads[relative], mode, uid, gid)
            if sha256_file(destination) != manifest["files"][relative]["sha256"]:
                raise RuntimeError("Installed file hash mismatch: " + relative)

        settings_with_turkish()
        mode, uid, gid = target_metadata(MANAGER_PATH, 0o700)
        write_atomic(MANAGER_PATH, manager_data, 0o700, uid, gid)
        marker = {
            "repository": "QUINRY/helixscreen-k2-pro-turkce",
            "version": PACKAGE_VERSION,
            "language": "tr",
            "mode": "overlay",
            "backup_dir": backup_dir,
            "installed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
        marker_bytes = (json.dumps(marker, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        write_atomic(MARKER_PATH, marker_bytes, 0o600, 0, 0)
        start_and_verify_service()
    except Exception:
        if deployment_started:
            try:
                restore_snapshot(transaction)
                start_and_verify_service()
            except Exception as rollback_error:
                print("Automatic rollback failed: {}".format(rollback_error), file=sys.stderr)
        raise

    print(json.dumps({"status": "installed", "mode": "overlay", "backup_dir": backup_dir, "version": PACKAGE_VERSION}, ensure_ascii=False))


def remove_overlay():
    marker = read_json(MARKER_PATH)
    if marker.get("mode") != "overlay":
        raise RuntimeError("Installed package is not an overlay installation")
    backup_dir = marker.get("backup_dir", "")
    if not safe_backup_dir(backup_dir) or not os.path.isdir(backup_dir):
        raise RuntimeError("The original HelixScreen backup is missing or unsafe")
    for required in ("settings.json", "absent.json", "manifest.json"):
        if not os.path.isfile(os.path.join(backup_dir, required)):
            raise RuntimeError("Backup is incomplete: " + required)

    transaction = os.path.join(BACKUP_ROOT, "remove-transaction-{}".format(os.getpid()))
    snapshot_targets(transaction)
    try:
        stop_service()
        restore_snapshot(backup_dir)
        start_and_verify_service()
        try:
            if os.path.isfile(POINTER_PATH):
                with open(POINTER_PATH, "r", encoding="utf-8") as handle:
                    if handle.read().strip() == backup_dir:
                        os.unlink(POINTER_PATH)
        except OSError:
            pass
    except Exception:
        try:
            restore_snapshot(transaction)
            start_and_verify_service()
        except Exception as rollback_error:
            print("Automatic rollback failed: {}".format(rollback_error), file=sys.stderr)
        raise
    finally:
        if os.path.isdir(transaction):
            shutil.rmtree(transaction)

    print(json.dumps({"status": "removed", "mode": "overlay", "restored_from": backup_dir}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    install_parser = subparsers.add_parser("install")
    install_parser.add_argument("--archive", required=True)
    install_parser.add_argument("--work-dir", required=True)
    subparsers.add_parser("remove")
    args = parser.parse_args()

    if args.command == "install":
        install_overlay(os.path.abspath(args.archive), os.path.abspath(args.work_dir))
    elif args.command == "remove":
        remove_overlay()
    else:
        parser.error("a command is required")
    return 0


if __name__ == "__main__":
    sys.exit(main())
