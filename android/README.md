# Android অ্যাপ (VidSave)

ওয়েব অ্যাপটার নেটিভ Android মোড়ক — একটা WebView অ্যাপ যা `https://vidsave.eu.org`
লোড করে, ডাউনলোড `DownloadManager` দিয়ে সেভ করে, ফাইল-চুজার সাপোর্ট করে।

## ফাইল

- `app/src/main/AndroidManifest.xml` — প্যাকেজ `eu.org.vidsave.app`, মিন SDK 24 (Android 7+)
- `app/src/main/java/eu/org/vidsave/app/MainActivity.java` — WebView, ডাউনলোড, বাহ্যিক লিংক, ফাইল চুজার
- `app/src/main/res/` — থিম, লেআউট, আইকন (mdpi…xxxhdpi + adaptive)
- `app/src/main/res/values/strings.xml` — `home_url` এখানে বদলান (ডিফল্ট `https://vidsave.eu.org`)

## সাইট URL বদলানো

`app/src/main/res/values/strings.xml` এর `home_url` বদলে আবার বিল্ড করুন।

## বিল্ড (Gradle ছাড়া, সরাসরি Android build-tools)

```bash
export ANDROID_HOME=/opt/android-sdk
BT=$ANDROID_HOME/build-tools/35.0.0
cd android

# 1) রিসোর্স কম্পাইল + লিংক
$BT/aapt2 compile --dir app/src/main/res -o build/res.zip
$BT/aapt2 link -o build/app.unsigned.apk \
  -I $ANDROID_HOME/platforms/android-34/android.jar \
  --manifest app/src/main/AndroidManifest.xml --java build/gen \
  --min-sdk-version 24 --target-sdk-version 34 \
  --version-code 1 --version-name 1.0 build/res.zip

# 2) জাভা কম্পাইল
javac --release 8 -classpath $ANDROID_HOME/platforms/android-34/android.jar \
  -d build/classes build/gen/eu/org/vidsave/app/R.java \
  app/src/main/java/eu/org/vidsave/app/MainActivity.java

# 3) ডেক্স + APK-তে যোগ
$BT/d8 --lib $ANDROID_HOME/platforms/android-34/android.jar --min-api 24 \
  --output build/ $(find build/classes -name "*.class")
python3 -c "import zipfile;z=zipfile.ZipFile('build/app.unsigned.apk','a');z.write('build/classes.dex','classes.dex');z.close()"

# 4) অ্যালাইন + সাইন
$BT/zipalign -f -p 4 build/app.unsigned.apk build/app.aligned.apk
$BT/apksigner sign --ks vidsave.keystore --ks-key-alias vidsave \
  --ks-pass pass:vidsave123 --key-pass pass:vidsave123 \
  --out build/VidSave.apk build/app.aligned.apk
```

আউটপুট: `android/build/VidSave.apk` (ওয়েব অ্যাপে `/VidSave.apk` লিংকে সার্ভ হয়)।

## ⚠️ গুরুত্বপূর্ণ

- `vidsave.keystore` **সুরক্ষিত রাখুন** — হারালে অ্যাপ আপডেট করতে পারবেন না। পাসওয়ার্ড
  ডিফল্ট `vidsave123`; আসল রিলিজের আগে বদলে নিন।
- Play Store-এ দিতে চাইলে debug নয়, **release keystore** আর **AAB** লাগবে।
- APK শুধু Android-এ চলে; iPhone-এর জন্য PWA ("Add to Home Screen") ব্যবহার করুন।
- শুধু নিজের বা অনুমোদিত কনটেন্ট ডাউনলোড করুন।
