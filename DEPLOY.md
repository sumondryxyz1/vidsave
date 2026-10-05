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

কোড এখন YouTube-এর জন্য একাধিক player client চেষ্টা করে, তবু Render-এর IP-তে
সবই ব্লক হতে পারে। তখন **কুকিজ**ই আসল সমাধান:

### কুকিজ দেওয়ার সহজ নিয়ম (base64)

1. ব্রাউজারে **"Get cookies.txt LOCALLY"** এক্সটেনশন বসান (Chrome/Firefox)।
2. `youtube.com`-এ লগইন করে এক্সটেনশন দিয়ে **Export** → `youtube.txt` নামান।
3. ফাইলটা base64 করুন:
   - Linux/Mac: `base64 -w0 youtube.txt > yt.b64`
   - Windows: `certutil -encode youtube.txt yt.b64`
   - অনলাইন: যেকোনো "base64 encode file" টুল
4. Render → সার্ভিস → **Environment** → Add:
   - `YOUTUBE_COOKIES_B64` = ওই base64 লেখাটা
   - (Facebook/Instagram/X-এর জন্য `FACEBOOK_COOKIES_B64`, `INSTAGRAM_COOKIES_B64`, `TWITTER_COOKIES_B64`)
5. **Save** → Render নিজেই আবার ডিপ্লয় করবে।

> ⚠️ কুকিজ = আপনার অ্যাকাউন্টের চাবি। শুধু নিজের হোস্টে দিন; কখনো GitHub-এ কমিট করবেন না।
> বিকল্প: `YOUTUBE_COOKIES` env var-এ ফাইলের পাথ দিন (Render-এ ফাইল আপলোড করা কষ্টের)।

### প্রক্সি (বিকল্প)

Render → Environment → `PROXY` = `http://user:pass@host:port` (রেসিডেন্সিয়াল প্রক্সি)।
এতে কুকিজ ছাড়াই YouTube/X চলবে। ফ্রি নয়, কিন্তু সস্তা।

## ৮. ঘুম না পড়ার সমাধান

Render ফ্রি প্ল্যান **১৫ মিনিট** নিষ্ক্রিয় থাকলে ঘুমায়; প্রথম রিকোয়েস্টে ~৫০ সেকেন্ড লাগে।
তিনটা স্তরে সামলানো যায়:

1. **GitHub Actions keep-alive** (রেডি আছে) — `.github/workflows/keepalive.yml`
   প্রতি ১০ মিনিটে `/health` ping করে। তবে GitHub-এর scheduled job কখনো দেরি করে,
   তাই এটাই একমাত্র ভরসা নয়।
2. **বাইরের uptime monitor** (সবচেয়ে ভরসাযোগ্য) — [UptimeRobot](https://uptimerobot.com)
   ফ্রি অ্যাকাউন্ট → Monitor `https://vidsave-tavc.onrender.com/health`, interval **৫ মিনিট**।
3. **Render-এর নিজের health check** — `render.yaml`-এ `healthCheckPath: /health` আছে।

> সব মিলিয়ে মাসে Render-এর ফ্রি ঘণ্টা (৭৫০h) ছাড়িয়ে যেতে পারে; ঘন ping-এ সীমা শেষ হলে
> সার্ভিস বন্ধ হতে পারে — তাই ৫-১০ মিনিটের বেশি ঘন করবেন না।

