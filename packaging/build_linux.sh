#!/usr/bin/env bash
# Baut aus dem PyInstaller-Bundle: .tar.gz, AppImage, .deb, .rpm.
# Voraussetzungen: pyinstaller (pip install -e ".[build]"), appimagetool im PATH,
# fpm (gem install fpm) im PATH.
set -euo pipefail
cd "$(dirname "$0")/.."

# Lokal existiert eine .venv, in CI installieren wir direkt in die System-/Runner-Umgebung.
PYTHON=python3
PYINSTALLER=pyinstaller
if [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
  PYINSTALLER=".venv/bin/pyinstaller"
fi

VERSION=$("$PYTHON" -c "from scanner_app import __version__; print(__version__)")
ARCH=$(uname -m)
DIST=dist
PKGROOT=packaging
ICON_PNG=src/scanner_app/resources/icon.png
OUT=dist/packages
mkdir -p "$OUT"

echo "== PyInstaller-Bundle bauen (v$VERSION) =="
rm -rf build "$DIST/Scanner"

# OCR-Programme (tesseract/qpdf/ghostscript) mitbündeln, damit OCR ohne manuelle
# System-Installation funktioniert — siehe ocr_engine.py::_ensure_bundled_tools_available().
# MUSS nach dem "rm -rf build" oben stehen, sonst löscht das den gerade befüllten Ordner
# wieder. build/ocr-tools landet über packaging/scanner.spec identisch in
# tar.gz/AppImage/deb/rpm, da alle vier aus demselben dist/Scanner-Onedir-Build entstehen.
echo "== OCR-Werkzeuge bündeln (tesseract/qpdf/ghostscript) =="
OCR_TOOLS_DIR="build/ocr-tools"
mkdir -p "$OCR_TOOLS_DIR"

_copy_with_shared_libs() {
  local tool="$1"
  local real
  real=$(command -v "$tool") || { echo "  WARNUNG: $tool nicht gefunden, wird übersprungen"; return; }
  real=$(readlink -f "$real")
  cp -L "$real" "$OCR_TOOLS_DIR/$tool"
  # ldd liefert bereits die volle transitive Abhängigkeitsliste, kein rekursives Auflösen
  # nötig. Basis-Systembibliotheken (libc, ld-linux, ...) bewusst NICHT mitkopieren — die
  # dürfen/sollen vom jeweiligen Host-System kommen (ABI-Kompatibilität über Distros hinweg
  # ist für genau diese Low-Level-Libs am ehesten gegeben; ein starres Mitkopieren würde bei
  # abweichender libc-Version eher schaden als nützen).
  ldd "$real" 2>/dev/null | awk '{print $3}' | grep '^/' | while read -r lib; do
    base=$(basename "$lib")
    case "$base" in
      libc.so*|libm.so*|libpthread.so*|libdl.so*|ld-linux*|librt.so*|libresolv.so*|libutil.so*|libgcc_s.so*|libnsl.so*)
        continue ;;
    esac
    [ -f "$OCR_TOOLS_DIR/$base" ] || cp -L "$lib" "$OCR_TOOLS_DIR/$base"
  done
}

for tool in tesseract qpdf gs; do
  _copy_with_shared_libs "$tool"
done

# rpath auf $ORIGIN setzen: die kopierten Programme/Bibliotheken finden sich damit
# gegenseitig unabhängig vom Installationsort, ohne dass die App zur Laufzeit
# LD_LIBRARY_PATH manipulieren muss.
find "$OCR_TOOLS_DIR" -type f \( -name '*.so*' -o -perm -u+x \) -print0 2>/dev/null \
  | while IFS= read -r -d '' f; do
      patchelf --set-rpath '$ORIGIN' "$f" 2>/dev/null || true
    done
echo "  -> $(find "$OCR_TOOLS_DIR" -maxdepth 1 -type f | wc -l) Dateien in $OCR_TOOLS_DIR"

QT_QPA_PLATFORM=offscreen "$PYINSTALLER" packaging/scanner.spec --distpath "$DIST" --workpath build --noconfirm

echo "== .tar.gz =="
TARDIR="$DIST/scanner-$VERSION-linux-$ARCH"
rm -rf "$TARDIR"
mkdir -p "$TARDIR"
cp -r "$DIST/Scanner" "$TARDIR/"
cp "$PKGROOT/scanner-installed.desktop" "$TARDIR/scanner.desktop"
cp "$ICON_PNG" "$TARDIR/"
tar -C "$DIST" -czf "$OUT/scanner-$VERSION-linux-$ARCH.tar.gz" "scanner-$VERSION-linux-$ARCH"
rm -rf "$TARDIR"
echo "  -> $OUT/scanner-$VERSION-linux-$ARCH.tar.gz"

echo "== AppImage =="
APPDIR="$DIST/AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
cp -r "$DIST/Scanner"/* "$APPDIR/usr/bin/"
cp "$PKGROOT/scanner.desktop" "$APPDIR/"
cp "$ICON_PNG" "$APPDIR/scanner.png"
cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "${0}")")"
exec "${HERE}/usr/bin/Scanner" "$@"
EOF
chmod +x "$APPDIR/AppRun"
ARCH="$ARCH" appimagetool "$APPDIR" "$OUT/Scanner-$VERSION-$ARCH.AppImage" 2>&1 | grep -v "^$" || true
echo "  -> $OUT/Scanner-$VERSION-$ARCH.AppImage"

FPM="fpm"
if ! command -v fpm >/dev/null 2>&1; then
  FPM=$(find "$HOME/.local/share/gem" -maxdepth 4 -name fpm -type f 2>/dev/null | head -1)
fi

echo "== .deb =="
"$FPM" -s dir -t deb -n scanner -v "$VERSION" \
  --description "Plattformübergreifende Dokumentenscanner-App mit OCR" \
  --url "https://github.com/CtrlCup/scanner" \
  --license "Proprietary" \
  --maintainer "Alex Klauser" \
  --package "$OUT/scanner_${VERSION}_amd64.deb" \
  --force \
  "$DIST/Scanner/=/opt/scanner" \
  "$PKGROOT/scanner-installed.desktop=/usr/share/applications/scanner.desktop" \
  "$ICON_PNG=/usr/share/icons/hicolor/512x512/apps/scanner.png"
echo "  -> $OUT/scanner_${VERSION}_amd64.deb"

echo "== .rpm =="
"$FPM" -s dir -t rpm -n scanner -v "$VERSION" \
  --description "Plattformübergreifende Dokumentenscanner-App mit OCR" \
  --url "https://github.com/CtrlCup/scanner" \
  --license "Proprietary" \
  --maintainer "Alex Klauser" \
  --package "$OUT/scanner-${VERSION}-1.x86_64.rpm" \
  --force \
  "$DIST/Scanner/=/opt/scanner" \
  "$PKGROOT/scanner-installed.desktop=/usr/share/applications/scanner.desktop" \
  "$ICON_PNG=/usr/share/icons/hicolor/512x512/apps/scanner.png"
echo "  -> $OUT/scanner-${VERSION}-1.x86_64.rpm"

echo
echo "Fertig. Pakete in $OUT/:"
ls -la "$OUT"
