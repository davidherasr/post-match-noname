from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets

_ITERATIONS = 390_000


def validate_password(password: str) -> None:
    if len(password or "") < 10:
        raise ValueError("La contraseña debe tener al menos 10 caracteres.")
    if not re.search(r"[A-ZÁÉÍÓÚÜÑ]", password):
        raise ValueError("La contraseña debe incluir una mayúscula.")
    if not re.search(r"[a-záéíóúüñ]", password):
        raise ValueError("La contraseña debe incluir una minúscula.")
    if not re.search(r"\d", password):
        raise ValueError("La contraseña debe incluir un número.")
    if not re.search(r"[^\w\s]", password):
        raise ValueError("La contraseña debe incluir un símbolo.")


def hash_password(password: str) -> str:
    validate_password(password)
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(
        _ITERATIONS,
        base64.urlsafe_b64encode(salt).decode("ascii"),
        base64.urlsafe_b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_b64, digest_b64 = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(salt_b64.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_b64.encode("ascii"))
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(candidate, expected)
    except (ValueError, TypeError):
        return False
