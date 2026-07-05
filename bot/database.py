"""
وحدة قاعدة البيانات - إدارة الجداول والعمليات المتعلقة بالمستخدمين
"""
import logging
from typing import Optional
import aiosqlite
from bot.config import config

logger = logging.getLogger(__name__)


async def init_db() -> None:
    """تهيئة جداول قاعدة البيانات"""
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                github_token TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                repo_path TEXT PRIMARY KEY,
                data TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()
        logger.info("تم تهيئة قاعدة البيانات بنجاح")


async def save_user_token(user_id: int, encrypted_token: str) -> None:
    """حفظ أو تحديث توكن GitHub المشفّر للمستخدم"""
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO users (user_id, github_token) VALUES (?, ?)",
            (user_id, encrypted_token)
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