from cryptography.fernet import Fernet

from ..config import settings


def _cipher() -> Fernet:
    return Fernet(settings.TOKEN_ENCRYPTION_KEY.encode())


def encrypt_token(token: str) -> str:
    return _cipher().encrypt(token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str:
    return _cipher().decrypt(encrypted_token.encode()).decode()