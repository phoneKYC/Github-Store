"""
معالجات أوامر التليجرام (Command Handlers)
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.config import config

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """رسالة الترحيب عند بدء المحادثة مع البوت"""
    user = update.effective_user

    welcome_text = (
        f"✨ *مرحباً بك يا {user.first_name} في بوت متجر GitHub!* ✨\n\n"
        f"🤖 يتيح لك هذا البوت البحث عن البرمجيات والتطبيقات مفتوحة المصدر "
        f"مباشرة من مستودعات GitHub وتحميل إصداراتها فوراً.\n\n"
        f"💡 *فكرة المشروع مستوحاة من:* "
        f"[OpenHub-Store/GitHub-Store](https://github.com/OpenHub-Store/GitHub-Store)\n\n"
        f"🛠️ *تطوير وبناء:* [@IIDZII]\n\n"
        f"اضغط على /help لمعرفة كيفية الاستخدام وبدء البحث!"
    )

    keyboard = [
        [InlineKeyboardButton("🔍 ابدأ البحث المباشر", callback_data="prompt_search")],
        [InlineKeyboardButton("🔑 ربط حساب GitHub", callback_data="prompt_login")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        welcome_text,
        parse_mode="Markdown",
        reply_markup=reply_markup,
        disable_web_page_preview=True,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """دليل الاستخدام"""
    help_text = (
        "📖 *دليل استخدام البوت وميزاته:*\n\n"
        "🔍 *البحث عن التطبيقات:*\n"
        "استخدم أمر `/search` متبوعاً باسم المستودع أو الرابط بالكامل.\n"
        "💡 _أمثلة:_\n"
        "• `/search termux/termux-app`\n"
        "• `/search https://github.com/PicoCrypt/PicoCrypt`\n\n"
        "⚙️ *تحديد نظام التشغيل:*\n"
        "بعد البحث، ستظهر لك أزرار تفاعلية لاختيار نظام التشغيل المستهدف "
        "(Android, Linux, Windows, macOS).\n\n"
        "📤 *الموازنة الذكية للملفات:*\n"
        f"• إذا كان حجم حزمة التثبيت *أقل من {config.MAX_FILE_SIZE_MB} ميجابايت*، "
        "سيقوم البوت برفعها وإرسالها لك مباشرة كملف وثيقة.\n"
        f"• إذا كان الحجم *أكبر من {config.MAX_FILE_SIZE_MB} ميجابايت*، "
        "سيرسل لك البوت رابط تحميل مباشر من سيرفرات GitHub الرسمية.\n\n"
        "🔑 *تخطي قيود الطلبات (Rate Limits):*\n"
        "لتفادي قيود الـ API الخاصة بـ GitHub، ربط حسابك بواسطة:\n"
        "• `/login YOUR_GITHUB_TOKEN`\n"
        "• `/logout` لإلغاء الربط\n"
        "_(يتم تشفير الرمز الخاص بك تلقائياً لحمايته وأمانه)._"
    )

    await update.message.reply_text(
        help_text, parse_mode="Markdown", disable_web_page_preview=True
    )