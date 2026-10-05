# VidSave — ফ্রি ডিপ্লয় গাইড (Render)

Render-এর ফ্রি প্ল্যানে সাইট ২৪/৭ চালানো যায়। ফ্রি ওয়েব সার্ভিস ১৫ মিনিট নিষ্ক্রিয়
থাকলে ঘুমিয়ে পড়ে, তাই নিচের keep-alive সেটআপ করা আছে।

## যা লাগবে
- একটি GitHub অ্যাকাউন্ট (আপনার: `sumondryxyz1`)
- একটি Render অ্যাকাউন্ট (GitHub দিয়ে সাইন-ইন) — কার্ড লাগে না

## ধাপ ১ — GitHub repo
1. github.com → **New repository**
2. নাম: `vidsave`, ভিজিবিলিটি: **Public**
3. **Create repository**
4. এই প্রজেক্টের কোড সেখানে পুশ করুন (নিচে কমান্ড)

```bash
cd /workspace/project
git remote add origin https://github.com/<your-username>/vidsave.git
git branch -M main
git push -u origin main
```

## ধাপ ২ — Render-এ ডিপ্লয়
1. render.com → **New +** → **Blueprint**
2. আপনার `vidsave` repo সিলেক্ট করুন
3. Render `render.yaml` পড়ে নিজেই সব সেট করবে → **Apply**
4. প্রথম বিল্ড শেষ হলে লিংক পাবেন: `https://vidsave.onrender.com`

> Blueprint না চাইলে: **New + → Web Service** → repo সিলেক্ট → Runtime: Python →
> Build: `pip install -r requirements.txt` → Start: `python main.py`

## ধাপ ৩ — keep-alive (ঘুমাবে না)
GitHub repo → **Settings → Secrets and variables → Actions → Variables → New variable**

- Name: `KEEPALIVE_URL`
- Value: `https://vidsave.onrender.com`

এরপর `.github/workflows/keepalive.yml` প্রতি ১০ মিনিটে `/health` ping করবে।

**বিকল্প:** [UptimeRobot](https://uptimerobot.com) (ফ্রি ৫০ মনিটর) — Monitor URL =
`https://vidsave.onrender.com/health`, interval ৫ মিনিট।

## ফ্রি প্ল্যানে যেসব সীমা ধরে রাখা হয়েছে
| সেটিং | মান | কারণ |
|---|---|---|
| `MAX_CONCURRENT` | 2 | ০.১ CPU-তে একসাথে বেশি ডাউনলোড নয় |
| `MAX_FILESIZE_MB` | 500 | ফ্রি ডিস্ক ভরে না যায় |
| `JOB_TTL` | 1800 | ফাইল ৩০ মিনিট পর মুছে যায় |

## ডাউনলোড ও মেমরি
- ফাইল **ডিস্কে** (temp dir) নামে, মেমরিতে পুরোটা লোড হয় না
- ডাউনলোড শেষে **stream** হয়ে ক্লায়েন্টে যায়
- `JOB_TTL` পরে ফাইল স্বয়ংক্রিয়ভাবে মুছে যায়
- একসাথে বেশি বড় ভিডিও/প্লেলিস্ট ফ্রিতে ধীর হতে পারে — টেস্ট করে দেখুন

## ফ্রি ডোমেইন (ঐচ্ছিক)
`vidsave.eu.org` চাইলে eu.org-এ ফ্রি সাবডোমেইন অ্যাপ্লাই করা যায়, তারপর
Render-এ **Settings → Custom Domains**-এ যোগ করে DNS সেট করতে হয়।
