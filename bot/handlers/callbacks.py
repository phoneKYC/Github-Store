"""
معالجات نقرات الأزرار الشفافة (Callback Query Handlers)
"""
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.config import config
from bot.crypto import decrypt_token
from bot.database import get_user_token
from bot.github_api import (
    fetch_latest_release,
    download_file,
    filter_assets_by_os,
    OS_LABELS,
)

logger = logging.getLogger(__name__)


async def button_router(update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """توجيه نقرات الأزرار الشفافة إلى المعالج المناسب"""
    query = update.callback_query
    data = query.data

    if data == "prompt_search":
        await query.answer()
        await query.edit_message_text(
            "🔍 للبحث، يرجى كتابة الأمر بالطريقة التالية:\n"
            "`/search اسم_المستودع`\n\n"
            "مثال:\n`/search OpenHub-Store/GitHub-Store`\n\n"
            "أو أرسل رابط المستودع مباشرة:\n`/search https://github.com/owner/repo`",
            parse_mode="Markdown",
        )

    elif data == "prompt_login":
        await query.answer()
        await query.edit_message_text(
            "🔑 لربط حسابك، يرجى كتابة الأمر بالطريقة التالية:\n"
            "`/login ghp_your_token_here`\n\n"
            "💡 للحصول على توكن:\n"
            "GitHub → Settings → Developer settings → "
            "Personal access tokens → Tokens (classic) → Generate new token",
            parse_mode="Markdown",
        )

    elif data.startswith("os_"):
        await handle_os_selection(update, context)


async def handle_os_selection(update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالجة اختيار نظام التشغيل وجلب الملفات المناسبة"""
    query = update.callback_query
    await query.answer()

    os_choice = query.data.split("_")[1]
    repo_path = context.user_data.get("current_repo")
    user_id = query.from_user.id

    if not repo_path:
        await query.edit_message_text(
            "❌ انتهت صلاحية الجلسة.\n"
            "يرجى إعادة كتابة أمر البحث `/search` من جديد."
        )
        return

    os_label = OS_LABELS.get(os_choice, os_choice.upper())

    await query.edit_message_text(
        f"⏳ جاري فحص أحدث إصدار لمستودع `{repo_path}` "
        f"وجلب ملفات *{os_label}*...",
        parse_mode="Markdown",
    )

    # جلب التوكن الخاص بالمستخدم إذا توفر
    token = None
    encrypted_token = await get_user_token(user_id)
    if encrypted_token:
        try:
            token = decrypt_token(encrypted_token)
        except Exception as e:
            logger.error(f"Failed to decrypt token for user {user_id}: {e}")

    # جلب بيانات الإصدار من GitHub API
    release_data = await fetch_latest_release(repo_path, token)

    if "error" in release_data:
        await query.edit_message_text(f"❌ {release_data['error']}")
        return

    assets = release_data.get("assets", [])
    tag_name = release_data.get("tag_name", "الإصدار الأخير")
    body = release_data.get("body", "لا يوجد وصف متوفر.")
    body = body[:config.MAX_DESCRIPTION_LENGTH]  # اقتطاع الوصف

    # فلترة الملفات حسب نظام التشغيل
    filtered_assets = filter_assets_by_os(assets, os_choice)

    if not filtered_assets:
        await query.edit_message_text(
            f"⚠️ لم يتم العثور على حزم تثبيت مخصصة لنظام *{os_label}* "
            f"في الإصدار الأخير `{tag_name}` لهذا المستودع.",
            parse_mode="Markdown",
        )
        return

    await query.edit_message_text(
        f"📦 تم العثور على {len(filtered_assets)} ملف متوافق مع {os_label}.\n"
        f"جاري المعالجة والموازنة حسب الحجم..."
    )

    # معالجة كل ملف
    max_size_bytes = config.MAX_FILE_SIZE_MB * 1024 * 1024

    for asset in filtered_assets:
        name = asset["name"]
        download_url = asset["browser_download_url"]
        size_bytes = asset["size"]
        size_mb = size_bytes / (1024 * 1024)

        caption = (
            f"📦 *الملف:* `{name}`\n"
            f"🏷️ *الإصدار:* `{tag_name}`\n"
            f"📊 *الحجم:* {size_mb:.2f} MB\n\n"
            f"📝 *موجز التغييرات:*\n_{body}_\n\n"
            f"🛠️ مطور البوت: [@IIDZII] | مستوحى من OpenHub"
        )

        if size_bytes <= max_size_bytes:
            # ملف صغير: تحميل ورفع كوثيقة
            try:
                await context.bot.send_chat_action(
                    chat_id=query.message.chat_id, action="upload_document"
                )

                file_content = await download_file(download_url)
                if file_content:
                    await context.bot.send_document(
                        chat_id=query.message.chat_id,
                        document=file_content,
                        filename=name,
                        caption=caption,
                        parse_mode="Markdown",
                    )
                else:
                    raise Exception("فشل تحميل الملف من سيرفرات GitHub")
            except Exception as e:
                logger.error(f"Error uploading file {name}: {e}")
                # تراجع لرابط مباشر
                keyboard = [
                    [InlineKeyboardButton("🔗 رابط تحميل مباشر", url=download_url)]
                ]
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=f"⚠️ تعذر رفع الملف مباشرة.\n\n{caption}",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown",
                )
        else:
            # ملف كبير: إرسال رابط مباشر
            keyboard = [
                [InlineKeyboardButton("🚀 رابط تحميل مباشر وسريع", url=download_url)]
            ]
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=caption,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
            )