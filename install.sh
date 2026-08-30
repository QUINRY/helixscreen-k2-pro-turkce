#!/bin/sh
# Copyright (C) 2026 QUINRY
# SPDX-License-Identifier: GPL-3.0-or-later

# Creality K2 Pro bootstrapper for HelixScreen Turkish. Existing compatible
# installs receive a minimal, reversible overlay; printers without HelixScreen
# receive the complete upstream-based K2 package.

set -eu
export PATH="/usr/sbin:/usr/bin:/sbin:/bin:${PATH:-}"

REPOSITORY="QUINRY/helixscreen-k2-pro-turkce"
PACKAGE_VERSION="v0.99.118-tr.1"
SUPPORTED_HELIX_VERSION="0.99.118"
FULL_NAME="helixscreen-k2.zip"
FULL_SHA256="1b39a6992648a3eae8e519bbdbb327f9ea2c0da38833478e4f0ab288e96990d1"
FULL_URL="https://github.com/${REPOSITORY}/releases/download/${PACKAGE_VERSION}/${FULL_NAME}"
OVERLAY_NAME="helixscreen-k2-tr-overlay.zip"
OVERLAY_SHA256="f223e4de63b5568fcf60c90bc97fe2f3d4b45ff247918204820968b4d1f5eac7"
OVERLAY_URL="https://github.com/${REPOSITORY}/releases/download/${PACKAGE_VERSION}/${OVERLAY_NAME}"
BINARY_SHA256="283c3f81720b24a53ff16485f3f1f2a44e054f047b88f8658fddd131145db269"
WORK_ROOT="/mnt/UDISK/helixscreen-turkish-installer"

ASSUME_YES=false
FORCE_STATE=false
CHECK_ONLY=false
LOCAL_ARCHIVE=""
PYTHON_BIN=""
WORK_DIR=""

say() { printf '%s\n' "$*"; }
info() { printf '[i] %s\n' "$*"; }
ok() { printf '[✓] %s\n' "$*"; }
warn() { printf '[!] %s\n' "$*" >&2; }
die() { printf '[x] %s\n' "$*" >&2; exit 1; }

usage() {
    cat <<'EOF'
HelixScreen Türkçe - Creality K2 Pro kurucusu

Kullanım:
  sh install.sh [--yes] [--check] [--force-print-state]
  sh install.sh --local /mnt/UDISK/PAKET.zip [--yes]

Seçenekler:
  --yes, -y             Onayı etkileşimsiz ver
  --check               Sistemi denetle, değişiklik yapma
  --local DOSYA         GitHub yerine uygun yerel ZIP paketini kullan
  --force-print-state   Moonraker durumu okunamasa da devam et
  --help, -h            Bu yardımı göster
EOF
}

cleanup() {
    [ -n "$WORK_DIR" ] || return 0
    case "$WORK_DIR" in
        "$WORK_ROOT"/run-*) rm -rf "$WORK_DIR" ;;
        *) warn "Güvensiz geçici yol temizlenmedi: $WORK_DIR" ;;
    esac
}
trap cleanup EXIT INT TERM

while [ "$#" -gt 0 ]; do
    case "$1" in
        --yes|-y) ASSUME_YES=true; shift ;;
        --check) CHECK_ONLY=true; shift ;;
        --force-print-state) FORCE_STATE=true; shift ;;
        --local)
            [ "$#" -ge 2 ] || die "--local bir dosya yolu gerektirir"
            LOCAL_ARCHIVE=$2
            shift 2
            ;;
        --help|-h) usage; exit 0 ;;
        *) die "Bilinmeyen seçenek: $1" ;;
    esac
done

[ "$(id -u)" = "0" ] || die "Kurucuyu root hesabıyla çalıştırın"
[ -d /mnt/UDISK ] || die "Bu cihaz Creality K2 serisi gibi görünmüyor (/mnt/UDISK yok)"
[ "$(uname -m)" = "armv7l" ] || die "Desteklenmeyen mimari: $(uname -m) (beklenen: armv7l)"
if ! { [ -d /mnt/UDISK/printer_data ] || grep -Eqi 'openwrt|tina' /etc/os-release 2>/dev/null; }; then
    die "K2 Pro platform doğrulaması başarısız"
fi

for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 && \
       "$candidate" -c 'import hashlib,json,urllib.request,zipfile' >/dev/null 2>&1; then
        PYTHON_BIN=$candidate
        break
    fi
done
[ -n "$PYTHON_BIN" ] || die "Python (json/urllib/zipfile) bulunamadı"

get_print_state() {
    "$PYTHON_BIN" - <<'PY'
import json
import sys
import urllib.request
try:
    with urllib.request.urlopen(
        "http://127.0.0.1:7125/printer/objects/query?print_stats", timeout=5
    ) as response:
        payload = json.load(response)
    print(payload["result"]["status"]["print_stats"]["state"])
except Exception:
    sys.exit(1)
PY
}

