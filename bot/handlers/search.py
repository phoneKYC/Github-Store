"""
معالجات البحث الكاملة - UX بأزرار شفافة ورسائل ذاتية التحديث
الرحلة: بحث → نتائج مستودعات → اختيار مستودع → قائمة إصدارات → اختيار إصدار → قائمة ملفات → تحميل
"""
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.crypto import decrypt_token
from bot.database import get_user_token
from bot.github_api import (
    search_repos,
    fetch_repo_info,
    fetch_releases,
    download_file,
    format_size,
    format_number,
)
from bot.config import config

logger = logging.getLogger(__name__)


async def _get_user_token(user_id: int) -> str | None:
    """جلب توكن المستخدم إذا موجود"""
    encrypted = await get_user_token(user_id)
    if encrypted:
        try:
            return decrypt_token(encrypted)
        except Exception:
            pass
    return None


# ──────────────────────────────────────────────
# المرحلة 1: بدء البحث
# ──────────────────────────────────────────────

async def search(update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """بدء عملية البحث"""
    if not context.args:
        keyboard = [
            [InlineKeyboardButton("🔙 رجوع", callback_data="action_back_home")],
        ]
        await update.message.reply_text(
            "❌ يرجى كتابة ما تريد البحث عنه.\n\n"
            "مثال:\n"
            "• `/search termux`\n"
            "• `/search owner/repo`\n"
            "• `/search https://github.com/owner/repo`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    query = " ".join(context.args)

    # حفظ في context
    context.user_data["search_query"] = query

    # إرسال رسالة "جاري البحث" قابلة للتحديث
    msg = await update.message.reply_text(
        f"🔍 جاري البحث عن \"{query}\"\n\n⏳ يرجى الانتظار..."
    )

    token = await _get_user_token(update.effective_user.id)
    result = await search_repos(query, token)

    chat_id = msg.chat_id
    message_id = msg.message_id

    if "error" in result:
        keyboard = [
            [InlineKeyboardButton("🔍 بحث جديد", callback_data="action_search"),
             InlineKeyboardButton("🔙 رجوع", callback_data="action_back_home")],
        ]
        await context.bot.edit_message_text(
            chat_id=chat_id, message_id=message_id,
            text=f"❌ {result['error']}",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    # ── نتيجة مباشرة: مستودع واحد (مسار مباشر) ──
    if "repo" in result:
        context.user_data["selected_repo"] = result["repo"]["full_name"]
        await _show_releases(
            context, chat_id, message_id,
            result["repo"], result["releases"], token
        )
        return

    # ── نتائج متعددة ──
    await _show_search_results(context, chat_id, message_id, result["results"], token)


# ──────────────────────────────────────────────
# المرحلة 2: عرض نتائج البحث
# ──────────────────────────────────────────────

async def _show_search_results(context, chat_id, message_id, results, token):
    """عرض نتائج البحث كأزرار"""
    text = (
        f"🔍 *نتائج البحث* ({len(results)} مستودعات):\n\n"
    )

    buttons = []
    for i, repo in enumerate(results):
        text += (
            f"{i+1}. [{repo['full_name']}](https://github.com/{repo['full_name']})\n"
            f"   {repo['description']}\n"
            f"   ⭐ {format_number(repo['stars'])}  |  🍴 {format_number(repo['forks'])}"
            f"  |  📅 {repo['updated_at']}\n\n"
        )
        buttons.append([InlineKeyboardButton(
            f"📦 {repo['full_name']}",
            callback_data=f"repo_{repo['full_name']}",
        )])

    buttons.append([InlineKeyboardButton("🔍 بحث جديد", callback_data="action_search")])
    buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data="action_back_home")])

    await context.bot.edit_message_text(
        chat_id=chat_id, message_id=message_id,
        text=text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
        disable_web_page_preview=True,
    )


# ──────────────────────────────────────────────
# المرحلة 3: اختيار مستودع → عرض الإصدارات
# ──────────────────────────────────────────────

