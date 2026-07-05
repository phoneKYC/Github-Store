"""
معالجات البحث الكاملة - UX بأزرار شفافة ورسائل ذاتية التحديث
الرحلة: بحث ← نتائج مستودعات ← اختيار مستودع ← قائمة إصدارات ← اختيار نظام التشغيل ← قائمة ملفات ← تحميل
"""
import logging
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.crypto import decrypt_token
from bot.database import get_user_token, ensure_user_exists, log_search, log_download
from bot.github_api import (
    search_repos,
    fetch_repo_info,
    download_file,
    format_size,
    format_number,
)
from bot.config import config

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# خريطة أنظمة التشغيل للفلترة
# ──────────────────────────────────────────────

OS_PATTERNS = {
    "linux": [
        r"linux", r"\.deb", r"\.rpm", r"\.AppImage", r"\.appimage",
        r"\.tar\.gz", r"\.tar\.xz", r"\.tar\.bz2", r"ubuntu",
        r"fedora", r"arch", r"linux-gnu", r"linux-musl",
    ],
    "windows": [
        r"windows", r"win", r"\.exe", r"\.msi", r"\.msix",
        r"\.zip", r"\.portable", r"win64", r"win32",
    ],
    "android": [
        r"android", r"\.apk", r"arm64-v8a", r"armeabi-v7a",
        r"arm64", r"armv7", r"aarch64-android",
    ],
    "macos": [
        r"macos", r"mac", r"darwin", r"osx", r"\.dmg",
        r"\.pkg", r"mac-os", r"macos-arm64", r"macos-x86",
    ],
}

OS_ICONS = {
    "linux": "🐧",
    "windows": "🪟",
    "android": "🤖",
    "macos": "🍎",
}

OS_NAMES = {
    "linux": "Linux",
    "windows": "Windows",
    "android": "Android",
    "macos": "macOS",
}


async def _get_user_token(user_id: int) -> str | None:
    """جلب توكن المستخدم إذا موجود"""
    encrypted = await get_user_token(user_id)
    if encrypted:
        try:
            return decrypt_token(encrypted)
        except Exception:
            pass
    return None


def _match_os(asset_name: str) -> str | None:
    """تحديد نظام التشغيل المناسب للملف بناءً على اسمه"""
    name_lower = asset_name.lower()
    for os_key, patterns in OS_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, name_lower, re.IGNORECASE):
                return os_key
    return None


def _filter_assets_by_os(assets: list, os_key: str) -> list:
    """فلترة الملفات حسب نظام التشغيل"""
    patterns = OS_PATTERNS.get(os_key, [])
    filtered = []
    for asset in assets:
        name_lower = asset["name"].lower()
        for pattern in patterns:
            if re.search(pattern, name_lower, re.IGNORECASE):
                filtered.append(asset)
                break
    return filtered


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
    user_id = update.effective_user.id

    # تسجيل النشاط
    await ensure_user_exists(user_id)

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
        await log_search(user_id, query, status="error")
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
        await log_search(user_id, query, result["repo"]["full_name"])
        await _show_releases(
            context, chat_id, message_id,
            result["repo"], result["releases"], token
        )
        return

    # ── نتائج متعددة ──
    await log_search(user_id, query, status="success")
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
# المرحلة 3: اختيار مستودع ← عرض الإصدارات
# ──────────────────────────────────────────────

async def show_repo_releases(update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """يُستدعى عند اختيار مستودع من نتائج البحث"""
    query_cb = update.callback_query
    await query_cb.answer()

    repo_full_name = query_cb.data.replace("repo_", "")
    chat_id = query_cb.message.chat_id
    message_id = query_cb.message.message_id
    user_id = query_cb.from_user.id

    context.user_data["selected_repo"] = repo_full_name

    # تحديث الرسالة: جاري التحميل
    await query_cb.edit_message_text(
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
# المرحلة 4: اختيار إصدار ← اختيار نظام التشغيل
# ──────────────────────────────────────────────

async def show_release_assets(update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """يُستدعى عند اختيار إصدار معين - يعرض اختيار نظام التشغيل أولاً"""
    query_cb = update.callback_query
    await query_cb.answer()

    idx = int(query_cb.data.replace("rel_", ""))

    releases = context.user_data.get("releases", [])
    if idx >= len(releases):
        await query_cb.answer("❌ الإصدار غير موجود", show_alert=True)
        return

    rel = releases[idx]
    assets = rel.get("assets", [])

    # حفظ الإصدار المختار
    context.user_data["current_release"] = rel
    context.user_data["current_assets"] = assets
    context.user_data["current_release_idx"] = idx

    if not assets:
        repo_name = context.user_data.get("selected_repo", "")
        await query_cb.edit_message_text(
            f"⚠️ لا توجد ملفات تحميل في هذا الإصدار.\n\n"
            f"🏷️ الإصدار: `{rel['tag_name']}`\n"
            f"📦 المستودع: `{repo_name}`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 رجوع للإصدارات", callback_data="back_to_releases")],
            ]),
        )
        return

    # عرض اختيار نظام التشغيل
    await _show_os_selection(query_cb, context, rel)


