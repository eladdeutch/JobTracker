"""Token encryption/decryption utilities using Fernet symmetric encryption."""
from backend.config import config


def encrypt_token(plaintext: str) -> str:
    """Encrypt a token string. Returns ciphertext or plaintext if no key configured."""
    if not plaintext:
        return plaintext
    if config.FERNET is None:
        return plaintext
    return config.FERNET.encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    """Decrypt a token string. Returns plaintext or the input if no key configured."""
    if not ciphertext:
        return ciphertext
    if config.FERNET is None:
        return ciphertext
    try:
        return config.FERNET.decrypt(ciphertext.encode()).decode()
    except Exception:
        # If decryption fails the value is likely already plaintext
        # (e.g. migrating from unencrypted storage).
        return ciphertext
