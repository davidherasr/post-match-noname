from datetime import timedelta

import pytest

from core.security import hash_password, verify_password
from models.entities import utcnow
from repositories import scouting as repo


def test_password_roundtrip_and_simple_policy():
    for password in ["1", "1234", "a", "hola", "UnaClaveSegura123!"]:
        encoded = hash_password(password)
        assert verify_password(password, encoded)
        assert not verify_password(password + "x", encoded)
    with pytest.raises(ValueError):
        hash_password("")


def test_login_lockout(session_factory):
    with session_factory.begin() as session:
        user = repo.create_user(session, "Usuario", "u@example.com", "1", must_change_password=False)
        for _ in range(5):
            assert repo.authenticate(session, "u@example.com", "incorrecta") is None
        assert user.locked_until is not None
        assert user.locked_until > utcnow() - timedelta(seconds=1)
        assert repo.authenticate(session, "u@example.com", "1") is None
