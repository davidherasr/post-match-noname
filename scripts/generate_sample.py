from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base
from repositories import scouting as repo
from services.report_service import generate_report_pdf


def main() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session.begin() as session:
        admin = repo.create_user(session, "Administrador", "admin@demo.local", "ClaveAdmin2026!", role="admin", must_change_password=False)
        reporter = repo.create_user(session, "David Heras", "david@demo.local", "ClaveDavid2026!", role="reporter", actor_id=admin.id, must_change_password=False)
        reporter2 = repo.create_user(session, "Analista Segundo", "analista@demo.local", "ClaveAnalista2026!", role="reporter", actor_id=admin.id, must_change_password=False)
        director = repo.create_user(session, "Director Deportivo", "director@demo.local", "ClaveDirector2026!", role="director", actor_id=admin.id, must_change_password=False)
        for key, value in {
            "club_name": "PostMatch Scout",
            "primary_color": "#A3131A",
            "secondary_color": "#101827",
            "report_subtitle": "Dirección deportiva · Observación postpartido",
            "report_confidentiality": "Documento interno y confidencial",
            "require_report_approval": "true",
        }.items():
            repo.set_setting(session, key, value, admin.id)
        season = repo.create_season(session, "2026/27", date(2026, 7, 1), date(2027, 6, 30), admin.id)
        comp = repo.create_competition(session, "LaLiga EA Sports", "España", admin.id)
        own = repo.create_team(session, "Real Madrid", "RMA", "España", True, admin.id)
        rival = repo.create_team(session, "FC Barcelona", "FCB", "España", False, admin.id)
        repo.set_setting(session, "own_team_id", str(own.id), admin.id)

        own_rows = [
            (1, "Thibaut Courtois", "POR"), (2, "Dani Carvajal", "LD"), (3, "Éder Militão", "DFC"),
            (22, "Antonio Rüdiger", "DFC"), (23, "Ferland Mendy", "LI"), (8, "Federico Valverde", "MC"),
            (14, "Aurélien Tchouaméni", "MCD"), (5, "Jude Bellingham", "MP"), (11, "Rodrygo", "ED"),
            (7, "Vinícius Júnior", "EI"), (9, "Kylian Mbappé", "DC"), (10, "Luka Modrić", "MC"),
            (21, "Brahim Díaz", "MP"), (20, "Fran García", "LI"),
        ]
        rival_rows = [
            (1, "Wojciech Szczęsny", "POR"), (23, "Jules Koundé", "LD"), (2, "Pau Cubarsí", "DFC"),
            (4, "Ronald Araújo", "DFC"), (3, "Alejandro Balde", "LI"), (21, "Frenkie de Jong", "MCD"),
            (8, "Pedri", "MC"), (20, "Dani Olmo", "MP"), (19, "Lamine Yamal", "ED"),
            (11, "Raphinha", "EI"), (9, "Robert Lewandowski", "DC"), (7, "Ferran Torres", "DC"),
            (16, "Fermín López", "MC"), (18, "Pau Víctor", "DC"),
        ]

        def roster(team, rows):
            seeded = []
            for number, name, position in rows:
                player = repo.find_or_create_player(session, name, primary_position=position, nationality="España" if name not in {"Wojciech Szczęsny", "Jules Koundé", "Ronald Araújo", "Frenkie de Jong", "Raphinha", "Robert Lewandowski"} else None, actor_id=admin.id)
                repo.assign_player_to_roster(session, team.id, season.id, player.id, number, admin.id)
                seeded.append((number, player, position))
            return seeded

        own_seed, rival_seed = roster(own, own_rows), roster(rival, rival_rows)
        match = repo.create_match(session, season_id=season.id, competition_id=comp.id, round_name="Jornada 1", match_date=date(2026, 8, 16), home_team_id=own.id, away_team_id=rival.id, created_by=admin.id, home_score=2, away_score=2, venue="Santiago Bernabéu", home_formation="4-2-3-1", away_formation="4-3-3", status="published")

        def lineup(team, seeded):
            rows = []
            for idx, (number, player, position) in enumerate(seeded):
                starter = idx < 11
                minute_in = 0 if starter else (68 if idx == 11 else 76 if idx == 12 else 84)
                minute_out = 90
                if starter and idx in {6, 7, 10}:
                    minute_out = {6: 76, 7: 68, 10: 84}[idx]
                rows.append({"selected": True, "player_id": player.id, "shirt_number": number, "starter": starter, "position": position, "minute_in": minute_in, "minute_out": minute_out, "captain": idx == 3})
            repo.replace_participations(session, match.id, team.id, rows, admin.id)
        lineup(own, own_seed); lineup(rival, rival_seed)
        repo.assign_reporters(session, match.id, [reporter.id, reporter2.id], admin.id)

        ratings = {
            "Wojciech Szczęsny": (6.5, "Correcto bajo palos y seguro en las acciones sencillas."),
            "Jules Koundé": (7.5, "Muy fiable en el duelo y rápido para corregir a campo abierto."),
            "Pau Cubarsí": (8.0, "Superó la primera presión con pase vertical y defendió hacia delante con serenidad."),
            "Ronald Araújo": (7.0, "Dominante en el contacto y bien protegido en área."),
            "Alejandro Balde": (6.5, "Aportó profundidad y velocidad, aunque decidió de forma irregular."),
            "Frenkie de Jong": (7.0, "Facilitó la salida y dio continuidad al juego."),
            "Pedri": (8.8, "Fue quien mejor interpretó el partido: recibió entre líneas, aceleró y dio pausa."),
            "Dani Olmo": (7.5, "Se movió con inteligencia entre mediocentro y central."),
            "Lamine Yamal": (8.5, "Generó desequilibrio constante desde la derecha."),
            "Raphinha": (7.0, "Aportó profundidad y repetición de esfuerzos."),
            "Robert Lewandowski": (6.5, "Fijó centrales y ocupó bien el área."),
            "Ferran Torres": (6.5, "Entró con energía y atacó el espacio."),
            "Fermín López": (7.0, "Aumentó el ritmo y llegó desde segunda línea."),
            "Pau Víctor": (0.0, "Pocos minutos para una valoración concluyente."),
        }

        def complete_report(user, adjustment: float):
            report = repo.get_or_create_report(session, match.id, user.id)
            rival_parts = {p.player.full_name: p for p in repo.get_participations(session, match.id, rival.id)}
            for name, (rating, note) in ratings.items():
                p = rival_parts[name]
                value = max(0.0, min(10.0, rating + adjustment)) if rating else 0.0
                repo.upsert_evaluation(
                    session, report.id, p.player_id, rival.id, p.id, actor_id=user.id,
                    observation_status="evaluated" if value > 0 else "not_observed",
                    general_rating=value if value > 0 else None,
                    short_note=note, standout=value >= 8.0, pdf_include=True,
                )
            own_parts = {p.player.full_name: p for p in repo.get_participations(session, match.id, own.id)}
            for name, value, note in [
                ("Thibaut Courtois", 7.0, "Seguro en las intervenciones que tuvo."),
                ("Federico Valverde", 7.5, "Sostuvo el ritmo del equipo durante todo el partido."),
                ("Vinícius Júnior", 8.0, "Fue el jugador propio más desequilibrante."),
            ]:
                p = own_parts[name]
                repo.upsert_evaluation(
                    session, report.id, p.player_id, own.id, p.id, actor_id=user.id,
                    observation_status="evaluated", general_rating=value, short_note=note,
                    standout=value >= 8.0, pdf_include=True,
                )
            repo.sync_report_standout(session, report.id, user.id)
            submitted, version = repo.submit_report(session, report.id, user.id)
            repo.approve_report(session, report.id, director.id, "Informe validado para el archivo de dirección deportiva.")
            return report, version

        report, version = complete_report(reporter, 0)
        complete_report(reporter2, -0.2)
        sample_dir = ROOT / "sample"
        sample_dir.mkdir(exist_ok=True)
        (sample_dir / "informe_demo_postmatch_scout_2_1_completo.pdf").write_bytes(generate_report_pdf(session, report.id, version=version.version, mode="full"))
        (sample_dir / "informe_demo_postmatch_scout_2_1_ejecutivo.pdf").write_bytes(generate_report_pdf(session, report.id, version=version.version, mode="executive"))
    print("PDF de muestra 2.1 generados.")


if __name__ == "__main__":
    main()