async def _show_os_selection(query_cb, context: ContextTypes.DEFAULT_TYPE, rel: dict) -> None:
    """عرض أزرار اختيار نظام التشغيل لفلترة الملفات"""
    repo_name = context.user_data.get("selected_repo", "")
    assets = context.user_data.get("current_assets", [])
    total_assets = len(assets)

    # حساب عدد الملفات لكل نظام
    os_counts = {"linux": 0, "windows": 0, "android": 0, "macos": 0}
    unmatched = 0
    for asset in assets:
        matched = _match_os(asset["name"])
        if matched:
            os_counts[matched] += 1
        else:
            unmatched += 1

    text = (
        f"📦 *{repo_name}*\n"
        f"🏷️ الإصدار: `{rel['tag_name']}`\n\n"
        f"📊 *اختر نظام التشغيل لفلترة الملفات:*\n"
        f"📂 إجمالي الملفات: {total_assets}\n\n"
    )

    # عرض عدد الملفات لكل نظام
    for os_key in ["linux", "windows", "android", "macos"]:
        icon = OS_ICONS[os_key]
        name = OS_NAMES[os_key]
        count = os_counts[os_key]
        text += f"{icon} {name}: {count} ملف\n"

    if unmatched > 0:
        text += f"📁 أخرى: {unmatched} ملف\n"

    buttons = [
        [
            InlineKeyboardButton(f"🐧 Linux ({os_counts['linux']})", callback_data="os_linux"),
            InlineKeyboardButton(f"🪟 Windows ({os_counts['windows']})", callback_data="os_windows"),
        ],
        [
            InlineKeyboardButton(f"🤖 Android ({os_counts['android']})", callback_data="os_android"),
            InlineKeyboardButton(f"🍎 macOS ({os_counts['macos']})", callback_data="os_macos"),
        ],
        [
            InlineKeyboardButton(f"📁 عرض الكل ({total_assets})", callback_data="os_all"),
        ],
        [InlineKeyboardButton("🔙 رجوع للإصدارات", callback_data="back_to_releases")],
    ]

    await query_cb.edit_message_text(
        text=text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# ──────────────────────────────────────────────
# المرحلة 5: عرض الملفات المفلترة حسب نظام التشغيل
# ──────────────────────────────────────────────

async def show_os_filtered_assets(update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """عرض الملفات بعد اختيار نظام التشغيل"""
    query_cb = update.callback_query
    await query_cb.answer()

    os_key = query_cb.data.replace("os_", "")

    assets = context.user_data.get("current_assets", [])
    repo_name = context.user_data.get("selected_repo", "")
    rel = context.user_data.get("current_release", {})
    tag = rel.get("tag_name", "")

    # فلترة الملفات
    if os_key == "all":
        filtered_assets = assets
        os_label = "الكل"
    else:
        filtered_assets = _filter_assets_by_os(assets, os_key)
        os_label = f"{OS_ICONS.get(os_key, '')} {OS_NAMES.get(os_key, os_key)}"

    if not filtered_assets:
        # لا توجد ملفات تطابق النظام المختار
        buttons = [
            [
                InlineKeyboardButton("📁 عرض الكل", callback_data="os_all"),
                InlineKeyboardButton("🔙 رجوع للإصدارات", callback_data="back_to_releases"),
            ],
        ]
        await query_cb.edit_message_text(
            text=(
                f"⚠️ لا توجد ملفات متوافقة مع *{os_label}*\n"
                f"في هذا الإصدار.\n\n"
                f"📦 `{repo_name}` — `{tag}`\n\n"
                f"💡 جرب اختيار نظام آخر أو اضغط \"عرض الكل\""
            ),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return

    # حفظ الملفات المفلترة
    context.user_data["filtered_assets"] = filtered_assets

    body = rel.get("body", "") or "لا يوجد وصف"
    body = body[:250]

    text = (
        f"📦 *{repo_name}*\n"
        f"🏷️ الإصدار: `{tag}`  |  {os_label}\n\n"
        f"📝 *موجز التغييرات:*\n_{body}_\n\n"
        f"📂 *الملفات المتاحة* ({len(filtered_assets)}):\n"
    )

    buttons = []
    for i, asset in enumerate(filtered_assets):
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

    buttons.append([
        InlineKeyboardButton("🔙 تغيير النظام", callback_data="os_back_to_selection"),
        InlineKeyboardButton("🔙 رجوع للإصدارات", callback_data="back_to_releases"),
    ])

    await query_cb.edit_message_text(
        text=text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
        disable_web_page_preview=True,
    )


# ──────────────────────────────────────────────
# المرحلة 6: تحميل الملف
# ──────────────────────────────────────────────

async def download_asset(update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """تحميل ملف محدد وإرساله أو إرسال رابط مباشر كزر شفاف عند الفشل"""
    query_cb = update.callback_query
    await query_cb.answer("⬇️ جاري تجهيز الملف...")

    idx = int(query_cb.data.replace("dl_", ""))
    chat_id = query_cb.message.chat_id
    message_id = query_cb.message.message_id
    user_id = query_cb.from_user.id

    # استخدام الملفات المفلترة (filtered_assets) إن وجدت، وإلا current_assets
    assets = context.user_data.get("filtered_assets") or context.user_data.get("current_assets", [])
    if idx >= len(assets):
        await query_cb.answer("❌ الملف غير موجود", show_alert=True)
        return

    asset = assets[idx]
    name = asset["name"]
    url = asset["download_url"]
    size_bytes = asset["size"]

    repo_name = context.user_data.get("selected_repo", "")
    rel = context.user_data.get("current_release", {})
    tag = rel.get("tag_name", "")

    caption = (
        f"📦 *{repo_name}*\n"
        f"🏷️ `{tag}`\n"
        f"📄 `{name}`\n"
        f"📊 {format_size(size_bytes)}"
    )

    # أزرار الرجوع والرابط المباشر (تُستخدم في كل الحالات)
    def _make_result_keyboard():
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 رابط تحميل مباشر", url=url)],
            [InlineKeyboardButton("🔙 رجوع للملفات", callback_data="back_to_assets")],
        ])

    def _make_error_keyboard():
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 تحميل مباشر من GitHub", url=url)],
            [InlineKeyboardButton("🔙 رجوع للملفات", callback_data="back_to_assets")],
        ])

    # دالة آمنة لتحديث الرسالة — إذا فشل التعديل، ترسل رسالة جديدة
    async def _safe_edit_or_send(text: str, keyboard: InlineKeyboardMarkup) -> None:
        try:
            await query_cb.edit_message_text(
                text=text, parse_mode="Markdown",
                reply_markup=keyboard,
            )
        except Exception:
            # Callback قد انتهى صلاحيته ← نرسل رسالة جديدة
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=text, parse_mode="Markdown",
                    reply_markup=keyboard,
                )
            except Exception as send_err:
                logger.error(f"Failed to send fallback message: {send_err}")

    # تحديث الرسالة: جاري التحميل
    await _safe_edit_or_send(
        f"⬇️ جاري تحميل `{name}`...\n"
        f"📊 الحجم: {format_size(size_bytes)}\n\n"
        f"⏳ يرجى الانتظار...",
        InlineKeyboardMarkup([]),
    )

    token = await _get_user_token(user_id)
    max_size = config.MAX_FILE_SIZE_MB * 1024 * 1024

    if size_bytes > max_size:
        # ملف كبير ← رابط مباشر فقط
        await log_download(user_id, repo_name, tag, name, size_bytes, "link")
        await _safe_edit_or_send(
            text=(
                f"📦 حجم الملف يتجاوز {config.MAX_FILE_SIZE_MB}MB\n\n"
                f"{caption}\n\n"
                f"🔗 رابط التحميل المباشر:"
            ),
            keyboard=_make_result_keyboard(),
        )
        return

    # محاولة التحميل والرفع كوثيقة
    try:
        await context.bot.send_chat_action(chat_id=chat_id, action="upload_document")
        file_content = await download_file(url, token, expected_size=size_bytes)

        if file_content:
            await log_download(user_id, repo_name, tag, name, size_bytes, "document")
            await context.bot.send_document(
                chat_id=chat_id,
                document=file_content,
                filename=name,
                caption=caption,
                parse_mode="Markdown",
            )
            # تحديث الرسالة الأصلية
            await _safe_edit_or_send(
                text=f"✅ تم إرسال `{name}` بنجاح!",
                keyboard=_make_result_keyboard(),
            )
        else:
            # فشل التحميل ← رسالة مع زر شفاف يحتوي الرابط المباشر
            await log_download(user_id, repo_name, tag, name, size_bytes, "link", "download_failed")
            await _safe_edit_or_send(
                text=(
                    f"⚠️ تعذر تحميل الملف من GitHub.\n\n"
                    f"{caption}\n\n"
                    f"🔗 اضغط الزر أدناه للتحميل المباشر:"
                ),
                keyboard=_make_error_keyboard(),
            )
    except Exception as e:
        logger.error(f"Upload error for {name}: {e}")
        await log_download(user_id, repo_name, tag, name, size_bytes, "link", "upload_error")
        # فشل الرفع ← رسالة مع زر شفاف يحتوي الرابط المباشر
        await _safe_edit_or_send(
            text=(
                f"⚠️ حدث خطأ أثناء رفع الملف.\n\n"
                f"{caption}\n\n"
                f"🔗 يمكنك التحميل مباشرة عبر الزر أدناه:"
            ),
            keyboard=_make_error_keyboard(),
        )


