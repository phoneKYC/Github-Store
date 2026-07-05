"""
معالجات أوامر /start و /help
"""
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def start(update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """رسالة الترحيب الرئيسية"""
    user = update.effective_user
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

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
        disable_web_page_preview=True,
    )


async def help_command(update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """دليل الاستخدام - يُرسل كرسالة ثابتة"""
    text = (
        "📖 *دليل الاستخدام الكامل:*\n\n"
        "🔍 *البحث عن التطبيقات:*\n"
        "• `/search termux` — بحث بالاسم\n"
        "• `/search termux/termux-app` — بحث بالمسار\n"
        "• `/search https://github.com/...` — بحث بالرابط\n\n"
        "📱 *رحلة التحميل:*\n"
        "1️⃣ ابحث عن التطبيق\n"
        "2️⃣ اختر المستودع من النتائج\n"
        "3️⃣ اختر الإصدار المطلوب\n"
        "4️⃣ اختر الملف المناسب لنظامك\n"
        "5️⃣ يتم إرساله لك مباشرة! 🎉\n\n"
        "🔑 *ربط حساب GitHub:*\n"
        "• `/login ghp_xxx` — ربط (مع التحقق الفوري)\n"
        "• `/logout` — إلغاء الربط\n"
        "• /login بدون توكن لعرض حالتك الحالية\n\n"
        "💡 *ملاحظة:* الربط يرفع حد الطلبات من 10 إلى 5000/ساعة"
    )

    keyboard = [
        [InlineKeyboardButton("🔙 رجوع", callback_data="action_back_home")],
    ]

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
            disable_web_page_preview=True,
        )
    else:
        await update.message.reply_text(
            text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
            disable_web_page_preview=True,
        )