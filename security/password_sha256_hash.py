import hashlib

def hash_256_password(password: str) -> str:
    return hashlib.sha256(password.encode("UTF-8")).hexdigest()