async def show_repo_releases(update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """يُستدعى عند اختيار مستودع من نتائج البحث"""
    query = update.callback_query
    await query.answer()

    repo_full_name = query.data.replace("repo_", "")
    chat_id = query.message.chat_id
    message_id = query.message.message_id
    user_id = query.from_user.id

    context.user_data["selected_repo"] = repo_full_name

    # تحديث الرسالة: جاري التحميل
    await query.edit_message_text(
        f"📦 جاري تحميل `{repo_full_name}`...\n\n⏳ جلب الإصدارات..."
    )

    token = await _get_user_token(user_id)
    result = await fetch_repo_info(repo_full_name, token)

    if "error" in result:
        keyboard = [
            [InlineKeyboardButton("🔍 بحث جديد", callback_data="action_search"),
             InlineKeyboardButton("🔙 رجوع", callback_data="action_back_home")],
        ]
        await context.bot.edit_message_text(
            chat_id=chat_id, message_id=message_id,
            text=f"❌ {result['error']}",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    await _show_releases(context, chat_id, message_id,
                         result["repo"], result["releases"], token)


async def _show_releases(context, chat_id, message_id, repo, releases, token):
    """عرض قائمة الإصدارات لمستودع"""
    # معلومات المستودع
    topics = " ".join(f"#{t}" for t in repo.get("topics", []))
    lang = f"  |  💻 {repo['language']}" if repo.get("language") else ""
    license_str = f"  |  📜 {repo['license']}" if repo.get("license") else ""

    text = (
        f"📦 *{repo['full_name']}*\n\n"
        f"📝 {repo['description']}\n\n"
        f"⭐ {format_number(repo['stars'])}  |  🍴 {format_number(repo['forks'])}"
        f"{lang}{license_str}\n"
    )
    if topics:
        text += f"\n🏷️ {topics}"
    text += f"\n\n📄 *الإصدارات المتاحة* ({len(releases)}):\n"

    buttons = []
    for i, rel in enumerate(releases[:8]):  # أقصى 8 إصدارات
        prerelease = " 🧪" if rel["prerelease"] else ""
        asset_count = len(rel["assets"])
        text += (
            f"\n{i+1}. `{rel['tag_name']}`{prerelease}"
            f"  —  {rel['published_at']}"
            f"  ({asset_count} ملف)"
        )
        label = f"🏷️ {rel['tag_name']}"
        if rel["prerelease"]:
            label += " (Beta)"
        buttons.append([InlineKeyboardButton(
            label, callback_data=f"rel_{i}"
        )])

    # حفظ الإصدارات في context
    context.user_data["releases"] = releases

    buttons.append([InlineKeyboardButton("🔍 بحث جديد", callback_data="action_search")])
    buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data="action_back_home")])

    await context.bot.edit_message_text(
        chat_id=chat_id, message_id=message_id,
        text=text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
        disable_web_page_preview=True,
    )


# ──────────────────────────────────────────────
# المرحلة 4: اختيار إصدار → عرض الملفات
# ──────────────────────────────────────────────

