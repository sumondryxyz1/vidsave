# ডাউনলোড বট (Downloader Bot)

টেলিগ্রাম বট — যেকোনো সাইটের লিংক (YouTube, Facebook, Instagram, TikTok, X/Twitter,
Vimeo, Reddit, প্রভৃতি) পাঠালে কোয়ালিটি বেছে নিয়ে ভিডিও বা MP3 ডাউনলোড করে পাঠায়।
ডাউনলোড ইঞ্জিন হিসেবে [yt-dlp](https://github.com/yt-dlp/yt-dlp) ব্যবহার করা হয়েছে,
তাই ১০০০+ সাইট সাপোর্টেড।

## ফিচার

- 🔗 যেকোনো লিংক পেস্ট করলেই মেটাডেটা (টাইটেল, থাম্বনেইল, ডিউরেশন) দেখায়
- 🎬 2160p / 1440p / 1080p / 720p / 480p / 360p — যেটা সোর্সে আছে
- 🎵 MP3 অডিও এক্সট্রাকশন (192 kbps)
- 🔒 প্রাইভেট/এজ-রেস্ট্রিক্টেড কনটেন্টের জন্য কুকি সাপোর্ট
- ⚡ একসাথে কয়েকটা ডাউনলোড (concurrency limit সহ)

## সেটআপ

```bash
pip install -r requirements.txt

# BotFather থেকে টোকেন নিয়ে সেট করুন
export BOT_TOKEN="123456:ABC-তোমার-টোকেন"

python bot.py
```

`imageio` ছাড়াই ffmpeg/ffprobe আসে `static-ffmpeg` প্যাকেজের সাথে — প্রথমবার চালালে
বাইনারি ডাউনলোড হয়ে যাবে।

## কুকি (ঐচ্ছিক)

প্রাইভেট ভিডিও, এজ-ভেরিফাইড বা লগইন-দরকার কনটেন্টের জন্য ব্রাউজার থেকে
Netscape ফরম্যাটে `cookies.txt` এক্সপোর্ট করে পাথ দিন:

```bash
export YT_COOKIES=/path/to/youtube-cookies.txt
export FB_COOKIES=/path/to/facebook-cookies.txt
export IG_COOKIES=/path/to/instagram-cookies.txt
```

## এনভায়রনমেন্ট ভেরিয়েবল

| ভেরিয়েবল | ডিফল্ট | কাজ |
|---|---|---|
| `BOT_TOKEN` | — | টেলিগ্রাম বট টোকেন (আবশ্যক) |
| `MAX_UPLOAD_MB` | `50` | টেলিগ্রাম আপলোড লিমিট (লোকাল Bot API হলে বাড়ান) |
| `DOWNLOAD_TIMEOUT` | `1800` | প্রতি ডাউনলোডের সর্বোচ্চ সময় (সেকেন্ড) |
| `MAX_CONCURRENT` | `3` | একসাথে সর্বোচ্চ ডাউনলোড |
| `YT_COOKIES` / `FB_COOKIES` / `IG_COOKIES` | — | কুকি ফাইলের পাথ |

## সীমাবদ্ধতা

- টেলিগ্রামের সাধারণ আপলোড লিমিট **50MB**। বড় ফাইল পাঠাতে হলে
  [লোকাল Bot API সার্ভার](https://github.com/tdlib/telegram-bot-api) চালিয়ে
  `MAX_UPLOAD_MB` বাড়ান (সর্বোচ্চ 2000MB)।
- ডেটাসেন্টার IP থেকে YouTube কখনো `403` দিতে পারে। কুকি দিলে বা রেসিডেন্সিয়াল
  প্রক্সি হলে ঠিক হয়। ডাউনলোডার-ফ্রেন্ডলি হোস্টে চালানো বাঞ্ছনীয়।
- শুধু নিজের বা অনুমোদিত কনটেন্ট ডাউনলোড করুন; সাইটের শর্তাবলি মেনে চলুন।

## ফাইল স্ট্রাকচার

```
bot.py          # টেলিগ্রাম হ্যান্ডলার, কোয়ালিটি মেনু, আপলোড
downloader.py   # yt-dlp র‍্যাপার (probe + download)
requirements.txt
```
