"""
وحدة التواصل مع GitHub API
يدعم: البحث عن المستودعات، جلب معلومات المستودع، جلب الإصدارات
"""
import logging
import httpx
from bot.config import config

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"


def _headers(token: str | None = None) -> dict:
    """تجهيز رأس الطلبات"""
    h = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "GitHubStoreBot/2.0",
    }
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


# ──────────────────────────────────────────────
# التحقق من صلاحية التوكن
# ──────────────────────────────────────────────

async def validate_token(token: str) -> dict:
    """
    التحقق من صلاحية توكن GitHub
    Returns: {"valid": True, "login": "..."} أو {"valid": False, "error": "..."}
    """
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{GITHUB_API_BASE}/user",
                headers=_headers(token),
                timeout=10.0,
            )
            if r.status_code == 200:
                data = r.json()
                return {"valid": True, "login": data.get("login", "unknown")}
            elif r.status_code == 401:
                return {"valid": False, "error": "التوكن غير صالح أو منتهي الصلاحية."}
            else:
                return {"valid": False, "error": f"خطأ في التحقق (كود: {r.status_code})."}
    except Exception as e:
        logger.error(f"Token validation error: {e}")
        return {"valid": False, "error": "خطأ في الاتصال أثناء التحقق من التوكن."}


# ──────────────────────────────────────────────
# البحث عن المستودعات
# ──────────────────────────────────────────────

async def search_repos(query: str, token: str | None = None) -> dict:
    """
    البحث في مستودعات GitHub باستخدام GitHub Search API
    يبحث عن المستودعات التي تحتوي على Releases فقط

    Returns:
        {"results": [...]} أو {"error": "..."}
    """
    # إذا كان الإدخال يحتوي على / فهو مسار مستودع مباشر
    if "/" in query and not query.startswith("http") and "." not in query.split("/")[0]:
        return await fetch_repo_info(query.strip(), token)

    # إذا كان رابط كامل
    if "github.com/" in query:
        from urllib.parse import urlparse
        path = urlparse(query).path
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 2:
            return await fetch_repo_info(f"{parts[0]}/{parts[1]}", token)

    # بحث باستخدام GitHub Search API
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{GITHUB_API_BASE}/search/repositories",
                params={
                    "q": f"{query} in:name",
                    "sort": "stars",
                    "order": "desc",
                    "per_page": 8,
                },
                headers=_headers(token),
                timeout=config.GITHUB_API_TIMEOUT,
            )

            if r.status_code == 403:
                return {"error": "تم تجاوز حد طلبات GitHub. استخدم /login لرفع الحد."}
            if r.status_code != 200:
                return {"error": f"خطأ في البحث (كود: {r.status_code})."}

            data = r.json()
            items = data.get("items", [])

            if not items:
                return {"error": f"لم يتم العثور على مستودعات تطابق \"{query}\"."}

            # فلترة: المستودعات التي تحتوي على releases فقط
            results = []
            for repo in items:
                full_name = repo["full_name"]
                has_releases = await _check_has_releases(full_name, token)
                if has_releases:
                    results.append({
                        "full_name": full_name,
                        "description": (repo.get("description") or "لا يوجد وصف")[:120],
                        "stars": repo.get("stargazers_count", 0),
                        "forks": repo.get("forks_count", 0),
                        "language": repo.get("language") or "",
                        "updated_at": repo.get("updated_at", "")[:10],
                    })
                if len(results) >= 5:
                    break

            if not results:
                return {"error": f"لم يتم العثور على مستودعات تحتوي على إصدارات (Releases) تطابق \"{query}\"."}

            return {"results": results}

    except httpx.TimeoutException:
        return {"error": "انتهت مهلة الاتصال بـ GitHub. يرجى المحاولة لاحقاً."}
    except Exception as e:
        logger.error(f"Search error: {e}")
        return {"error": "خطأ في الاتصال أثناء البحث."}


async def _check_has_releases(repo_path: str, token: str | None = None) -> bool:
    """التحقق السريع مما إذا كان المستودع يحتوي على releases"""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.head(
                f"{GITHUB_API_BASE}/repos/{repo_path}/releases",
                headers=_headers(token),
                timeout=8.0,
            )
            return r.status_code == 200
    except Exception:
        return False


# ──────────────────────────────────────────────
# جلب معلومات المستودع
# ──────────────────────────────────────────────

