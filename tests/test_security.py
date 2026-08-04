from datetime import timedelta

import pytest

from core.security import hash_password, verify_password
from models.entities import utcnow
from repositories import scouting as repo


def test_password_roundtrip_and_policy():
    encoded = hash_password("UnaClaveSegura123!")
    assert verify_password("UnaClaveSegura123!", encoded)
    assert not verify_password("incorrecta", encoded)
    with pytest.raises(ValueError):
        hash_password("corta")


def test_login_lockout(session_factory):
    with session_factory.begin() as session:
        user = repo.create_user(session, "Usuario", "u@example.com", "ClaveSegura123!", must_change_password=False)
        for _ in range(5):
            assert repo.authenticate(session, "u@example.com", "incorrecta") is None
        assert user.locked_until is not None
        assert user.locked_until > utcnow() - timedelta(seconds=1)
        assert repo.authenticate(session, "u@example.com", "ClaveSegura123!") is None
