#!/bin/sh
# Install Breathe as a `breathe` command and a desktop launcher entry.
# Usage: ./install.sh              (per-user, into ~/.local)
#        sudo PREFIX=/usr/local ./install.sh   (system-wide)
#        ./install.sh --uninstall
set -e

PREFIX="${PREFIX:-$HOME/.local}"
SRC="$(cd "$(dirname "$0")" && pwd)/breathing.py"
BIN="$PREFIX/bin/breathe"
DESKTOP="$PREFIX/share/applications/breathe.desktop"

if [ "$1" = "--uninstall" ]; then
    rm -f "$BIN" "$DESKTOP"
    echo "Removed $BIN and $DESKTOP"
    exit 0
fi

chmod +x "$SRC"
mkdir -p "$PREFIX/bin" "$PREFIX/share/applications"
ln -sf "$SRC" "$BIN"
cat > "$DESKTOP" <<EOF
[Desktop Entry]
Type=Application
Name=Breathe
Comment=Guided breathing patterns
Exec=$BIN
Icon=weather-windy
Terminal=false
Categories=Utility;
EOF

echo "Installed: $BIN -> $SRC"
echo "Installed: $DESKTOP"
case ":$PATH:" in
    *":$PREFIX/bin:"*) ;;
    *) echo "Note: $PREFIX/bin is not on your PATH; add it to run 'breathe' from a shell." ;;
esac
