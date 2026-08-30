#!/usr/bin/env python3
"""Build the minimal, settings-preserving Turkish overlay for K2 Pro."""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path
from xml.etree import ElementTree


PACKAGE_VERSION = "v0.99.118-tr.1"
HELIXSCREEN_VERSION = "0.99.118"
EXPECTED_TRANSLATION_COUNT = 2855
EXPECTED_BINARY_SHA256 = (
    "283c3f81720b24a53ff16485f3f1f2a44e054f047b88f8658fddd131145db269"
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def add_file(
    archive: zipfile.ZipFile, name: str, data: bytes, mode: int = 0o644
) -> None:
    info = zipfile.ZipInfo(name, (2026, 8, 30, 0, 0, 0))
    info.create_system = 3
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = (stat.S_IFREG | mode) << 16
    archive.writestr(
        info,
        data,
        compress_type=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    )


def build(source: Path, binary: Path, output: Path) -> dict[str, object]:
    files = {
        "bin/helix-screen": binary,
        "installer/k2_turkish_overlay.py": (
            source / "installer/k2_turkish_overlay.py"
        ),
        "release_info.json": source / "packaging/k2/release_info.json",
        "ui_xml/translations/tr.xml": source / "ui_xml/translations/tr.xml",
        "ui_xml/translations/translations.xml": (
            source / "ui_xml/translations/translations.xml"
        ),
        "ui_xml/wizard_language_chooser.xml": (
            source / "ui_xml/wizard_language_chooser.xml"
        ),
        "assets/images/flags/flag_tr.bin": (
            source / "assets/images/flags/flag_tr.bin"
        ),
        "assets/images/flags/flag_tr.png": (
            source / "assets/images/flags/flag_tr.png"
        ),
    }
    missing = [str(path) for path in files.values() if not path.is_file()]
    if missing:
        raise SystemExit("Missing overlay inputs:\n" + "\n".join(missing))

    payloads = {name: path.read_bytes() for name, path in files.items()}
    binary_hash = sha256(payloads["bin/helix-screen"])
    if binary_hash != EXPECTED_BINARY_SHA256:
        raise SystemExit(f"Unexpected K2 binary SHA256: {binary_hash}")

    root = ElementTree.fromstring(
        payloads["ui_xml/translations/tr.xml"].decode("utf-8")
    )
    entry_count = len(root.findall("translation"))
    if entry_count != EXPECTED_TRANSLATION_COUNT:
        raise SystemExit(f"Unexpected Turkish translation count: {entry_count}")

    manifest = {
        "name": "HelixScreen Türkçe K2 Pro overlay",
        "package_version": PACKAGE_VERSION,
        "helixscreen_version": HELIXSCREEN_VERSION,
        "platform": "k2",
        "language": "tr",
        "translation_entries": entry_count,
        "files": {
            name: {
                "sha256": sha256(data),
                "mode": "0755"
                if name in {"bin/helix-screen", "installer/k2_turkish_overlay.py"}
                else "0644",
            }
            for name, data in sorted(payloads.items())
        },
        "repository": "https://github.com/QUINRY/helixscreen-k2-pro-turkce",
        "license": "GPL-3.0-or-later",
    }
    manifest_bytes = (
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        add_file(archive, "manifest.json", manifest_bytes)
        for name, data in sorted(payloads.items()):
            executable = name in {
                "bin/helix-screen",
                "installer/k2_turkish_overlay.py",
            }
            add_file(archive, name, data, 0o755 if executable else 0o644)

    with zipfile.ZipFile(output, "r") as archive:
        bad = archive.testzip()
        if bad is not None:
            raise SystemExit(f"Overlay ZIP CRC validation failed at: {bad}")
        if set(archive.namelist()) != {"manifest.json", *files.keys()}:
            raise SystemExit("Overlay ZIP member list is not exact")
        archived_manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        for name, metadata in archived_manifest["files"].items():
            if sha256(archive.read(name)) != metadata["sha256"]:
                raise SystemExit(f"Overlay member hash mismatch: {name}")

    return {
        "output": str(output.resolve()),
        "bytes": output.stat().st_size,
        "sha256": sha256(output.read_bytes()),
        "translation_entries": entry_count,
        "binary_sha256": binary_hash,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.source.resolve(), args.binary.resolve(), args.output.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
