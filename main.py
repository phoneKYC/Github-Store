"""
النقطة الرئيسية لتشغيل البوت (Entry Point)
يدعم وضعين: Polling و Webhook
"""
import asyncio
import logging
import os

from telegram.ext import Application, CommandHandler, CallbackQueryHandler

from bot.config import config
from bot.database import init_db
from bot.handlers.commands import start, help_command
from bot.handlers.auth import login, logout
from bot.handlers.search import search
from bot.handlers.callbacks import button_router

# ──────────────────────────────────────────────
# إعداد التسجيل
# ──────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
)
logger = logging.getLogger(__name__)


def build_application() -> Application:
    """بناء تطبيق التليجرام وتسجيل جميع المعالجات"""
    application = Application.builder().token(config.BOT_TOKEN).build()

    # معالجات الأوامر
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("login", login))
    application.add_handler(CommandHandler("logout", logout))
    application.add_handler(CommandHandler("search", search))

    # معالجات الأزرار الشفافة
    application.add_handler(CallbackQueryHandler(button_router))

    return application


# ──────────────────────────────────────────────
# وضع Polling (للتشغيل المحلي)
# ──────────────────────────────────────────────

async def run_polling() -> None:
    """تشغيل البوت بوضع الاستطلاع (Polling)"""
    application = build_application()

    async def post_init(app):
        await init_db()
        logger.info("تمت التهيئة الأولية بنجاح")

    application.post_init = post_init

    logger.info("البوت يعمل بوضع Polling...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling(allowed_updates=["message", "callback_query"])
    await application.updater.idle()
    await application.shutdown()


# ──────────────────────────────────────────────
# وضع Webhook (للنشر على Railway)
# ──────────────────────────────────────────────

async def run_webhook() -> None:
    """تشغيل البوت بوضع Webhook مع خادم FastAPI"""
    import uvicorn

    # استيراد خادم الـ Webhook (يُهيئ نفسه عند التشغيل عبر on_event)
    from bot.webhook_server import app as fastapi_app

    port = int(os.environ.get("PORT", config.WEBHOOK_PORT))

    logger.info(f"البوت يعمل بوضع Webhook على المنفذ {port}")

    # تشغيل خادم FastAPI (يُهيئ البوت وقاعدة البيانات تلقائياً)
    config_uvicorn = uvicorn.Config(
        app=fastapi_app,
        host="0.0.0.0",
        port=port,
        log_level=config.LOG_LEVEL.lower(),
    )
    server = uvicorn.Server(config_uvicorn)
    await server.serve()


# ──────────────────────────────────────────────
# الدالة الرئيسية
# ──────────────────────────────────────────────

def main():
    """الدالة الرئيسية - تحدد وضع التشغيل من متغيرات البيئة"""
    if config.MODE == "webhook":
        if not config.WEBHOOK_URL:
            logger.error("وضع Webhook يتطلب تعيين متغير WEBHOOK_URL في متغيرات البيئة")
            return
        asyncio.run(run_webhook())
    else:
        asyncio.run(run_polling())


if __name__ == "__main__":
    main()