PRINT_STATE=$(get_print_state 2>/dev/null || true)
case "$PRINT_STATE" in
    printing|paused) die "Yazıcı şu anda ${PRINT_STATE}; kurulum reddedildi" ;;
    standby|complete|cancelled|error) info "Baskı durumu: $PRINT_STATE" ;;
    *)
        if [ "$FORCE_STATE" = true ]; then
            warn "Moonraker baskı durumu okunamadı; --force-print-state ile devam ediliyor"
        else
            die "Moonraker baskı durumu okunamadı. Sorunu giderin veya bilinçli olarak --force-print-state kullanın"
        fi
        ;;
esac

MODE=fresh
PACKAGE_NAME=$FULL_NAME
PACKAGE_SHA256=$FULL_SHA256
DOWNLOAD_URL=$FULL_URL
if [ -x /opt/helixscreen/bin/helix-screen ]; then
    MODE=overlay
    PACKAGE_NAME=$OVERLAY_NAME
    PACKAGE_SHA256=$OVERLAY_SHA256
    DOWNLOAD_URL=$OVERLAY_URL
    INSTALLED_VERSION=$("$PYTHON_BIN" - <<'PY' 2>/dev/null || true
import json
try:
    with open("/opt/helixscreen/release_info.json", encoding="utf-8") as handle:
        print(json.load(handle).get("version", ""))
except Exception:
    pass
PY
    )
    if [ -z "$INSTALLED_VERSION" ]; then
        INSTALLED_VERSION=$(/opt/helixscreen/bin/helix-screen --version 2>/dev/null | head -n 1 || true)
    fi
    case "$INSTALLED_VERSION" in
        *"$SUPPORTED_HELIX_VERSION"*) ;;
        *) die "Mevcut HelixScreen sürümü uyumlu değil: ${INSTALLED_VERSION:-bilinmiyor}. Desteklenen: ${SUPPORTED_HELIX_VERSION}" ;;
    esac
fi

if [ "$CHECK_ONLY" = true ]; then
    say ""
    ok "K2 Pro platform kontrolü geçti"
    ok "Python ve Moonraker erişimi hazır"
    if [ "$MODE" = overlay ]; then
        info "Mod: ayarları koruyan Türkçe katman (${INSTALLED_VERSION})"
    else
        info "Mod: yeni tam HelixScreen Türkçe kurulumu"
    fi
    exit 0
fi

if [ "$ASSUME_YES" != true ]; then
    if [ -t 0 ]; then
        say ""
        if [ "$MODE" = overlay ]; then
            say "Mevcut HelixScreen'e geri alınabilir Türkçe katman uygulanacak."
        else
            say "HelixScreen ${PACKAGE_VERSION} Türkçe paketi ilk kez kurulacak."
        fi
        printf 'Devam edilsin mi? [e/H] '
        read -r answer
        case "$answer" in e|E|evet|EVET) ;; *) die "Kurulum iptal edildi" ;; esac
    else
        die "Etkileşimsiz kullanımda --yes gereklidir"
    fi
fi

mkdir -p "$WORK_ROOT"
WORK_DIR="${WORK_ROOT}/run-$$"
mkdir "$WORK_DIR"

download_file() {
    url=$1
    destination=$2
    if command -v curl >/dev/null 2>&1 && curl --version >/dev/null 2>&1; then
        if curl -fL --retry 3 --connect-timeout 20 --max-time 600 -o "$destination" "$url"; then
            return 0
        fi
        rm -f "$destination"
    fi
    if command -v wget >/dev/null 2>&1; then
        if wget -O "$destination" "$url"; then
            return 0
        fi
        rm -f "$destination"
    fi
    "$PYTHON_BIN" - "$url" "$destination" <<'PY'
import shutil
import sys
import urllib.request
request = urllib.request.Request(
    sys.argv[1], headers={"User-Agent": "helixscreen-k2-pro-turkce-installer"}
)
with urllib.request.urlopen(request, timeout=600) as response:
    with open(sys.argv[2], "wb") as output:
        shutil.copyfileobj(response, output, length=1024 * 1024)
PY
}

sha256_file() {
    file=$1
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$file" | awk '{print $1}'
    else
        "$PYTHON_BIN" - "$file" <<'PY'
import hashlib
import sys
digest = hashlib.sha256()
with open(sys.argv[1], "rb") as handle:
    for block in iter(lambda: handle.read(1024 * 1024), b""):
        digest.update(block)
print(digest.hexdigest())
PY
    fi
}

if [ -n "$LOCAL_ARCHIVE" ]; then
    [ -f "$LOCAL_ARCHIVE" ] || die "Yerel paket bulunamadı: $LOCAL_ARCHIVE"
    ARCHIVE=$LOCAL_ARCHIVE
    info "Yerel paket kullanılacak: $ARCHIVE"
else
    ARCHIVE="${WORK_DIR}/${PACKAGE_NAME}"
    info "Paket indiriliyor: ${DOWNLOAD_URL}"
    download_file "$DOWNLOAD_URL" "$ARCHIVE" || die "Paket indirilemedi"
fi

ACTUAL_SHA256=$(sha256_file "$ARCHIVE")
[ "$ACTUAL_SHA256" = "$PACKAGE_SHA256" ] || die "Paket SHA256 doğrulaması başarısız (gelen: $ACTUAL_SHA256)"
ok "Paket SHA256 doğrulandı"

if [ "$MODE" = overlay ]; then
    MANAGER="${WORK_DIR}/k2_turkish_overlay.py"
    "$PYTHON_BIN" - "$ARCHIVE" "$MANAGER" <<'PY'
import os
import sys
import zipfile
with zipfile.ZipFile(sys.argv[1], "r") as archive:
    bad = archive.testzip()
    if bad is not None:
        raise SystemExit("ZIP CRC hatası: " + bad)
    data = archive.read("installer/k2_turkish_overlay.py")
with open(sys.argv[2], "wb") as output:
    output.write(data)
os.chmod(sys.argv[2], 0o700)
PY
    info "Mevcut HelixScreen ayarları korunarak Türkçe katman uygulanıyor..."
    "$PYTHON_BIN" "$MANAGER" install --archive "$ARCHIVE" --work-dir "$WORK_DIR"
else
    BASE_INSTALLER="${WORK_DIR}/upstream-install.sh"
    "$PYTHON_BIN" - "$ARCHIVE" "$BASE_INSTALLER" <<'PY'
import os
import sys
import zipfile
with zipfile.ZipFile(sys.argv[1], "r") as archive:
    bad = archive.testzip()
    if bad is not None:
        raise SystemExit("ZIP CRC hatası: " + bad)
    data = archive.read("install.sh")
with open(sys.argv[2], "wb") as output:
    output.write(data)
os.chmod(sys.argv[2], 0o755)
PY
    info "HelixScreen ilk kez kuruluyor..."
    sh "$BASE_INSTALLER" --local "$ARCHIVE" --yes
    "$PYTHON_BIN" - <<'PY'
import json
import os
import stat
import time
configured = "/opt/helixscreen/config/settings.json"
target = os.path.realpath(configured)
with open(target, "r", encoding="utf-8") as handle:
    settings = json.load(handle)
settings["language"] = "tr"
metadata = os.stat(target)
temporary = target + ".turkish-new"
with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
    json.dump(settings, handle, ensure_ascii=False, indent=2)
    handle.write("\n")
os.chmod(temporary, stat.S_IMODE(metadata.st_mode))
try:
    os.chown(temporary, metadata.st_uid, metadata.st_gid)
except PermissionError:
    pass
os.replace(temporary, target)
marker = {
    "repository": "QUINRY/helixscreen-k2-pro-turkce",
    "version": "v0.99.118-tr.1",
    "language": "tr",
    "mode": "fresh",
    "installed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
}
marker_path = "/opt/helixscreen/config/quinry-turkish-package.json"
with open(marker_path + ".new", "w", encoding="utf-8") as handle:
    json.dump(marker, handle, ensure_ascii=False, indent=2)
    handle.write("\n")
os.replace(marker_path + ".new", marker_path)
PY
    /etc/init.d/helixscreen stop >/dev/null 2>&1 || true
    sleep 2
    rm -f /tmp/helix-screen.lock
    /etc/init.d/helixscreen start
    sleep 8
fi

[ -x /opt/helixscreen/bin/helix-screen ] || die "HelixScreen ikilisi kurulamadı"
[ "$(sha256_file /opt/helixscreen/bin/helix-screen)" = "$BINARY_SHA256" ] || die "Kurulu HelixScreen ikilisi beklenen sürüm değil"
[ -f /opt/helixscreen/ui_xml/translations/tr.xml ] || die "Türkçe çeviri dosyası eksik"
pidof helix-screen >/dev/null 2>&1 || ps w | grep '[h]elix-screen' >/dev/null 2>&1 || die "HelixScreen başlatılamadı"

LANGUAGE=$("$PYTHON_BIN" - <<'PY'
import json
with open("/opt/helixscreen/config/settings.json", encoding="utf-8") as handle:
    print(json.load(handle).get("language", ""))
PY
)
[ "$LANGUAGE" = "tr" ] || die "Türkçe dili etkinleştirilemedi"

say ""
ok "HelixScreen Türkçe ${PACKAGE_VERSION} kuruldu"
ok "Türkçe seçildi ve servis çalışıyor"
info "Kurulum modu: $MODE"
info "Kaldırma: https://github.com/${REPOSITORY}#kaldırma"
