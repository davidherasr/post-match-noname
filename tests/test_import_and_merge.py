from __future__ import annotations

import pandas as pd

from repositories import scouting as repo
from services.import_service import preview_import


def test_import_preview_detects_lineup_errors():
    df = pd.DataFrame([{"partido_id": 1, "equipo": "Rival", "jugador": "Uno", "titular": "Sí", "entrada": 10, "salida": 5}])
    result = preview_import(df, "lineups")
    assert result["errors"]


def test_duplicate_merge_moves_alias_and_marks_source(session_factory):
    with session_factory.begin() as session:
        admin = repo.create_user(session, "Admin", "admin@example.com", "ClaveAdmin123!", role="admin", must_change_password=False)
        source = repo.find_or_create_player(session, "José Pérez", primary_position="MC", actor_id=admin.id)
        # Force a second plausible duplicate with a different birth date.
        target = repo.find_or_create_player(session, "Jose Perez", date_of_birth=pd.Timestamp("2001-01-01").date(), primary_position="MC", actor_id=admin.id)
        repo.add_player_alias(session, source.id, "J. Pérez", admin.id)
        merged = repo.merge_players(session, source.id, target.id, admin.id)
        assert merged.id == target.id
        assert source.active is False
        assert source.merged_into_id == target.id
