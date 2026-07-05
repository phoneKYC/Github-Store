# GitHub Store Bot

بوت تيليجرام احترافي للبحث عن البرمجيات مفتوحة المصدر على GitHub وتحميل إصداراتها (Releases) مباشرة.

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Telegram-Bot-26A5E4?logo=telegram&logoColor=white" alt="Telegram">
  <img src="https://img.shields.io/badge/Railway-Deploy-0B0D0E?logo=railway&logoColor=white" alt="Railway">
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License">
</p>

---

## ✨ المميزات

- **🔍 بحث سريع** - ابحث بالاسم أو بالرابط الكامل للمستودع
- **⚙️ فلترة ذكية** - اختر نظام التشغيل (Android, Linux, Windows, macOS)
- **📤 موازنة ذكية** - ملفات صغيرة تُرفع مباشرة، ملفات كبيرة تُرسل كرابط
- **🔐 تشفير كامل** - توكنات GitHub تُشفر بـ AES-128 قبل الحفظ
- **🌐 وضعان للتشغيل** - Polling (محلي) و Webhook (إنتاجي)
- **🚀 نشر واحد أمر** - جاهز للنشر على Railway بضغطة واحدة

---

## 📁 هيكل المشروع

```
github-store-bot/
├── bot/
│   ├── __init__.py
│   ├── config.py          # إعدادات التهيئة (متغيرات البيئة)
│   ├── crypto.py          # تشفير/فك تشفير التوكنات
│   ├── database.py        # إدارة قاعدة البيانات (SQLite)
│   ├── github_api.py      # التواصل مع GitHub API
│   ├── webhook_server.py  # خادم Webhook (FastAPI)
│   └── handlers/
│       ├── __init__.py
│       ├── commands.py    # أوامر /start و /help
│       ├── search.py      # أوامر /search, /login, /logout
│       └── callbacks.py   # معالجات الأزرار الشفافة
├── main.py                # نقطة الدخول الرئيسية
├── Dockerfile             # صورة Docker للنشر
├── railway.json           # إعدادات Railway
├── Procfile               # أمر التشغيل
├── requirements.txt       # مكتبات Python
├── .env.example           # قالب متغيرات البيئة
├── .gitignore
├── LICENSE
└── README.md
```

---

## 🚀 النشر على Railway

### الطريقة 1: عبر GitHub (موصى بها)

1. **ارفع المشروع على GitHub:**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/YOUR_USERNAME/github-store-bot.git
   git push -u origin main
   ```

2. **أنشئ مشروع جديد على Railway:**
   - اذهب إلى [railway.app](https://railway.app)
   - اضغط **New Project** → **Deploy from GitHub repo**
   - اختر مستودع البوت

3. **أضف متغيرات البيئة في Railway:**
   - اذهب إلى **Variables** في مشروع Railway
   - أضف المتغيرات التالية:

   | المتغير | القيمة | مطلوب؟ |
   |---------|--------|--------|
   | `TELEGRAM_BOT_TOKEN` | توكن البوت من @BotFather | ✅ نعم |
   | `ENCRYPTION_KEY` | أي نص عشوائي طويل (أنشئه: `python -c "import secrets; print(secrets.token_urlsafe(32))"`) | ✅ نعم |
   | `BOT_MODE` | `webhook` | ✅ نعم |
   | `WEBHOOK_URL` | `https://your-app.up.railway.app/webhook` | ✅ نعم |
   | `WEBHOOK_PORT` | `8080` | اختياري |
   | `WEBHOOK_SECRET` | نص عشوائي للحماية | اختياري |
   | `LOG_LEVEL` | `INFO` | اختياري |

4. **أضف Volume للحفاظ على البيانات:**
   - في Railway، اذهب إلى **Services** → أضف **Volume**
   - اضبط **Mount Path** على `/data`
   - هذا يضمن بقاء قاعدة البيانات حتى عند إعادة النشر

5. **فعّل Public Networking:**
   - اذهب إلى **Settings** → **Networking**
   - فعّل **Public** للحصول على رابط عام
   - انسخ الرابط وحدّث `WEBHOOK_URL` به

6. **أعد النشر** وسيبدأ البوت بالعمل!

### الطريقة 2: عبر Railway CLI

```bash
# تثبيت Railway CLI
npm install -g @railway/cli

# تسجيل الدخول
railway login

# إنشاء مشروع جديد
railway init

# ضبط المتغيرات
railway variables set TELEGRAM_BOT_TOKEN="your_token"
railway variables set ENCRYPTION_KEY="your_key"
railway variables set BOT_MODE="webhook"
railway variables set WEBHOOK_URL="https://your-app.up.railway.app/webhook"

# إنشاء Volume
railway volume create /data

# النشر
railway up
```

---

## 💻 التشغيل محلياً

### 1. استنساخ المشروع

```bash
git clone https://github.com/YOUR_USERNAME/github-store-bot.git
cd github-store-bot
```

### 2. إنشاء بيئة افتراضية

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# أو: venv\Scripts\activate  # Windows
```

### 3. تثبيت المكتبات

```bash
pip install -r requirements.txt
```

### 4. إعداد متغيرات البيئة

```bash
cp .env.example .env
# عدّل الملف .env وأضف قيمك
```

### 5. تشغيل البوت

```bash
# وضع Polling (افتراضي للتشغيل المحلي)
python -m main
```

---

## ⚙️ الأوامر

| الأمر | الوصف |
|-------|-------|
| `/start` | بدء المحادثة وعرض الأزرار الرئيسية |
| `/help` | دليل الاستخدام الكامل |
| `/search <repo>` | البحث عن مستودع (بالاسم أو الرابط) |
| `/login <token>` | ربط حساب GitHub لرفع حد الطلبات |
| `/logout` | إلغاء ربط حساب GitHub |

---

## 🔐 الأمان

- **توكنات المستخدمين** تُشفر بـ AES-128 (Fernet) قبل حفظها في قاعدة البيانات
- **التوكن السري للـ Webhook** يمنع الطلبات المزيفة
- **لا يوجد أي بيانات حساسة** في الكود المصدري
- جميع الإعدادات تُقرأ من **متغيرات البيئة**

---

## 🛠️ التقنيات المستخدمة

- [Python 3.12](https://python.org)
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) - مكتبة التليجرام
- [FastAPI](https://fastapi.tiangolo.com) + [Uvicorn](https://www.uvicorn.org) - خادم Webhook
- [httpx](https://www.python-httpx.org) - طلبات HTTP غير متزامنة
- [aiosqlite](https://aiosqlite.omnilib.dev) - قاعدة بيانات SQLite غير متزامنة
- [cryptography](https://cryptography.io) - تشفير التوكنات

---

## 📝 ملاحظات

- فكرة المشروع مستوحاة من [OpenHub-Store/GitHub-Store](https://github.com/OpenHub-Store/GitHub-Store)
- التطوير والبناء: [@IIDZII](https://t.me/IIDZII)

---

## 📄 الرخصة

هذا المشروع مرخص تحت رخصة [MIT](LICENSE).