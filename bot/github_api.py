"""
وحدة التواصل مع GitHub API
"""
import logging
import httpx
from bot.config import config

logger = logging.getLogger(__name__)

GITHUB_API_URL = "https://api.github.com/repos/{repo_path}/releases/latest"


async def fetch_latest_release(repo_path: str, token: str | None = None) -> dict:
    """
    جلب أحدث إصدار (Release) من مستودع GitHub

    Args:
        repo_path: مسار المستودع (مثال: "owner/repo")
        token: توكن GitHub اختياري لرفع حد الطلبات

    Returns:
        dict: بيانات الإصدار أو dict يحتوي على مفتاح "error"
    """
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "GitHubStoreBot/1.0"}
    if token:
        headers["Authorization"] = f"token {token}"

    url = GITHUB_API_URL.format(repo_path=repo_path)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=config.GITHUB_API_TIMEOUT)

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                return {"error": "المستودع غير موجود أو لا يحتوي على إصدارات (Releases)."}
            elif response.status_code == 403:
                return {"error": "تم تجاوز حد الطلبات لـ GitHub. يرجى ربط حسابك عبر /login لتفادي هذا."}
            else:
                return {"error": f"حدث خطأ أثناء التواصل مع GitHub (كود: {response.status_code})."}

    except httpx.TimeoutException:
        logger.error(f"Timeout while fetching release for {repo_path}")
        return {"error": "انتهت مهلة الاتصال بـ GitHub. يرجى المحاولة لاحقاً."}
    except httpx.RequestError as e:
        logger.error(f"Request error for {repo_path}: {e}")
        return {"error": "خطأ في الاتصال بالشبكة أثناء التواصل مع GitHub."}


async def download_file(url: str) -> bytes | None:
    """
    تحميل ملف من رابط (لرفعه مباشرة كوثيقة في التليجرام)

    Args:
        url: رابط التحميل المباشر

    Returns:
        محتوى الملف كـ bytes أو None في حال الفشل
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=60.0)
            if response.status_code == 200:
                return response.content
            return None
    except Exception as e:
        logger.error(f"Error downloading file from {url}: {e}")
        return None


# امتدادات الملفات حسب نظام التشغيل
OS_EXTENSIONS = {
    "android": [".apk", ".xapk"],
    "linux": [".deb", ".appimage", ".sh", ".tar.gz", ".rpm"],
    "windows": [".exe", ".msi", ".zip"],
    "macos": [".dmg", ".pkg", ".zip"],
}

OS_LABELS = {
    "android": "Android",
    "linux": "Linux",
    "windows": "Windows",
    "macos": "macOS",
}


def filter_assets_by_os(assets: list, os_choice: str) -> list:
    """فلترة ملفات Release حسب نظام التشغيل المختار"""
    target_exts = OS_EXTENSIONS.get(os_choice, [])
    filtered = []
    for asset in assets:
        name_lower = asset["name"].lower()
        if any(name_lower.endswith(ext) for ext in target_exts):
            filtered.append(asset)
    return filtered