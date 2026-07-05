"""
معالجات تسجيل الدخول والخروج
"""
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.crypto import encrypt_token, decrypt_token
from bot.database import get_user_token, save_user_token, delete_user_token
from bot.github_api import validate_token

logger = logging.getLogger(__name__)


async def login(update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ربط حساب GitHub مع التحقق من صلاحية التوكن"""
    user_id = update.effective_user.id
    is_callback = bool(update.callback_query)

    if is_callback:
        await update.callback_query.answer()

    # ── حالة 1: بدون توكن → عرض الحالة الحالية ──
    if not context.args:
        encrypted = await get_user_token(user_id)
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="action_back_home")]]

        if encrypted:
            try:
                token = decrypt_token(encrypted)
                result = await validate_token(token)
                if result["valid"]:
                    text = (
                        "✅ *حالة الربط الحالية:*\n\n"
                        f"👤 الحساب: `@{result['login']}`\n"
                        "🔑 الحالة: متصل وفعّال\n\n"
                        "لتحديث التوكن:\n`/login ghp_your_new_token`\n\n"
                        "لإلغاء الربط:\n`/logout`"
                    )
                else:
                    text = (
                        "⚠️ *حالة الربط الحالية:*\n\n"
                        "🔑 التوكن المحفوظ: غير صالح أو منتهي\n\n"
                        "يرجى تحديثه:\n`/login ghp_your_new_token`"
                    )
            except Exception:
                text = (
                    "⚠️ *حالة الربط:*\n\n"
                    "حدث خطأ في قراءة التوكن المحفوظ.\n"
                    "يرجى إعادة الربط:\n`/login ghp_your_new_token`"
                )
        else:
            text = (
                "❌ *حالة الربط:*\n\n"
                "لم يتم ربط أي حساب GitHub بعد.\n\n"
                "للربط:\n`/login ghp_your_token`\n\n"
                "💡 *كيف تحصل على توكن؟*\n"
                "GitHub → Settings → Developer settings\n"
                "→ Personal access tokens → Tokens (classic)\n"
                "→ Generate new token\n\n"
                "✅ تحتاج فقط صلاحية: `public_repo`"
            )

        if is_callback:
            await update.callback_query.edit_message_text(
                text, parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        else:
            await update.message.reply_text(
                text, parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        return

    # ── حالة 2: مع توكن → التحقق ثم الحفظ ──
    token = context.args[0]
    loading_text = "⏳ جاري التحقق من صلاحية التوكن..."

    if is_callback:
        await update.callback_query.edit_message_text(loading_text)
    else:
        msg = await update.message.reply_text(loading_text)

    result = await validate_token(token)

    if result["valid"]:
        encrypted = encrypt_token(token)
        await save_user_token(user_id, encrypted)

        text = (
            f"✅ *تم الربط بنجاح!*\n\n"
            f"👤 الحساب: `@{result['login']}`\n"
            f"🔑 الحالة: متصل وفعّال 🔐\n\n"
            f"يمكنك الآن البحث بحرية بمعدل 5000 طلب/ساعة."
        )
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="action_back_home")]]

        if is_callback:
            await update.callback_query.edit_message_text(
                text, parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        else:
            await msg.edit_text(
                text, parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
    else:
        text = (
            f"❌ *فشل التحقق من التوكن!*\n\n"
            f"原因: {result['error']}\n\n"
            f"تأكد من:\n"
            f"• التوكن يبدأ بـ `ghp_` أو `github_pat_`\n"
            f"• التوكن لم يُلغَ أو ينتهِ\n"
            f"• يحتوي على صلاحية `public_repo`"
        )
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="action_back_home")]]

        if is_callback:
            await update.callback_query.edit_message_text(
                text, parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        else:
            await msg.edit_text(
                text, parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )


async def logout(update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """إلغاء ربط حساب GitHub"""
    user_id = update.effective_user.id
    is_callback = bool(update.callback_query)

    if is_callback:
        await update.callback_query.answer()

    deleted = await delete_user_token(user_id)
    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="action_back_home")]]

    if deleted:
        text = "✅ تم إلغاء ربط حساب GitHub بنجاح."
    else:
        text = "ℹ️ لا يوجد حساب GitHub مرتبط بحسابك."

    if is_callback:
        await update.callback_query.edit_message_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard),
        )
    else:
        await update.message.reply_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard),
        )