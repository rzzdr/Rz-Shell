#!/bin/bash

echo "This will permanently delete Rz-Shell cache, configuration, and remove its entry from hyprland.conf."
read -p "Are you sure you want to continue? [y/N] " confirm

if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
    echo "Aborted."
    exit 1
fi

rm -rf ~/.cache/rz-shell
rm -rf ~/.config/Rz-Shell

conf_file=~/.config/hypr/hyprland.conf
tmp_file=$(mktemp)

awk '
BEGIN { found_comment=0 }
{
    if ($0 ~ /# Rz-Shell/) {
        found_comment=1
        next
    }
    if (found_comment && $0 ~ /source[[:space:]]*=[[:space:]]*~\/\.config\/Rz-Shell\/config\/hypr\/rz-shell\.conf/) {
        found_comment=0
        next
    }
    print
}' "$conf_file" > "$tmp_file" && mv "$tmp_file" "$conf_file"

echo "Rz-Shell data and config removed successfully."
