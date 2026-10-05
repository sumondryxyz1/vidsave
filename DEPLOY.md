# VidSave — Render ফ্রি ডিপ্লয় (ধাপে ধাপে)

Render ফ্রিতে সাইট চলে ২৪/৭, কার্ড লাগে না। ফ্রি সার্ভিস ১৫ মিনিট নিষ্ক্রিয় থাকলে
ঘুমিয়ে পড়ে — নিচের ধাপ ৪-এ সেটার সমাধান আছে।

---

## ১. Render অ্যাকাউন্ট খুলুন

1. যান: **https://dashboard.render.com/register**
2. **GitHub** বাটনে ক্লিক করে সাইন-ইন করুন
3. **Authorize Render** চাপুন
   - "Only select repositories" → **`freetools-site`** সিলেক্ট করুন
4. কার্ড লাগবে না ✅

> ⚠️ গুরুত্বপূর্ণ: Render-কে অবশ্যই `freetools-site` repo-তে অ্যাক্সেস দিতে হবে,
> কারণ সেখানেই এখন VidSave কোড আছে (`vidsave/` ফোল্ডারে)।

---

## ২. Render-এ ডিপ্লয় করুন

1. Render ড্যাশবোর্ড → ডানদিকে **New +** → **Blueprint**
2. **`freetools-site`** repo সিলেক্ট করুন → **Connect**
3. Render `render.yaml` পড়ে নিজেই সব সেট করবে:
   - Name: `vidsave`
   - Root Directory: `vidsave`
   - Plan: **Free**
   - Health check: `/health`
4. **Apply** বাটনে ক্লিক করুন
5. বিল্ড চলবে ~২-৪ মিনিট → লগে `Your service is live 🎉` দেখলেই শেষ

> Blueprint না চাইলে — **New + → Web Service** → `freetools-site` →
> Language **Python 3** → Root Directory `vidsave` →
> Build `pip install -r requirements.txt` → Start `python main.py` →
> Instance **Free** → **Deploy**

---

## ৩. আপনার লিংক

Render ড্যাশবোর্ডে পাবেন:

```
https://vidsave-tavc.onrender.com
```

এটাই স্থায়ী ফ্রি লিংক — **ওয়েবসাইট আর APK দুটোই** এটা দিয়েই চলবে ✅

---

## ৪. keep-alive (ঘুম থামাতে)

1. GitHub → `freetools-site` → **Settings → Secrets and variables → Actions**
2. **Variables** ট্যাব → **New repository variable**
3. Name: `KEEPALIVE_URL` → Value: `https://vidsave-tavc.onrender.com` → **Add**
4. `.github/workflows/keepalive.yml` প্রতি ১০ মিনিটে `/health` ping করবে

**সহজ বিকল্প:** https://uptimerobot.com (ফ্রি) → Monitor URL =
`https://vidsave-tavc.onrender.com/health`, interval ৫ মিনিট।

---

## ৫. ফ্রি প্ল্যানে সীমা (আগেই সেট করা)

| সেটিং | মান | কারণ |
|---|---|---|
| `MAX_CONCURRENT` | 2 | ০.১ CPU-তে বেশি ডাউনলোড নয় |
| `MAX_FILESIZE_MB` | 500 | ফ্রি ডিস্ক ভরে না যায় |
| `JOB_TTL` | 1800 | ফাইল ৩০ মিনিট পর মুছে যায় |

**ডাউনলোড ও মেমরি:** ফাইল ডিস্কে নামে (মেমরিতে পুরোটা নয়), শেষে stream হয়,
তারপর স্বয়ংক্রিয়ভাবে মুছে যায়। তাই RAM নয় — সীমা হলো CPU ও ডিস্ক।

---

## ৬. নিজের ডোমেইন (ঐচ্ছিক)

`vidsave.eu.org` চাইলে eu.org-এ ফ্রি সাবডোমেইন অ্যাপ্লাই করুন, তারপর Render-এ
**Settings → Custom Domains**-এ যোগ করে DNS সেট করুন।

## ৭. YouTube/X ব্লক হলে (গুরুত্বপূর্ণ)

Render-এর ডেটাসেন্টার IP থেকে YouTube ও X প্রায়ই **"not a bot"** চেক দেয়, তাই ওই
সাইটের ডাউনলোড ফ্রি হোস্টে কাজ নাও করতে পারে। TikTok, Facebook, Instagram, Vimeo,
Reddit, সরাসরি MP4 — সাধারণত কাজ করে।

সমাধান (যেকোনো একটা):
- **কুকিজ দিন** — ব্রাউজার থেকে YouTube cookies এক্সপোর্ট করে Render-এ
  `YT_COOKIES` env var-এ ফাইলের পাথ দিন (age/region/bot-check এড়ায়)।
- **রেসিডেন্সিয়াল প্রক্সি** — Render-এ `PROXY` env var সেট করুন
  (`http://user:pass@host:port`)। এতে YouTube-ও কাজ করবে।
- **নিজের হোস্টে চালান** — Oracle Cloud Free VM বা হোম সার্ভারে চালালে IP ব্লক হয় না।

