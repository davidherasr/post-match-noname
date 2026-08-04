from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select

from core.config import settings
from core.database import session_scope
from models.entities import Match, Team, User
from repositories import scouting as repo


def bootstrap_application() -> None:
    with session_scope() as session:
        if repo.count_users(session) == 0:
            repo.create_user(
                session,
                settings.bootstrap_admin_name,
                settings.bootstrap_admin_email,
                settings.bootstrap_admin_password,
                role="admin",
                must_change_password=not settings.demo_mode,
            )
        defaults = {
            "club_name": "PostMatch Scout",
            "primary_color": "#B91C1C",
            "secondary_color": "#111827",
            "report_subtitle": "Dirección deportiva · Observación de rivales",
            "report_confidentiality": "Documento interno y confidencial",
            "pdf_default_mode": "executive",
            "require_report_approval": "true" if settings.require_report_approval else "false",
        }
        for key, value in defaults.items():
            if repo.get_setting(session, key) is None:
                repo.set_setting(session, key, value)
    if settings.demo_mode:
        seed_demo_data()


def seed_demo_data() -> None:
    with session_scope() as session:
        season = repo.create_season(session, "2026/27", date(2026, 7, 1), date(2027, 6, 30))
        competition = repo.create_competition(session, "Liga - Demostración", "España")
        own = repo.create_team(session, "Real Madrid", "RMA", "España", is_own_team=True)
        rival = repo.create_team(session, "FC Barcelona", "FCB", "España")
        repo.set_setting(session, "club_name", "PostMatch Scout · Demo")
        repo.set_setting(session, "own_team_id", str(own.id))
        admin = session.scalar(select(User).where(User.role == "admin").order_by(User.id))
        reporter = session.scalar(select(User).where(User.email == "informador@postmatch.local"))
        if not reporter:
            reporter = repo.create_user(session, "Informador Demo", "informador@postmatch.local", "DemoReporter2026!", role="reporter", actor_id=admin.id, must_change_password=False)

        own_players = [
            (1, "Portero Demo Madrid", "POR"), (2, "Lateral Derecho Demo Madrid", "LD"),
            (3, "Central Uno Demo Madrid", "DFC"), (4, "Central Dos Demo Madrid", "DFC"),
            (5, "Lateral Izquierdo Demo Madrid", "LI"), (6, "Mediocentro Demo Madrid", "MCD"),
            (8, "Interior Demo Madrid", "MC"), (10, "Mediapunta Demo Madrid", "MP"),
            (7, "Extremo Derecho Demo Madrid", "ED"), (11, "Extremo Izquierdo Demo Madrid", "EI"),
            (9, "Delantero Demo Madrid", "DC"), (12, "Suplente Uno Demo Madrid", "MC"),
            (14, "Suplente Dos Demo Madrid", "DC"),
        ]
        rival_players = [
            (1, "Wojciech Szczesny", "POR"), (23, "Jules Koundé", "LD"),
            (2, "Pau Cubarsí", "DFC"), (4, "Central Demo Barcelona", "DFC"),
            (3, "Lateral Demo Barcelona", "LI"), (21, "Frenkie de Jong", "MC"),
            (8, "Pedri", "MC"), (20, "Dani Olmo", "MP"), (19, "Lamine Yamal", "ED"),
            (11, "Raphinha", "EI"), (9, "Robert Lewandowski", "DC"),
            (7, "Ferran Torres", "DC"), (16, "Mediocentro Suplente Demo", "MCD"),
            (18, "Extremo Suplente Demo", "EI"),
        ]

        def seed_roster(team: Team, rows: list[tuple[int, str, str]]):
            result = []
            for number, name, position in rows:
                player = repo.find_or_create_player(session, name, primary_position=position)
                repo.assign_player_to_roster(session, team.id, season.id, player.id, number)
                result.append((number, player, position))
            return result

        own_seed = seed_roster(own, own_players)
        rival_seed = seed_roster(rival, rival_players)
        existing_match = session.scalar(select(Match).where(Match.round_name == "Jornada 1 - Demo", Match.home_team_id == own.id, Match.away_team_id == rival.id))
        if not existing_match:
            existing_match = repo.create_match(
                session,
                season_id=season.id,
                competition_id=competition.id,
                round_name="Jornada 1 - Demo",
                match_date=date(2026, 8, 15),
                home_team_id=own.id,
                away_team_id=rival.id,
                created_by=admin.id,
                home_score=2,
                away_score=1,
                home_formation="4-2-3-1",
                away_formation="4-3-3",
                status="published",
                report_due_at=datetime(2026, 8, 17, 20, 0),
            )

            def lineup(team: Team, seeded: list[tuple[int, object, str]]):
                rows = []
                for idx, (number, player, pos) in enumerate(seeded):
                    starter = idx < 11
                    rows.append({
                        "selected": True,
                        "player_id": player.id,
                        "shirt_number": number,
                        "starter": starter,
                        "position": pos,
                        "minute_in": 0 if starter else (70 if idx < 13 else 80),
                        "minute_out": 90 if not starter else (70 if idx in (8, 10) else 90),
                        "captain": idx == 2,
                    })
                repo.replace_participations(session, existing_match.id, team.id, rows, admin.id)

            lineup(own, own_seed)
            lineup(rival, rival_seed)
            repo.assign_reporters(session, existing_match.id, [reporter.id, admin.id], admin.id, due_at=existing_match.report_due_at)
