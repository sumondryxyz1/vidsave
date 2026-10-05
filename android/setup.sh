#!/usr/bin/env bash
# One-time (idempotent) Android build toolchain setup for VidSave.
set -e
SDK="${ANDROID_HOME:-$HOME/android-sdk}"

if ! command -v javac >/dev/null 2>&1; then
  echo "[setup] installing JDK 21 + unzip..."
  sudo apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq openjdk-21-jdk-headless unzip
fi

if [ ! -x "$SDK/build-tools/35.0.0/aapt2" ]; then
  echo "[setup] installing Android cmdline-tools + platform 34 + build-tools 35..."
  mkdir -p "$SDK/cmdline-tools"
  [ -f /tmp/cmdline-tools.zip ] || curl -sL -o /tmp/cmdline-tools.zip \
    https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip
  unzip -q -o /tmp/cmdline-tools.zip -d "$SDK/cmdline-tools"
  [ -d "$SDK/cmdline-tools/cmdline-tools" ] && mv "$SDK/cmdline-tools/cmdline-tools" "$SDK/cmdline-tools/latest"
  :
  yes | "$SDK/cmdline-tools/latest/bin/sdkmanager" --sdk_root="$SDK" --licenses >/dev/null 2>&1 || true
  "$SDK/cmdline-tools/latest/bin/sdkmanager" --sdk_root="$SDK" \
    "platforms;android-34" "build-tools;35.0.0" >/tmp/sdkmanager.log 2>&1
fi

echo "[setup] done: $(javac -version 2>&1) | $SDK/build-tools/35.0.0"
