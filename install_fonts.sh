#!/bin/bash
# ==============================================================================
# install_fonts.sh - Install International Fonts for Headless Chrome / Linux
#
# Solves the 'Tofu Boxes' (□□□□) issue where non-Latin characters (Japanese,
# Chinese, Korean, Hindi, Arabic, Emojis) render as empty rectangular boxes
# on Linux servers, Docker containers, or VMs.
# ==============================================================================

echo '================================================================='
echo ' Installing International Fonts for Chrome / Playwright'
echo ' (Japanese, Chinese, Korean, Indic, Arabic, Emojis)'
echo '================================================================='

if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update && sudo apt-get install -y --no-install-recommends \
        fonts-noto-core \
        fonts-noto-cjk \
        fonts-noto-color-emoji \
        fonts-indic \
        fonts-liberation \
        fonts-dejavu-core \
        fontconfig
    sudo fc-cache -f -v
    echo '================================================================='
    echo ' [SUCCESS] Fonts installed! Chrome can now render all languages.'
    echo '================================================================='
elif command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y \
        google-noto-sans-cjk-fonts \
        google-noto-color-emoji-fonts \
        dejavu-sans-fonts
    sudo fc-cache -f -v
    echo '================================================================='
    echo ' [SUCCESS] Fonts installed via DNF!'
    echo '================================================================='
else
    echo '[WARNING] Unknown package manager. Please manually install Noto CJK fonts.'
fi
