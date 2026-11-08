#!/bin/bash
# Genera dist/<App>.app y dist/<App>-<versión>.dmg. Uso: bash empaquetado/compilar_mac.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PY:-venv/bin/python}
NOMBRE=$($PY -c "from nucleo.config import NOMBRE_APP; print(NOMBRE_APP)")
VERSION=$($PY -c "from nucleo.config import VERSION; print(VERSION)")

$PY empaquetado/icono.py
rm -rf build "dist/$NOMBRE" "dist/$NOMBRE.app"
$PY -m PyInstaller empaquetado/app.spec --noconfirm --distpath dist --workpath build

# Firma "ad hoc" (gratis): sin ella, macOS en chips Apple a veces no deja abrirla.
# No sustituye a la firma de Apple Developer (99 $/año): el primer arranque pedirá permiso.
codesign --force --deep --sign - "dist/$NOMBRE.app"

# .dmg con el típico "arrastra la app a Aplicaciones"
PREP=$(mktemp -d)
cp -R "dist/$NOMBRE.app" "$PREP/"
ln -s /Applications "$PREP/Aplicaciones"
rm -f "dist/$NOMBRE-$VERSION.dmg"
hdiutil create -volname "$NOMBRE" -srcfolder "$PREP" -ov -format UDZO "dist/$NOMBRE-$VERSION.dmg" >/dev/null
rm -rf "$PREP"
du -sh "dist/$NOMBRE.app" "dist/$NOMBRE-$VERSION.dmg"