async def fetch_repo_info(repo_path: str, token: str | None = None) -> dict:
    """
    جلب معلومات مستودع محدد + قائمة إصداراته

    Returns:
        {"repo": {...}, "releases": [...]} أو {"error": "..."}
    """
    try:
        async with httpx.AsyncClient() as client:
            # جلب معلومات المستودع
            r = await client.get(
                f"{GITHUB_API_BASE}/repos/{repo_path}",
                headers=_headers(token),
                timeout=config.GITHUB_API_TIMEOUT,
            )
            if r.status_code == 404:
                return {"error": f"المستودع `{repo_path}` غير موجود."}
            if r.status_code == 403:
                return {"error": "تم تجاوز حد طلبات GitHub. استخدم /login لرفع الحد."}
            if r.status_code != 200:
                return {"error": f"خطأ في جلب المستودع (كود: {r.status_code})."}

            repo = r.json()
            repo_info = {
                "full_name": repo["full_name"],
                "description": (repo.get("description") or "لا يوجد وصف")[:200],
                "stars": repo.get("stargazers_count", 0),
                "forks": repo.get("forks_count", 0),
                "language": repo.get("language") or "",
                "topics": repo.get("topics", [])[:5],
                "license": (repo.get("license") or {}).get("spdx_id", ""),
                "html_url": repo.get("html_url", ""),
            }

            # جلب الإصدارات
            releases = await fetch_releases(repo_path, token)
            if "error" in releases:
                return {"error": releases["error"]}

            return {"repo": repo_info, "releases": releases["releases"]}

    except httpx.TimeoutException:
        return {"error": "انتهت مهلة الاتصال بـ GitHub."}
    except Exception as e:
        logger.error(f"Fetch repo error for {repo_path}: {e}")
        return {"error": "خطأ في الاتصال أثناء جلب المستودع."}


# ──────────────────────────────────────────────
# جلب إصدارات المستودع
# ──────────────────────────────────────────────

async def fetch_releases(repo_path: str, token: str | None = None) -> dict:
    """
    جلب قائمة الإصدارات (آخر 10 إصدارات)

    Returns:
        {"releases": [...]} أو {"error": "..."}
    """
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{GITHUB_API_BASE}/repos/{repo_path}/releases",
                params={"per_page": 10},
                headers=_headers(token),
                timeout=config.GITHUB_API_TIMEOUT,
            )
            if r.status_code != 200:
                return {"error": "لم يتم العثور على إصدارات."}

            releases = []
            for rel in r.json():
                assets = []
                for a in rel.get("assets", []):
                    assets.append({
                        "name": a["name"],
                        "size": a["size"],
                        "download_url": a["browser_download_url"],
                        "download_count": a.get("download_count", 0),
                    })

                releases.append({
                    "tag_name": rel.get("tag_name", ""),
                    "name": rel.get("name", "") or rel.get("tag_name", ""),
                    "body": (rel.get("body") or "لا يوجد وصف.")[:300],
                    "prerelease": rel.get("prerelease", False),
                    "published_at": (rel.get("published_at", "")[:10]),
                    "assets": assets,
                })

            if not releases:
                return {"error": "لا يوجد إصدارات متاحة لهذا المستودع."}

            return {"releases": releases}

    except httpx.TimeoutException:
        return {"error": "انتهت مهلة الاتصال بـ GitHub."}
    except Exception as e:
        logger.error(f"Fetch releases error for {repo_path}: {e}")
        return {"error": "خطأ في جلب الإصدارات."}


# ──────────────────────────────────────────────
# تحميل ملف
# ──────────────────────────────────────────────

async def download_file(url: str, token: str | None = None, expected_size: int = 0) -> bytes | None:
    """
    تحميل ملف من رابط لرفعه كوثيقة في التليجرام.
    التايم أوت ديناميكي حسب حجم الملف المتوقع:
      - أقل من 10MB  → 60 ثانية
      - 10-50MB      → 180 ثانية
      - 50-100MB     → 300 ثانية
      - أكبر من 100MB → 600 ثانية (10 دقائق)
    """
    # حساب التايم أوت ديناميكياً
    if expected_size >= 100 * 1024 * 1024:
        timeout = 600.0
    elif expected_size >= 50 * 1024 * 1024:
        timeout = 300.0
    elif expected_size >= 10 * 1024 * 1024:
        timeout = 180.0
    else:
        timeout = 60.0

    try:
        headers = {"User-Agent": "GitHubStoreBot/2.0"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        async with httpx.AsyncClient(follow_redirects=True) as client:
            r = await client.get(url, headers=headers, timeout=timeout)
            if r.status_code == 200:
                return r.content
            logger.warning(f"Download returned status {r.status_code} for {url}")
            return None
    except httpx.TimeoutException:
        logger.error(f"Download timed out ({timeout}s) for {url}")
        return None
    except Exception as e:
        logger.error(f"Download error from {url}: {e}")
        return None


# ──────────────────────────────────────────────
# مساعدات
# ──────────────────────────────────────────────

def format_size(size_bytes: int) -> str:
    """تحويل حجم البايت إلى صيغة مقروءة"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def format_number(n: int) -> str:
    """تحويل الأرقام الكبيرة إلى صيغة مقروءة"""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    elif n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)