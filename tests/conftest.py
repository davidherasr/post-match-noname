from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base
import core.security as security


@pytest.fixture()
def session_factory():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        engine.dispose()


@pytest.fixture(autouse=True)
def fast_password_hashing(monkeypatch):
    # Production keeps 390k PBKDF2 iterations. Tests exercise behavior, not CPU cost.
    monkeypatch.setattr(security, "_ITERATIONS", 2_000)
