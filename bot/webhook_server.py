"""
خادم Webhook لاستقبال التحديثات من Telegram
يعمل مع FastAPI ويُستخدم عند النشر على منصات مثل Railway
"""
import logging

from fastapi import FastAPI, Request, Response

from bot.config import config
from bot.database import init_db
from bot.handlers.commands import start, help_command
from bot.handlers.auth import login, logout
from bot.handlers.search import search
from bot.handlers.callbacks import button_router
from telegram.ext import CommandHandler, CallbackQueryHandler

logger = logging.getLogger(__name__)

app = FastAPI(title="GitHub Store Bot Webhook")


@app.on_event("startup")
async def startup_event():
    """
    تهيئة البوت وقاعدة البيانات وضبط الـ Webhook
    عند بدء تشغيل الخادم
    """
    from telegram.ext import Application
    # بناء تطبيق التليجرام
    application = Application.builder().token(config.BOT_TOKEN).build()

    # تسجيل المعالجات
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("login", login))
    application.add_handler(CommandHandler("logout", logout))
    application.add_handler(CommandHandler("search", search))
    application.add_handler(CallbackQueryHandler(button_router))

    # تهيئة التطبيق وقاعدة البيانات
    await application.initialize()
    await application.start()
    await init_db()

    # ضبط الـ Webhook في Telegram
    await application.bot.set_webhook(
        url=config.WEBHOOK_URL,
        secret_token=config.WEBHOOK_SECRET if config.WEBHOOK_SECRET else None,
        allowed_updates=["message", "callback_query"],
    )
    logger.info(f"تم ضبط Webhook بنجاح: {config.WEBHOOK_URL}")

    # تخزين التطبيق في حالة FastAPI للوصول إليه في المعالجات
    app.state.application = application


@app.on_event("shutdown")
async def shutdown_event():
    """إيقاف التطبيق عند إغلاق الخادم"""
    application = getattr(app.state, "application", None)
    if application:
        await application.shutdown()
        logger.info("تم إيقاف التطبيق بنجاح")


@app.post("/webhook")
async def webhook_handler(request: Request) -> Response:
    """
    نقطة نهاية لاستقبال التحديثات من Telegram
    Telegram يرسل التحديثات إلى هذا المسار عند وضعه كـ Webhook
    """
    from telegram import Update

    # التحقق من التوكن السري إن وُجد
    if config.WEBHOOK_SECRET:
        telegram_signature = request.headers.get(
            "X-Telegram-Bot-Api-Secret-Token", ""
        )
        if telegram_signature != config.WEBHOOK_SECRET:
            logger.warning("محاولة وصول غير مصرح بها إلى Webhook")
            return Response(status_code=403)

    # تحليل التحديث ومعالجته
    application = app.state.application
    data = await request.json()
    update = Update.de_json(data, application.bot)

    await application.process_update(update)

    return Response(status_code=200)


@app.get("/health")
async def health_check() -> dict:
    """
    فحص صحي (Health Check)
    Railway تستخدمه لمراقبة حالة الخدمة
    """
    return {"status": "ok", "service": "github-store-bot", "mode": "webhook"}