# ──────────────────────────────────────────────
# معالجات الرجوع (Back handlers)
# ──────────────────────────────────────────────

async def back_to_releases(update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """الرجوع لعرض قائمة الإصدارات من أي مرحلة لاحقة"""
    query_cb = update.callback_query
    await query_cb.answer()

    repo_full_name = context.user_data.get("selected_repo", "")
    if not repo_full_name:
        await query_cb.edit_message_text(
            "❌ لم يتم تحديد مستودع.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 بحث جديد", callback_data="action_search")],
            ]),
        )
        return

    # جلب معلومات المستودع والإصدارات من جديد
    token = await _get_user_token(query_cb.from_user.id)
    result = await fetch_repo_info(repo_full_name, token)

    if "error" in result:
        await query_cb.edit_message_text(
            f"❌ {result['error']}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 بحث جديد", callback_data="action_search"),
                 InlineKeyboardButton("🔙 رجوع", callback_data="action_back_home")],
            ]),
        )
        return

    chat_id = query_cb.message.chat_id
    message_id = query_cb.message.message_id

    await _show_releases(context, chat_id, message_id,
                         result["repo"], result["releases"], token)


async def back_to_assets(update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """الرجوع لعرض قائمة الملفات المفلترة"""
    query_cb = update.callback_query
    await query_cb.answer()

    # إعادة عرض الملفات بنفس الفلترة السابقة
    # نستخدم os_all أو نعيد عرض الاختيار
    filtered_assets = context.user_data.get("filtered_assets", [])
    if not filtered_assets:
        # لا توجد ملفات مفلترة ← نرجع لاختيار النظام
        rel = context.user_data.get("current_release", {})
        await _show_os_selection(query_cb, context, rel)
        return

    # إعادة عرض الملفات المفلترة
    assets = context.user_data.get("current_assets", [])
    filtered_assets = context.user_data.get("filtered_assets", [])
    repo_name = context.user_data.get("selected_repo", "")
    rel = context.user_data.get("current_release", {})
    tag = rel.get("tag_name", "")

    # تحديد أي نظام كان مُختاراً
    os_label = "📁 الكل"
    for os_key, patterns in OS_PATTERNS.items():
        test_filtered = _filter_assets_by_os(assets, os_key)
        if test_filtered == filtered_assets:
            os_label = f"{OS_ICONS[os_key]} {OS_NAMES[os_key]}"
            break

    body = rel.get("body", "") or "لا يوجد وصف"
    body = body[:250]

    text = (
        f"📦 *{repo_name}*\n"
        f"🏷️ الإصدار: `{tag}`  |  {os_label}\n\n"
        f"📝 *موجز التغييرات:*\n_{body}_\n\n"
        f"📂 *الملفات المتاحة* ({len(filtered_assets)}):\n"
    )

    buttons = []
    for i, asset in enumerate(filtered_assets):
        size_str = format_size(asset["size"])
        dl_str = f"  |  ⬇️ {format_number(asset.get('download_count', 0))}" if asset.get("download_count") else ""
        text += f"\n{i+1}. `{asset['name']}`  —  {size_str}{dl_str}"

        name = asset["name"]
        if len(name) > 35:
            name = name[:32] + "..."
        buttons.append([InlineKeyboardButton(
            f"📥 {name} ({size_str})",
            callback_data=f"dl_{i}",
        )])

    buttons.append([
        InlineKeyboardButton("🔙 تغيير النظام", callback_data="os_back_to_selection"),
        InlineKeyboardButton("🔙 رجوع للإصدارات", callback_data="back_to_releases"),
    ])

    await query_cb.edit_message_text(
        text=text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
        disable_web_page_preview=True,
    )


async def back_to_os_selection(update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """الرجوع لشاشة اختيار نظام التشغيل"""
    query_cb = update.callback_query
    await query_cb.answer()

    rel = context.user_data.get("current_release", {})
    if not rel:
        await query_cb.edit_message_text(
            "❌ لم يتم تحديد إصدار.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 رجوع", callback_data="action_back_home")],
            ]),
        )
        return

    await _show_os_selection(query_cb, context, rel)