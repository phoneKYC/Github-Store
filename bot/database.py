"""
وحدة قاعدة البيانات - إدارة الجداول والعمليات المتعلقة بالمستخدمين والإحصائيات
الأمان: جميع الاستعلامات تستخدم parameterized queries (?, ?) لحماية من SQL Injection
لا يوجد أي exec/eval/subprocess — حماية كاملة من RCE
"""
import logging
from typing import Optional
import aiosqlite
from bot.config import config

logger = logging.getLogger(__name__)


async def init_db() -> None:
    """تهيئة جداول قاعدة البيانات"""
    async with aiosqlite.connect(config.DB_PATH) as db:
        # جدول المستخدمين (لا يحتوي على بيانات حساسة - التوكنات مشفرة)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                github_token TEXT,
                github_login TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_active DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # جدول سجل البحث
        await db.execute("""
            CREATE TABLE IF NOT EXISTS search_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                query TEXT NOT NULL,
                repo_found TEXT,
                status TEXT NOT NULL DEFAULT 'success',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # جدول سجل التحميلات
        await db.execute("""
            CREATE TABLE IF NOT EXISTS download_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                repo_name TEXT NOT NULL,
                release_tag TEXT,
                file_name TEXT NOT NULL,
                file_size INTEGER DEFAULT 0,
                delivery_method TEXT NOT NULL DEFAULT 'document',
                status TEXT NOT NULL DEFAULT 'success',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # جدول الإحصائيات اليومية المجمعة
        await db.execute("""
            CREATE TABLE IF NOT EXISTS daily_stats (
                date TEXT PRIMARY KEY,
                total_users INTEGER DEFAULT 0,
                total_searches INTEGER DEFAULT 0,
                total_downloads INTEGER DEFAULT 0,
                total_errors INTEGER DEFAULT 0,
                active_users INTEGER DEFAULT 0
            )
        """)
        # فهرس لتسريع الاستعلامات
        await db.execute("CREATE INDEX IF NOT EXISTS idx_search_user ON search_log(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_dl_user ON download_log(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_search_date ON search_log(created_at)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_dl_date ON download_log(created_at)")

        await db.commit()
        logger.info("تمت تهيئة قاعدة البيانات بنجاح")


# ──────────────────────────────────────────────
# عمليات المستخدمين
# ──────────────────────────────────────────────

async def save_user_token(user_id: int, encrypted_token: str, github_login: str = "") -> None:
    """حفظ أو تحديث توكن GitHub المشفّر للمستخدم (مع تحديث آخر نشاط)"""
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO users (user_id, github_token, github_login, last_active) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
            (user_id, encrypted_token, github_login)
        )
        await db.commit()


async def get_user_token(user_id: int) -> Optional[str]:
    """استرجاع التوكن المشفّر للمستخدم"""
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute(
            "SELECT github_token FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


async def delete_user_token(user_id: int) -> bool:
    """حذف توكن GitHub للمستخدم"""
    async with aiosqlite.connect(config.DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM users WHERE user_id = ?", (user_id,)
        )
        await db.commit()
        return cursor.rowcount > 0


async def update_user_activity(user_id: int) -> None:
    """تحديث آخر نشاط للمستخدم"""
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE user_id = ?",
            (user_id,)
        )
        await db.commit()


async def ensure_user_exists(user_id: int) -> None:
    """التأكد من وجود المستخدم (يُستدعى عند أي تفاعل)"""
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id) VALUES (?)",
            (user_id,)
        )
        await db.execute(
            "UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE user_id = ?",
            (user_id,)
        )
        await db.commit()


# ──────────────────────────────────────────────
# سجل البحث
# ──────────────────────────────────────────────

async def log_search(user_id: int, query: str, repo_found: str = "", status: str = "success") -> None:
    """تسجيل عملية بحث"""
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "INSERT INTO search_log (user_id, query, repo_found, status) VALUES (?, ?, ?, ?)",
            (user_id, query[:200], repo_found[:200] if repo_found else "", status[:20])
        )
        await db.commit()


# ──────────────────────────────────────────────
# سجل التحميلات
# ──────────────────────────────────────────────

