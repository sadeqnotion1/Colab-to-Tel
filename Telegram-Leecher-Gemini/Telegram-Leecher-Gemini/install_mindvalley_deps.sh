#!/bin/bash
# Mindvalley Dependencies Installer for Google Colab
# Installs N_m3u8DL-RE for M3U8 stream downloads

set -e

echo "📦 Installing Mindvalley downloader dependencies..."

# Install N_m3u8DL-RE (Linux x64 binary)
echo "⬇️  Downloading N_m3u8DL-RE..."
wget -q https://github.com/nilaoda/N_m3u8DL-RE/releases/latest/download/N_m3u8DL-RE_Beta_linux-x64 \
    -O /usr/local/bin/N_m3u8DL-RE

# Make executable
chmod +x /usr/local/bin/N_m3u8DL-RE

# Verify installation
if command -v N_m3u8DL-RE &> /dev/null; then
    echo "✅ N_m3u8DL-RE installed successfully"
    N_m3u8DL-RE --version || echo "   (Version info not available)"
else
    echo "❌ N_m3u8DL-RE installation failed"
    exit 1
fi

# FFmpeg is already installed via apt in the main setup
# Just verify it's available
if command -v ffmpeg &> /dev/null; then
    echo "✅ FFmpeg is available"
else
    echo "⚠️  Warning: FFmpeg not found. Installing..."
    apt-get update -qq && apt-get install -y ffmpeg -qq
    echo "✅ FFmpeg installed"
fi

# Install Python dependencies for subtitle downloads
echo "📦 Installing Python dependencies..."
pip install -q aiohttp

echo ""
echo "✅ All Mindvalley dependencies installed!"
echo "   - N_m3u8DL-RE: $(which N_m3u8DL-RE)"
echo "   - FFmpeg: $(which ffmpeg)"
echo ""
