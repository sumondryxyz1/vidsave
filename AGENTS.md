# VidSave — এজেন্ট নোট

মিডিয়া ডাউনলোডার প্রকল্প: (১) Telegram bot, (২) ওয়েব অ্যাপ (FastAPI), (৩) Android APK,
(৪) PWA। ব্র্যান্ড নাম **VidSave**।

## স্ট্রাকচার

- `webapp.py` — FastAPI অ্যাপ, `STATIC_DIR=static/`, ডিফল্ট পোর্ট `PORT` (fallback 12000)
- `static/index.html` — সম্পূর্ণ ফ্রন্টএন্ড (এক ফাইল, CSS+JS ইনলাইন, lang="bn")
- `static/manifest.webmanifest`, `static/icon.svg`, `static/sw.js` — PWA
- `static/VidSave.apk` — বিল্ড করা Android APK (সাইটে `/VidSave.apk` লিংকে সার্ভ হয়)
- `bot.py`, `downloader.py` — Telegram bot + yt-dlp ইঞ্জিন
- `android/` — WebView অ্যাপ সোর্স (বিল্ড: `android/README.md`)
- `main.py` — হোস্টিং entrypoint; `Dockerfile`, `render.yaml` — ডিপ্লয়

## গুরুত্বপূর্ণ নিয়ম

- ওয়েব অ্যাপের সব লিংক **relative** রাখুন — কাস্টম ডোমেইনে (vidsave.eu.org) কাজ করার জন্য।
- Android APK-র সাইট URL: `android/app/src/main/res/values/strings.xml` → `home_url`।
- APK সাইটটাই WebView-তে লোড করে, তাই ওয়েব ফিচার/অ্যাড অ্যাপেও সাথে সাথে আসে —
  APK আবার বিল্ড না করেই ওয়েব আপডেটে অ্যাপ আপডেট হয় (URL একই থাকলে)।
- `AD_CONFIG` (index.html) — অ্যাড ইন্টিগ্রেশন পয়েন্ট, `#adTop` স্লটে বসে।
- `android/vidsave.keystore` **সুরক্ষিত** রাখুন; হারালে অ্যাপ আপডেট করা যাবে না।

## ডেভেলপমেন্ট

```bash
pip install -r requirements.txt
PORT=12000 python webapp.py        # ওয়েব অ্যাপ
export BOT_TOKEN=...; python bot.py  # বট
```

## Android বিল্ড (Gradle নেই, সরাসরি build-tools)

```bash
export ANDROID_HOME=/opt/android-sdk
BT=$ANDROID_HOME/build-tools/35.0.0
# aapt2 compile/link → javac --release 8 → d8 → zip dex → zipalign → apksigner
# বিস্তারিত: android/README.md
```

- build-tools **35.0.0** ব্যবহার করুন; 34.0.0-এ d8 ল্যাম্বডা-ডেক্সে বাগ করে।
- `javac --release 8` ব্যবহার করুন (bootclasspath override দিলে LambdaMetafactory error)।

## টেস্ট

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:12000/  # 200
# রুট: / /manifest.webmanifest /icon.svg /sw.js /VidSave.apk — সব 200 হওয়া উচিত
```

## মনিটাইজেশন

Adsterra APK-তে শুধু Direct Link/Smartlink; ওয়েবে Popunder/Social Bar/Banner।
বিকল্প: Monetag (APK SDK)। বিস্তারিত README-তে।

## হোস্টিং (স্থায়ী ফ্রি লিংক)

- `/workspace/project` = পুরো অ্যাপ (repo root-এ `render.yaml` আছে)।
- Render Blueprint: `render.yaml` → `rootDir: vidsave` ধরে নেয়; repo root-এ পুশ করলে
  `rootDir` সরিয়ে দিন অথবা কোড `vidsave/` ফোল্ডারে রাখুন।
- `/health` endpoint আছে — uptime monitor ও Render health check-এর জন্য।
- keep-alive: `.github/workflows/keepalive.yml` (repo variable `KEEPALIVE_URL`)।
- ফ্রি-টিয়ার সীমা: `MAX_CONCURRENT=2`, `MAX_FILESIZE_MB=500`, `JOB_TTL=1800`।
- সেশন পডের লিংক (`work-*.<...>.all-hands.dev`) **অস্থায়ী** — সেশন শেষে মরে যায়।

## GitHub অ্যাক্সেস সীমা (গুরুত্বপূর্ণ)

- হাতের `GITHUB_TOKEN` = `ghu_` (OpenHands AI OAuth অ্যাপ) → **read-only**, কোনো
  repo-তে push/API-write সম্ভব নয় ("Resource not accessible by integration")।
- নতুন repo তৈরি করাও সম্ভব নয়। কোড বদলাতে চাইলে ইউজারের নিজের PAT (`repo` scope)
  লাগবে, অথবা ইউজার হাতে আপলোড করবেন (`/vidsave-code.zip` রেডি করা আছে)।
