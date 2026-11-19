#!/usr/bin/env bash
# Crea symlinks en ~/.local/bin para cada script de bin/.
# No sobrescribe un archivo que no es symlink.
set -u
src="$(cd "$(dirname "$0")/bin" && pwd)"
dest="$HOME/.local/bin"
mkdir -p "$dest"
for f in "$src"/*; do
    name="$(basename "$f")"
    target="$dest/$name"
    if [ -e "$target" ] && [ ! -L "$target" ]; then
        echo "aviso: $target existe y no es un symlink. No lo cambio." >&2
        continue
    fi
    ln -sfn "$f" "$target"
    echo "ok: $target -> $f"
done
