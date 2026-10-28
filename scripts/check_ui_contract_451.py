"""Import smoke test, run with production requirements before deploying.

Unlike compileall, it checks dynamic imports used by specific UI routes.
It does not connect to a database or alter customer information.
"""
from __future__ import annotations
import importlib
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.config import APP_VERSION
from repositories.users import PARTICIPATION_PROFILES
from models.entities import PlayerObservationResponse, UnidentifiedPlayerSignal
from repositories.dd_attention import team_knowledge

assert APP_VERSION == '4.6'
assert set(PARTICIPATION_PROFILES) == {'own_only', 'full', 'free', 'viewer'}
assert PlayerObservationResponse.__tablename__ == 'player_observation_responses'
assert UnidentifiedPlayerSignal.__tablename__ == 'unidentified_player_signals'
assert callable(team_knowledge)
for mod in ('views.admin', 'views.team_hub', 'views.player_hub',
            'views.reports', 'views.home', 'views.jornada', 'views.squad'):
    loaded = importlib.import_module(mod)
    assert callable(loaded.render), mod
print('OK · Importaciones UI y ORM 4.6')
