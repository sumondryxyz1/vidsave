#!/usr/bin/env bash
# VidSave Android APK build (no Gradle). Requires ANDROID_HOME with build-tools 35.
set -e
cd "$(dirname "$0")"

: "${ANDROID_HOME:=$HOME/android-sdk}"
BT="$ANDROID_HOME/build-tools/35.0.0"
PLATFORM="$ANDROID_HOME/platforms/android-34/android.jar"
VER_CODE="${VER_CODE:-5}"
VER_NAME="${VER_NAME:-1.4}"

rm -rf build
mkdir -p build/classes

"$BT/aapt2" compile --dir app/src/main/res -o build/res.zip
"$BT/aapt2" link -o build/app.unsigned.apk \
  -I "$PLATFORM" \
  --manifest app/src/main/AndroidManifest.xml \
  --java build/gen \
  --min-sdk-version 24 --target-sdk-version 34 \
  --version-code "$VER_CODE" --version-name "$VER_NAME" \
  build/res.zip

javac --release 8 -classpath "$PLATFORM" \
  -d build/classes build/gen/eu/org/vidsave/app/R.java \
  app/src/main/java/eu/org/vidsave/app/MainActivity.java

"$BT/d8" --lib "$PLATFORM" --min-api 24 \
  --output build/ $(find build/classes -name "*.class")

python3 -c "import zipfile;z=zipfile.ZipFile('build/app.unsigned.apk','a');z.write('build/classes.dex','classes.dex');z.close()"

"$BT/zipalign" -f -p 4 build/app.unsigned.apk build/app.aligned.apk
"$BT/apksigner" sign --ks vidsave.keystore --ks-key-alias vidsave \
  --ks-pass pass:vidsave123 --key-pass pass:vidsave123 \
  --out build/VidSave.apk build/app.aligned.apk

cp build/VidSave.apk ../static/VidSave.apk
echo "OK -> android/build/VidSave.apk and static/VidSave.apk (v$VER_NAME)"
