import secrets
import hashlib

def hashed_token_generate():
    randomized_char = secrets.token_urlsafe(50)
    return hashlib.sha256(randomized_char.encode("UTF-8").hexdigest())
