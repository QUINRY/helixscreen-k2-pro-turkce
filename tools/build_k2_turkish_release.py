#!/usr/bin/env python3
"""Build the K2 Pro Turkish release from an official HelixScreen K2 ZIP.

The official archive remains the base so its platform hooks, camera service,
launcher, and uninstaller stay byte-for-byte unchanged.  Only the files listed
in REPLACEMENTS are replaced, and the Turkish package metadata is added.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree


REPLACEMENTS = {
    "bin/helix-screen": "bin/helix-screen",
    "config/settings.json": "config/settings.json",
    "install.sh": "install.sh",
    "release_info.json": "release_info.json",
    "scripts/uninstall.sh": "scripts/uninstall.sh",
    "ui_xml/translations/tr.xml": "ui_xml/translations/tr.xml",
    "ui_xml/translations/translations.xml": "ui_xml/translations/translations.xml",
    "ui_xml/wizard_language_chooser.xml": "ui_xml/wizard_language_chooser.xml",
    "assets/images/flags/flag_tr.bin": "assets/images/flags/flag_tr.bin",
    "assets/images/flags/flag_tr.png": "assets/images/flags/flag_tr.png",
    "TURKISH_PACKAGE.json": "TURKISH_PACKAGE.json",
}

EXECUTABLES = {
    "bin/helix-screen",
    "install.sh",
    "scripts/uninstall.sh",
}

EXPECTED_BINARY_SHA256 = (
    "141405d9580e68a660a038ec07e4a81d130b28b869f3fef19347b6bf7122e2d6"
)
EXPECTED_TRANSLATION_COUNT = 2851


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_member(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(name) and not path.is_absolute() and ".." not in path.parts


def replacement_info(name: str, template: zipfile.ZipInfo | None) -> zipfile.ZipInfo:
    if template is not None:
        info = zipfile.ZipInfo(name, template.date_time)
        info.comment = template.comment
        info.create_system = template.create_system
        info.create_version = template.create_version
        info.extract_version = template.extract_version
        info.flag_bits = template.flag_bits
        info.internal_attr = template.internal_attr
        info.external_attr = template.external_attr
        info.extra = template.extra
    else:
        info = zipfile.ZipInfo(name, (2026, 8, 29, 0, 0, 0))
        info.create_system = 3

    mode = 0o755 if name in EXECUTABLES else 0o644
    info.external_attr = (stat.S_IFREG | mode) << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    return info


def validate_staging(staging: Path) -> dict[str, bytes]:
    payloads: dict[str, bytes] = {}
    for archive_name, relative_path in REPLACEMENTS.items():
        source = staging / relative_path
        if not source.is_file():
            raise SystemExit(f"Missing staged file: {source}")
        payloads[archive_name] = source.read_bytes()

    binary_hash = sha256(payloads["bin/helix-screen"])
    if binary_hash != EXPECTED_BINARY_SHA256:
        raise SystemExit(
            f"Unexpected helix-screen SHA256: {binary_hash} "
            f"(expected {EXPECTED_BINARY_SHA256})"
        )

    settings = json.loads(payloads["config/settings.json"].decode("utf-8"))
    if settings.get("language") != "tr" or settings.get("preset") != "k2":
        raise SystemExit("Staged K2 settings must select language=tr and preset=k2")

    translations = ElementTree.fromstring(
        payloads["ui_xml/translations/tr.xml"].decode("utf-8")
    )
    count = len(translations.findall("translation"))
    if count != EXPECTED_TRANSLATION_COUNT:
        raise SystemExit(
            f"Unexpected Turkish translation count: {count} "
            f"(expected {EXPECTED_TRANSLATION_COUNT})"
        )

    return payloads


def build(source_zip: Path, staging: Path, output_zip: Path) -> dict[str, object]:
    payloads = validate_staging(staging)
    output_zip.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(source_zip, "r") as source:
        if source.testzip() is not None:
            raise SystemExit("The official source ZIP failed its CRC check")

        infos = source.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            raise SystemExit("The official source ZIP contains duplicate members")
        if any(not safe_member(name) for name in names):
            raise SystemExit("The official source ZIP contains an unsafe member path")

        templates = {info.filename: info for info in infos}
        with zipfile.ZipFile(
            output_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as output:
            for info in infos:
                name = info.filename
                if name in payloads:
                    output.writestr(
                        replacement_info(name, info),
                        payloads.pop(name),
                        compress_type=zipfile.ZIP_DEFLATED,
                        compresslevel=9,
                    )
                else:
                    output.writestr(info, source.read(info))

            for name in sorted(payloads):
                output.writestr(
                    replacement_info(name, templates.get(name)),
                    payloads[name],
                    compress_type=zipfile.ZIP_DEFLATED,
                    compresslevel=9,
                )

    with zipfile.ZipFile(output_zip, "r") as built:
        bad_member = built.testzip()
        if bad_member is not None:
            raise SystemExit(f"Built ZIP failed CRC validation at: {bad_member}")
        built_names = set(built.namelist())
        missing = sorted(set(REPLACEMENTS) - built_names)
        if missing:
            raise SystemExit(f"Built ZIP is missing files: {', '.join(missing)}")
        if sha256(built.read("bin/helix-screen")) != EXPECTED_BINARY_SHA256:
            raise SystemExit("Built ZIP contains the wrong helix-screen binary")

    result = {
        "output": str(output_zip.resolve()),
        "bytes": output_zip.stat().st_size,
        "sha256": sha256(output_zip.read_bytes()),
        "translation_entries": EXPECTED_TRANSLATION_COUNT,
        "binary_sha256": EXPECTED_BINARY_SHA256,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--official-zip", type=Path, required=True)
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    result = build(
        args.official_zip.resolve(), args.staging.resolve(), args.output.resolve()
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
