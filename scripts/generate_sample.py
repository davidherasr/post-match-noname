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
            "Wojciech Szczęsny": (6.5, "Anotar en base de datos", "Correcto bajo palos y seguro en las acciones sencillas, sin asumir riesgos innecesarios."),
            "Jules Koundé": (7.5, "Seguimiento recomendado", "Muy fiable en el duelo y rápido para corregir a campo abierto. Sostuvo bien la amplitud sin perder equilibrio."),
            "Pau Cubarsí": (8.0, "Jugador interesante", "Superó la primera presión con pase vertical y defendió hacia delante con una serenidad muy destacable."),
            "Ronald Araújo": (7.0, "Anotar en base de datos", "Dominante en el contacto y bien protegido en área, aunque menos limpio en la primera salida."),
            "Alejandro Balde": (6.5, "Anotar en base de datos", "Aportó profundidad y velocidad, pero su influencia fue irregular cuando tuvo que decidir cerca del área."),
            "Frenkie de Jong": (7.0, "Seguimiento recomendado", "Facilitó la salida y dio continuidad al juego, especialmente cuando recibió a la espalda de la primera línea."),
            "Pedri": (8.8, "Prioridad de seguimiento", "Fue el futbolista que mejor interpretó el partido: recibió entre líneas, aceleró con ventaja y dio pausa cuando el equipo la necesitó."),
            "Dani Olmo": (7.6, "Jugador interesante", "Se movió con inteligencia entre mediocentro y central y fue una amenaza constante cuando pudo girarse."),
            "Lamine Yamal": (8.3, "Prioridad de seguimiento", "Generó desequilibrio constante desde la derecha y obligó a activar ayudas en cada recepción."),
            "Raphinha": (7.2, "Seguimiento recomendado", "Profundidad, repetición de esfuerzos y capacidad para aparecer en zonas de remate, aunque perdió precisión en varias asociaciones."),
            "Robert Lewandowski": (6.7, "Anotar en base de datos", "Fijó centrales y ocupó bien el área, pero tuvo poca continuidad fuera de las acciones de finalización."),
            "Ferran Torres": (6.8, "Anotar en base de datos", "Entró con energía, atacó el espacio y dio una amenaza distinta en el tramo final."),
            "Fermín López": (7.1, "Seguimiento recomendado", "Aumentó el ritmo del centro del campo y atacó con decisión el espacio desde segunda línea."),
            "Pau Víctor": (None, None, "Pocos minutos para una valoración concluyente."),
        }

        def complete_report(user, adjustment: float):
            report = repo.get_or_create_report(session, match.id, user.id)
            parts = {p.player.full_name: p for p in repo.get_participations(session, match.id, rival.id)}
            for name, (rating, recommendation, note) in ratings.items():
                p = parts[name]
                if rating is None:
                    repo.upsert_evaluation(session, report.id, p.player_id, rival.id, p.id, actor_id=user.id, observation_status="insufficient", short_note=note, pdf_include=False)
                    continue
                value = min(10, max(1, rating + adjustment))
                advanced = name in {"Jules Koundé", "Pau Cubarsí", "Pedri", "Lamine Yamal", "Dani Olmo"}
                repo.upsert_evaluation(
                    session, report.id, p.player_id, rival.id, p.id, actor_id=user.id,
                    observation_status="evaluated", general_rating=value,
                    technical_rating=(value + 0.3 if advanced else None), tactical_rating=(value if advanced else None), physical_rating=(value - 0.4 if advanced else None),
                    recommendation=recommendation, confidence="Alta" if advanced else "Media", short_note=note,
                    strengths=["Técnica", "Visión"] if name == "Pedri" else ["Desborde", "Velocidad"] if name == "Lamine Yamal" else ["Anticipación", "Salida de balón"] if name == "Pau Cubarsí" else [],
                    standout=name in {"Pedri", "Lamine Yamal"}, pdf_include=name not in {"Wojciech Szczęsny", "Alejandro Balde", "Robert Lewandowski", "Ferran Torres", "Pau Víctor"},
                    detailed_note=("Conviene repetir la observación ante un contexto de mayor exigencia defensiva para confirmar cómo responde cuando debe proteger más metros a su espalda y tomar decisiones bajo una presión más agresiva." if advanced else None),
                )
            repo.save_report_summary(
                session, report.id, rival_level="Alto",
                opponent_overview="Rival con capacidad para controlar el partido en campo contrario y varios perfiles diferenciales. Sus interiores encontraron ventajas entre líneas y los extremos obligaron a defender con ayudas continuas. El equipo mantuvo una identidad reconocible incluso tras los cambios.",
                own_team_note="Nuestro equipo compitió bien, pero sufrió cuando el rival consiguió fijar por dentro y liberar a los extremos.",
                key_takeaways="Pedri y Lamine Yamal fueron los perfiles más influyentes. Cubarsí dejó una impresión muy positiva por su salida de balón y Koundé confirmó un nivel alto de fiabilidad y polivalencia.",
                standout_player_id=parts["Pedri"].player_id, actor_id=user.id,
            )
            submitted, version = repo.submit_report(session, report.id, user.id)
            repo.approve_report(session, report.id, director.id, "Informe validado para el archivo de dirección deportiva.")
            return report, version

        report, version = complete_report(reporter, 0)
        complete_report(reporter2, -0.2)
        sample_dir = ROOT / "sample"
        sample_dir.mkdir(exist_ok=True)
        (sample_dir / "informe_demo_postmatch_scout_2_0_completo.pdf").write_bytes(generate_report_pdf(session, report.id, version=version.version, mode="full"))
        (sample_dir / "informe_demo_postmatch_scout_2_0_ejecutivo.pdf").write_bytes(generate_report_pdf(session, report.id, version=version.version, mode="executive"))
    print("PDF de muestra 2.0 generados.")


if __name__ == "__main__":
    main()
