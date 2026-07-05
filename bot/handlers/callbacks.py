"""
معالجات الأزرار الشفافة (Callback Query Handlers)
توجيه جميع النقرات إلى المعالج المناسب
"""
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.handlers.auth import login, logout

logger = logging.getLogger(__name__)


async def button_router(update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """الموجّه الرئيسي لجميع الأزرار الشفافة"""
    query = update.callback_query
    data = query.data

    # ── أزرار القائمة الرئيسية ──
    if data == "action_search":
        await query.answer()
        await query.edit_message_text(
            "🔍 *البحث عن تطبيق*\n\n"
            "أرسل اسم التطبيق أو المستودع:\n"
            "`/search اسم التطبيق`\n\n"
            "💡 أمثلة:\n"
            "• `/search termux`\n"
            "• `/search owner/repo`\n"
            "• `https://github.com/owner/repo`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 رجوع", callback_data="action_back_home")],
            ]),
        )

    elif data == "action_account":
        # عرض حالة الحساب بدون إدخال توكن
        await query.answer()
        context.args = []
        await login(update, context)

    elif data == "action_help":
        from bot.handlers.commands import help_command
        await help_command(update, context)

    elif data == "action_change_token":
        await query.answer()
        await query.edit_message_text(
            "🔑 *تحديث توكن GitHub*\n\n"
            "أرسل التوكن الجديد:\n`/login ghp_your_token`\n\n"
            "أو ألغِ الربط: `/logout`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 رجوع", callback_data="action_back_home")],
            ]),
        )

    elif data == "action_back_home":
        await query.answer()
        await _show_home(query, context)

    # ── أزرار نتائج البحث ──
    elif data.startswith("repo_"):
        from bot.handlers.search import show_repo_releases
        await show_repo_releases(update, context)

    # ── أزرار الإصدارات ──
    elif data.startswith("rel_"):
        from bot.handlers.search import show_release_assets
        await show_release_assets(update, context)

    # ── أزرار التحميل ──
    elif data.startswith("dl_"):
        from bot.handlers.search import download_asset
        await download_asset(update, context)

    # ── أزرار الرجوع ──
    elif data == "back_to_releases":
        from bot.handlers.search import show_repo_releases
        # إعادة عرض الإصدارات عن طريق تغيير callback_data مؤقتاً
        original_data = update.callback_query.data
        update.callback_query.data = f"repo_{context.user_data.get('selected_repo', '')}"
        await show_repo_releases(update, context)
        update.callback_query.data = original_data

    elif data == "back_to_assets":
        from bot.handlers.search import show_release_assets
        releases = context.user_data.get("releases", [])
        current_rel = context.user_data.get("current_release", {})
        tag = current_rel.get("tag_name", "")
        idx = next((i for i, r in enumerate(releases) if r["tag_name"] == tag), 0)
        original_data = update.callback_query.data
        update.callback_query.data = f"rel_{idx}"
        await show_release_assets(update, context)
        update.callback_query.data = original_data


async def _show_home(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """إعادة عرض القائمة الرئيسية في نفس الرسالة"""
    from bot.handlers.commands import start
    # تعديل الرسالة الحالية لتبدو كرسالة الترحيب
    user = query.from_user
    name = user.first_name or "صديقي"

    text = (
        f"┏━━━━━━━━━━━━━━━━━━━━━━━┓\n"
        f"┃  🏪  GitHub Store Bot  ┃\n"
        f"┗━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        f"مرحباً {name}! 👋\n\n"
        f"بوتك لاستكشاف وتحميل التطبيقات مفتوحة المصدر\n"
        f"مباشرة من مستودعات GitHub بسهولة وسرعة.\n\n"
        f"💡 *فكرة المشروع مستوحاة ومطوّرة بفضل*\n"
        f"[Komi Store](https://github.com/kurikomi-labs/komi-store) "
        f"و [OpenHub Store](https://github.com/OpenHub-Store/GitHub-Store)\n\n"
        f"🤝 *شكر خاص لفريق* [kurikomi-labs](https://github.com/kurikomi-labs)\n"
        f"*على إلهامهم الرائع وإسهاماتهم القيّمة في عالم البرمجيات المفتوحة.*\n\n"
        f"🛠️ التطوير: [@IIDZII]"
    )

    keyboard = [
        [
            InlineKeyboardButton("🔍 بحث", callback_data="action_search"),
            InlineKeyboardButton("👤 حسابي", callback_data="action_account"),
        ],
        [
            InlineKeyboardButton("📖 دليل الاستخدام", callback_data="action_help"),
            InlineKeyboardButton("🔄 تغيير التوكن", callback_data="action_change_token"),
        ],
    ]

    await query.edit_message_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
        disable_web_page_preview=True,
    )