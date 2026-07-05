"""
إعدادات التهيئة الرئيسية للبوت
جميع القيم تُقرأ من متغيرات البيئة (Environment Variables)
"""
import os
import base64
import hashlib
from cryptography.fernet import Fernet


class Config:
    """إعدادات البوت - تُقرأ جميعها من متغيرات البيئة"""

    # --- توكن بوت تيليجرام (إجباري) ---
    BOT_TOKEN: str = os.environ["TELEGRAM_BOT_TOKEN"]

    # --- مفتاح تشفير الـ GitHub Tokens (إجباري) ---
    # يُستخدم لتشفير توكنات المستخدمين قبل حفظها في قاعدة البيانات
    @staticmethod
    def get_encryption_key() -> bytes:
        raw = os.environ["ENCRYPTION_KEY"]
        # تحويل أي نص إلى مفتاح Fernet صالح (32 بايت مشفّر بـ base64)
        digest = hashlib.sha256(raw.encode()).digest()
        return base64.urlsafe_b64encode(digest)

    @property
    def cipher_suite(self) -> Fernet:
        return Fernet(self.get_encryption_key())

    # --- مسار قاعدة البيانات ---
    # في Railway يُستحفظ في مجلد /data (Persistent Volume)
    DB_PATH: str = os.environ.get("DB_PATH", "github_store_bot.db")

    # --- وضع التشغيل ---
    # polling: للنشر المحلي أو الخوادم العادية
    # webhook: للنشر على منصات مثل Railway (أكثر كفاءة واستقراراً)
    MODE: str = os.environ.get("BOT_MODE", "polling")

    # --- إعدادات Webhook (مطلوبة عند استخدام MODE=webhook) ---
    WEBHOOK_URL: str = os.environ.get("WEBHOOK_URL", "")
    WEBHOOK_PORT: int = int(os.environ.get("WEBHOOK_PORT", "8080"))
    WEBHOOK_SECRET: str = os.environ.get("WEBHOOK_SECRET", "")

    # --- إعدادات عامة ---
    LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")
    GITHUB_API_TIMEOUT: int = int(os.environ.get("GITHUB_API_TIMEOUT", "15"))
    MAX_FILE_SIZE_MB: int = int(os.environ.get("MAX_FILE_SIZE_MB", "49"))
    MAX_DESCRIPTION_LENGTH: int = int(os.environ.get("MAX_DESCRIPTION_LENGTH", "300"))


# نسخة واحدة من الإعدادات للاستخدام في جميع أنحاء المشروع
config = Config()