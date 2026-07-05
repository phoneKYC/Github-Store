"""
معالجات البحث وربط الحساب
"""
import logging
from urllib.parse import urlparse

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.config import config
from bot.crypto import encrypt_token, decrypt_token
from bot.database import save_user_token, get_user_token, delete_user_token
from bot.github_api import (
    fetch_latest_release,
    download_file,
    filter_assets_by_os,
    OS_LABELS,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# أمر ربط حساب GitHub
# ──────────────────────────────────────────────

async def login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ربط حساب GitHub بحساب التليجرام (حفظ التوكن مشفّراً)"""
    user_id = update.effective_user.id

    if not context.args:
        await update.message.reply_text(
            "❌ يرجى إدخال التوكن بعد الأمر. مثال:\n"
            "`/login ghp_your_classic_personal_access_token`",
            parse_mode="Markdown",
        )
        return

    token = context.args[0]

    # التحقق البسيط من صيغة التوكن
    if not (token.startswith("ghp_") or token.startswith("github_pat_")):
        await update.message.reply_text(
            "⚠️ التوكن يبدو غير صالح. يرجى التأكد من استخدام "
            "Classic Personal Access Token (يبدأ بـ `ghp_`) أو "
            "Fine-grained Token (يبدأ بـ `github_pat_`).",
            parse_mode="Markdown",
        )
        return

    encrypted = encrypt_token(token)
    await save_user_token(user_id, encrypted)

    await update.message.reply_text(
        "✅ تم ربط حسابك بـ GitHub بنجاح!\n"
        "تم تشفير التوكن تلقائياً لحمايته.\n"
        "يمكنك الآن البحث بحرية وبمعدل طلبات مرتفع."
    )


async def logout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """إلغاء ربط حساب GitHub"""
    user_id = update.effective_user.id
    deleted = await delete_user_token(user_id)

    if deleted:
        await update.message.reply_text(
            "✅ تم إلغاء ربط حسابك بـ GitHub بنجاح."
        )
    else:
        await update.message.reply_text(
            "ℹ️ لا يوجد حساب GitHub مرتبط بحسابك."
        )


# ──────────────────────────────────────────────
# أمر البحث
# ──────────────────────────────────────────────

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """البحث عن مستودع وعرض أزرار اختيار نظام التشغيل"""
    user_id = update.effective_user.id

    if not context.args:
        await update.message.reply_text(
            "❌ يرجى كتابة اسم المستودع أو الرابط بعد الأمر. مثال:\n"
            "`/search OpenHub-Store/GitHub-Store`",
            parse_mode="Markdown",
        )
        return

    raw_input = context.args[0]

    # تنظيف المدخلات إذا أرسل المستخدم رابط كامل
    repo_path = raw_input
    if "github.com/" in raw_input:
        path = urlparse(raw_input).path
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 2:
            repo_path = f"{parts[0]}/{parts[1]}"

    # حفظ مسار المستودع لتمريره عبر الأزرار
    context.user_data["current_repo"] = repo_path

    keyboard = [
        [
            InlineKeyboardButton("🤖 Android", callback_data="os_android"),
            InlineKeyboardButton("🐧 Linux", callback_data="os_linux"),
        ],
        [
            InlineKeyboardButton("🪟 Windows", callback_data="os_windows"),
            InlineKeyboardButton("🍏 macOS", callback_data="os_macos"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"🔍 تم استلام طلب البحث عن المستودع:\n`{repo_path}`\n\n"
        "الرجاء اختيار *نظام التشغيل المستهدف* لعرض الملفات المناسبة:",
        parse_mode="Markdown",
        reply_markup=reply_markup,
    )