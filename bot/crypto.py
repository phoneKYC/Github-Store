"""
وحدة التشفير - تشفير وفك تشفير توكنات GitHub
"""
from bot.config import config


def encrypt_token(token: str) -> str:
    """تشفير التوكن باستخدام Fernet (AES-128-CBC)"""
    return config.cipher_suite.encrypt(token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str:
    """فك تشفير التوكن"""
    return config.cipher_suite.decrypt(encrypted_token.encode()).decode()