async def log_download(user_id: int, repo_name: str, release_tag: str,
                       file_name: str, file_size: int, delivery_method: str,
                       status: str = "success") -> None:
    """تسجيل عملية تحميل"""
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "INSERT INTO download_log (user_id, repo_name, release_tag, file_name, file_size, delivery_method, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, repo_name[:200], release_tag[:100], file_name[:200],
             file_size, delivery_method[:20], status[:20])
        )
        await db.commit()


# ──────────────────────────────────────────────
# استعلامات الداشبورد (Read-only)
# ──────────────────────────────────────────────

async def get_dashboard_stats() -> dict:
    """إحصائيات عامة للداشبورد"""
    async with aiosqlite.connect(config.DB_PATH) as db:
        # إجمالي المستخدمين
        async with db.execute("SELECT COUNT(*) FROM users") as c:
            total_users = (await c.fetchone())[0]

        # مستخدمين مرتبطين
        async with db.execute("SELECT COUNT(*) FROM users WHERE github_token IS NOT NULL") as c:
            linked_users = (await c.fetchone())[0]

        # إجمالي البحث
        async with db.execute("SELECT COUNT(*) FROM search_log") as c:
            total_searches = (await c.fetchone())[0]

        # إجمالي التحميلات
        async with db.execute("SELECT COUNT(*) FROM download_log") as c:
            total_downloads = (await c.fetchone())[0]

        # أخطاء البحث
        async with db.execute("SELECT COUNT(*) FROM search_log WHERE status = 'error'") as c:
            total_errors = (await c.fetchone())[0]

        # مستخدمين نشطين (آخر 24 ساعة)
        async with db.execute(
            "SELECT COUNT(DISTINCT user_id) FROM users WHERE last_active > datetime('now', '-24 hours')"
        ) as c:
            active_24h = (await c.fetchone())[0]

        # حجم التحميلات الإجمالي
        async with db.execute("SELECT COALESCE(SUM(file_size), 0) FROM download_log") as c:
            total_bytes = (await c.fetchone())[0]

        # متوسط البحث اليومي (آخر 7 أيام)
        async with db.execute(
            "SELECT COUNT(*) FROM search_log WHERE created_at > datetime('now', '-7 days')"
        ) as c:
            weekly_searches = (await c.fetchone())[0]

        return {
            "total_users": total_users,
            "linked_users": linked_users,
            "total_searches": total_searches,
            "total_downloads": total_downloads,
            "total_errors": total_errors,
            "active_24h": active_24h,
            "total_bytes": total_bytes,
            "weekly_searches": weekly_searches,
        }


async def get_recent_searches(limit: int = 20) -> list:
    """آخر عمليات البحث"""
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT user_id, query, repo_found, status, created_at "
            "FROM search_log ORDER BY id DESC LIMIT ?",
            (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_recent_downloads(limit: int = 20) -> list:
    """آخر عمليات التحميل"""
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT user_id, repo_name, release_tag, file_name, file_size, delivery_method, status, created_at "
            "FROM download_log ORDER BY id DESC LIMIT ?",
            (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_users_list(limit: int = 50) -> list:
    """قائمة المستخدمين (بدون التوكنات المشفرة!)"""
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT user_id, github_login, "
            "CASE WHEN github_token IS NOT NULL THEN 1 ELSE 0 END as is_linked, "
            "created_at, last_active "
            "FROM users ORDER BY last_active DESC LIMIT ?",
            (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_daily_activity(days: int = 14) -> list:
    """نشاط الأيام الأخيرة (للرسم البياني)"""
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT date(created_at) as day, "
            "COUNT(DISTINCT user_id) as users, "
            "COUNT(*) as searches "
            "FROM search_log "
            "WHERE created_at > datetime('now', ? || ' days') "
            "GROUP BY day ORDER BY day",
            (str(-days),)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_top_repos(limit: int = 10) -> list:
    """أكثر المستودعات بحثاً"""
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT repo_found, COUNT(*) as count "
            "FROM search_log WHERE repo_found != '' AND status = 'success' "
            "GROUP BY repo_found ORDER BY count DESC LIMIT ?",
            (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]