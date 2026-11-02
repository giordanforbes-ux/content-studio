#!/usr/bin/env bash
# One-time setup for the content studio (macOS). Safe to run again.
set -e
if ! command -v ffmpeg >/dev/null; then
  if command -v brew >/dev/null; then brew install ffmpeg; else echo "Install Homebrew first: https://brew.sh"; exit 1; fi
fi
python3 -m pip install --user --quiet faster-whisper numpy
mkdir -p inbox work exports archive
echo "Ready. Run: claude   (from this folder), then drop a video in."