async def show_release_assets(update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """يُستدعى عند اختيار إصدار معين"""
    query = update.callback_query
    await query.answer()

    idx = int(query.data.replace("rel_", ""))
    chat_id = query.message.chat_id
    message_id = query.message.message_id
    user_id = query.from_user.id

    releases = context.user_data.get("releases", [])
    if idx >= len(releases):
        await query.answer("❌ الإصدار غير موجود", show_alert=True)
        return

    rel = releases[idx]
    assets = rel.get("assets", [])

    if not assets:
        keyboard = [
            [InlineKeyboardButton("🔙 رجوع للإصدارات", callback_data=f"back_releases_{context.user_data.get('selected_repo', '')}")],
        ]
        await query.edit_message_text(
            f"⚠️ لا توجد ملفات تحميل في هذا الإصدار.\n\n"
            f"🏷️ الإصدار: `{rel['tag_name']}`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    repo_name = context.user_data.get("selected_repo", "")
    body = rel.get("body", "") or "لا يوجد وصف"
    body = body[:250]

    text = (
        f"📦 *{repo_name}*\n"
        f"🏷️ الإصدار: `{rel['tag_name']}`\n\n"
        f"📝 *موجز التغييرات:*\n_{body}_\n\n"
        f"📂 *الملفات المتاحة* ({len(assets)}):\n"
    )

    buttons = []
    for i, asset in enumerate(assets):
        size_str = format_size(asset["size"])
        dl_str = f"  |  ⬇️ {format_number(asset.get('download_count', 0))}" if asset.get("download_count") else ""
        text += f"\n{i+1}. `{asset['name']}`  —  {size_str}{dl_str}"

        # اختصار الاسم إذا طال
        name = asset["name"]
        if len(name) > 35:
            name = name[:32] + "..."
        buttons.append([InlineKeyboardButton(
            f"📥 {name} ({size_str})",
            callback_data=f"dl_{i}",
        )])

    context.user_data["current_release"] = rel
    context.user_data["current_assets"] = assets

    buttons.append([InlineKeyboardButton("🔙 رجوع للإصدارات", callback_data="back_to_releases")])

    await query.edit_message_text(
        chat_id=chat_id, message_id=message_id,
        text=text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# ──────────────────────────────────────────────
# المرحلة 5: تحميل الملف
# ──────────────────────────────────────────────

async def download_asset(update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """تحميل ملف محدد وإرساله أو إرسال رابط مباشر"""
    query = update.callback_query
    await query.answer("⬇️ جاري تجهيز الملف...")

    idx = int(query.data.replace("dl_", ""))
    chat_id = query.message.chat_id
    user_id = query.from_user.id

    assets = context.user_data.get("current_assets", [])
    if idx >= len(assets):
        await query.answer("❌ الملف غير موجود", show_alert=True)
        return

    asset = assets[idx]
    name = asset["name"]
    url = asset["download_url"]
    size_bytes = asset["size"]
    size_mb = size_bytes / (1024 * 1024)

    repo_name = context.user_data.get("selected_repo", "")
    rel = context.user_data.get("current_release", {})
    tag = rel.get("tag_name", "")

    caption = (
        f"📦 *{repo_name}*\n"
        f"🏷️ `{tag}`\n"
        f"📄 `{name}`\n"
        f"📊 {format_size(size_bytes)}"
    )

    # تحديث الرسالة: جاري التحميل
    await query.edit_message_text(
        f"⬇️ جاري تحميل `{name}`...\n"
        f"📊 الحجم: {format_size(size_bytes)}\n\n"
        f"⏳ يرجى الانتظار..."
    )

    token = await _get_user_token(user_id)
    max_size = config.MAX_FILE_SIZE_MB * 1024 * 1024

    if size_bytes <= max_size:
        # محاولة التحميل والرفع كوثيقة
        try:
            await context.bot.send_chat_action(chat_id=chat_id, action="upload_document")
            file_content = await download_file(url, token)

            if file_content:
                await context.bot.send_document(
                    chat_id=chat_id,
                    document=file_content,
                    filename=name,
                    caption=caption,
                    parse_mode="Markdown",
                )
                # تحديث الرسالة الأصلية
                keyboard = [
                    [InlineKeyboardButton("🔙 رجوع للملفات", callback_data="back_to_assets")],
                    [InlineKeyboardButton("🔗 رابط بديل", url=url)],
                ]
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=query.message.message_id,
                    text=f"✅ تم إرسال `{name}` بنجاح!",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                )
            else:
                # فشل التحميل → إرسال رابط
                keyboard = [
                    [InlineKeyboardButton("🚀 رابط تحميل مباشر", url=url)],
                    [InlineKeyboardButton("🔙 رجوع للملفات", callback_data="back_to_assets")],
                ]
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=query.message.message_id,
                    text=(
                        f"⚠️ تعذر تحميل الملف مباشرة.\n\n"
                        f"{caption}\n\n"
                        f"🔗 استخدم الرابط التالي:"
                    ),
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                )
        except Exception as e:
            logger.error(f"Upload error for {name}: {e}")
            keyboard = [
                [InlineKeyboardButton("🚀 رابط تحميل مباشر", url=url)],
                [InlineKeyboardButton("🔙 رجوع للملفات", callback_data="back_to_assets")],
            ]
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=query.message.message_id,
                text=(
                    f"⚠️ حدث خطأ أثناء رفع الملف.\n\n"
                    f"{caption}\n\n"
                    f"🔗 يمكنك التحميل عبر الرابط:"
                ),
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
    else:
        # ملف كبير → رابط مباشر فقط
        keyboard = [
            [InlineKeyboardButton("🚀 رابط تحميل مباشر", url=url)],
            [InlineKeyboardButton("🔙 رجوع للملفات", callback_data="back_to_assets")],
        ]
        await context.bot.edit_message_text(
            chat_id=chat_id, message_id=query.message.message_id,
            text=(
                f"📦 حجم الملف يتجاوز {config.MAX_FILE_SIZE_MB}MB\n\n"
                f"{caption}\n\n"
                f"🔗 رابط التحميل المباشر:"
            ),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )