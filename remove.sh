#!/bin/sh
# Copyright (C) 2026 QUINRY
# SPDX-License-Identifier: GPL-3.0-or-later

# Remove only the Turkish overlay when it was added to an existing HelixScreen.
# For a fresh installation made by this project, use the upstream uninstaller
# shipped in the release and restore the stock Creality UI.

set -eu

export PATH="/usr/sbin:/usr/bin:/sbin:/bin:${PATH:-}"

WORK_ROOT="/mnt/UDISK/helixscreen-turkish-installer"
ASSUME_YES=false
FORCE_STATE=false
CHECK_ONLY=false
WORK_DIR=""
PYTHON_BIN=""

say() { printf '%s\n' "$*"; }
info() { printf '[i] %s\n' "$*"; }
ok() { printf '[✓] %s\n' "$*"; }
warn() { printf '[!] %s\n' "$*" >&2; }
die() { printf '[x] %s\n' "$*" >&2; exit 1; }

usage() {
    cat <<'EOF'
HelixScreen Türkçe - Creality K2 Pro kaldırıcı

Kullanım:
  sh remove.sh [--yes] [--check] [--force-print-state]

Mevcut HelixScreen Türkçeleştirildiyse yalnız Türkçe katman kaldırılır.
HelixScreen bu proje ile sıfırdan kurulduysa stok Creality ekranı geri yüklenir.
EOF
}

cleanup() {
    [ -n "$WORK_DIR" ] || return 0
    case "$WORK_DIR" in
        "$WORK_ROOT"/remove-*) rm -rf "$WORK_DIR" ;;
        *) warn "Güvensiz geçici yol temizlenmedi: $WORK_DIR" ;;
    esac
}
trap cleanup EXIT INT TERM

while [ "$#" -gt 0 ]; do
    case "$1" in
        --yes|-y) ASSUME_YES=true; shift ;;
        --check) CHECK_ONLY=true; shift ;;
        --force-print-state) FORCE_STATE=true; shift ;;
        --help|-h) usage; exit 0 ;;
        *) die "Bilinmeyen seçenek: $1" ;;
    esac
done

[ "$(id -u)" = "0" ] || die "Kaldırıcıyı root hesabıyla çalıştırın"
[ -d /mnt/UDISK ] || die "Bu cihaz Creality K2 serisi gibi görünmüyor"
[ "$(uname -m)" = "armv7l" ] || die "Desteklenmeyen mimari: $(uname -m)"

for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 && \
       "$candidate" -c 'import json,urllib.request' >/dev/null 2>&1; then
        PYTHON_BIN=$candidate
        break
    fi
done
[ -n "$PYTHON_BIN" ] || die "Python bulunamadı"

PRINT_STATE=$("$PYTHON_BIN" - <<'PY' 2>/dev/null || true
import json
import urllib.request
with urllib.request.urlopen(
    "http://127.0.0.1:7125/printer/objects/query?print_stats", timeout=5
) as response:
    payload = json.load(response)
print(payload["result"]["status"]["print_stats"]["state"])
PY
)

case "$PRINT_STATE" in
    printing|paused) die "Yazıcı şu anda ${PRINT_STATE}; kaldırma reddedildi" ;;
    standby|complete|cancelled|error) info "Baskı durumu: $PRINT_STATE" ;;
    *)
        [ "$FORCE_STATE" = true ] || \
            die "Moonraker baskı durumu okunamadı; gerekirse --force-print-state kullanın"
        warn "Baskı durumu doğrulanmadan devam edilecek"
        ;;
esac

if [ ! -d /opt/helixscreen ]; then
    ok "HelixScreen zaten kurulu değil"
    exit 0
fi

REMOVE_MODE=full
MARKER_MODE=$("$PYTHON_BIN" - <<'PY' 2>/dev/null || true
import json
try:
    with open("/opt/helixscreen/config/quinry-turkish-package.json", encoding="utf-8") as handle:
        print(json.load(handle).get("mode", ""))
except Exception:
    pass
PY
)
if [ "$MARKER_MODE" = overlay ]; then
    [ -f /opt/helixscreen/config/quinry-turkish-manager.py ] || \
        die "Türkçe katman yöneticisi eksik; güvenli geri yükleme yapılamadı"
    REMOVE_MODE=overlay
fi

if [ "$CHECK_ONLY" = true ]; then
    ok "K2 Pro platform kontrolü geçti"
    if [ "$REMOVE_MODE" = overlay ]; then
        ok "Türkçe katman kaldırılabilir; mevcut HelixScreen korunacak"
    else
        ok "HelixScreen kaldırılabilir; stok Creality arayüzü geri yüklenecek"
    fi
    exit 0
fi

if [ "$ASSUME_YES" != true ]; then
    if [ -t 0 ]; then
        say ""
        if [ "$REMOVE_MODE" = overlay ]; then
            warn "Türkçe katman kaldırılacak; önceki HelixScreen geri yüklenecek."
        else
            warn "HelixScreen kaldırılacak ve stok Creality arayüzü geri yüklenecek."
        fi
        printf 'Devam edilsin mi? [e/H] '
        read -r answer
        case "$answer" in e|E|evet|EVET) ;; *) die "Kaldırma iptal edildi" ;; esac
    else
        die "Etkileşimsiz kullanımda --yes gereklidir"
    fi
fi

mkdir -p "$WORK_ROOT"
WORK_DIR="${WORK_ROOT}/remove-$$"
mkdir "$WORK_DIR"

if [ "$REMOVE_MODE" = overlay ]; then
    cp /opt/helixscreen/config/quinry-turkish-manager.py "$WORK_DIR/manager.py"
    chmod 700 "$WORK_DIR/manager.py"
    info "Türkçe katman kaldırılıyor; önceki HelixScreen geri yükleniyor..."
    "$PYTHON_BIN" "$WORK_DIR/manager.py" remove
elif [ -f /opt/helixscreen/install.sh ]; then
    cp /opt/helixscreen/install.sh "$WORK_DIR/install.sh"
    chmod 755 "$WORK_DIR/install.sh"
    info "Resmî HelixScreen kaldırıcı çalıştırılıyor..."
    sh "$WORK_DIR/install.sh" --uninstall --yes
elif [ -f /opt/helixscreen/scripts/uninstall.sh ]; then
    cp /opt/helixscreen/scripts/uninstall.sh "$WORK_DIR/uninstall.sh"
    chmod 755 "$WORK_DIR/uninstall.sh"
    info "Bağımsız HelixScreen kaldırıcı çalıştırılıyor..."
    sh "$WORK_DIR/uninstall.sh" --force
else
    die "Kurulu HelixScreen kaldırma betiği bulunamadı; otomatik silme yapılmadı"
fi

say ""
if [ "$REMOVE_MODE" = overlay ]; then
    [ -d /opt/helixscreen ] || die "Önceki HelixScreen geri yüklenemedi"
    ok "Türkçe katman kaldırıldı; önceki HelixScreen geri yüklendi"
else
    [ ! -d /opt/helixscreen ] || die "HelixScreen klasörü kaldırılamadı"
    ok "HelixScreen kaldırıldı"
    info "Stok Creality arayüzünün temiz başlaması için yazıcıyı yeniden başlatın"
fi
