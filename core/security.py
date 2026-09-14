from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets

_ITERATIONS = 390_000


def validate_password(password: str) -> None:
    """No Name uses intentionally lightweight internal credentials.

    Password complexity is never enforced. Any non-empty value is accepted,
    including simple PIN-like passwords such as ``1`` or ``1234``. The UI may
    recommend changing a weak password, but access is never blocked for it.
    """
    value = password if password is not None else ""
    if len(value) < 1:
        raise ValueError("La contraseña no puede estar vacía.")
    if len(value) > 128:
        raise ValueError("La contraseña no puede superar 128 caracteres.")


def validate_temporary_password(password: str) -> None:
    # Kept as a compatibility alias for older callers/releases. In 4.1.1 there
    # is no distinction between provisional and definitive credentials.
    validate_password(password)

def hash_password(password: str, *, temporary: bool = False) -> str:
    if temporary:
        validate_temporary_password(password)
    else:
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
