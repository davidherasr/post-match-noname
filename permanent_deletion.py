"""Explicit, transaction-scoped removal of selected sporting records.

All FK-linked rows are included in a preview before execution. Nullable references
are detached, except for observations and drafts owned by a deleted match/season.
Never infer which records are disposable from a name or a 'test' flag.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from collections import defaultdict

from sqlalchemy import and_, delete, or_, select, update
from sqlalchemy.orm import Session

from models import entities
from models.base import Base
from repositories.common import audit
from repositories.users import assert_role

ROOTS = {
    'temporadas': 'seasons',
    'partidos': 'matches',
    'equipos': 'teams',
    'jugadores': 'players',
}
# A reference can be optional but still belong to a particular match/season.
OWNED_OPTIONAL = {
    ('scout_observations', 'match_id'),
    ('postmatch_drafts', 'season_id'),
    ('scouting_lists', 'season_id'),
}
LABELS = {
    'seasons':'Temporadas', 'matches':'Partidos', 'teams':'Equipos',
    'players':'Jugadores', 'participations':'Participaciones',
    'team_rosters':'Plantillas', 'report_assignments':'Asignaciones',
    'reports':'Informes', 'player_evaluations':'Valoraciones',
    'report_versions':'Versiones de informes', 'documents':'Documentos (metadatos)',
    'match_opinions':'Lecturas neutrales', 'match_opinion_players':'Señales',
    'scout_observations':'Observaciones individuales',
}


@dataclass(frozen=True)
class DeletionPlan:
    roots: dict[str, tuple[int, ...]]
    rows: dict[str, tuple[int, ...]]
    detach: dict[tuple[str, str], tuple[int, ...]]
    settings: tuple[str, ...]
    external_files: tuple[tuple[str, str], ...]
    fingerprint: str

    @property
    def total(self) -> int:
        return sum(map(len, self.rows.values()))


def _canonical_roots(roots: dict[str, list[int]]) -> dict[str, tuple[int, ...]]:
    if not isinstance(roots, dict) or any(key not in ROOTS for key in roots):
        raise ValueError('Tipo de selección no admitido.')
    selected = {}
    for key in ROOTS:
        values = roots.get(key) or []
        if len(values) > 10000 or any(not isinstance(value, int) or isinstance(value, bool) or value < 1 for value in values):
            raise ValueError('La selección contiene IDs inválidos.')
        selected[key] = tuple(sorted(set(values)))
    if not any(selected.values()):
        raise ValueError('Selecciona al menos un registro.')
    return selected


def build_plan(session: Session, roots: dict[str, list[int]], actor_id: int) -> DeletionPlan:
    """Read-only preview: no deletes, updates, auto-selected teams or guessed IDs."""
    assert_role(session, actor_id, 'admin')
    chosen = _canonical_roots(roots)
    table_by_name = Base.metadata.tables
    doomed = defaultdict(set)
    for kind, ids in chosen.items():
        if not ids:
            continue
        table = table_by_name[ROOTS[kind]]
        existing = set(session.scalars(select(table.c.id).where(table.c.id.in_(ids))).all())
        if existing != set(ids):
            raise ValueError(f'La selección de {kind} contiene registros inexistentes. Actualiza el listado.')
        doomed[table.name].update(ids)

    # Topological metadata order ensures every parent is visited before its children.
    # Non-nullable FKs and explicitly owned optional references follow the parent;
    # remaining optional references will be detached without deleting their row.
    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            for fk in column.foreign_keys:
                parent_ids = doomed.get(fk.column.table.name)
                if not parent_ids:
                    continue
                if column.nullable and (table.name, column.name) not in OWNED_OPTIONAL:
                    continue
                dependent_ids = session.scalars(select(table.c.id).where(column.in_(parent_ids))).all()
                doomed[table.name].update(dependent_ids)

    detach = defaultdict(set)
    for table in Base.metadata.sorted_tables:
        surviving = doomed.get(table.name, set())
        for column in table.columns:
            for fk in column.foreign_keys:
                parent_ids = doomed.get(fk.column.table.name)
                if not parent_ids or not column.nullable or (table.name, column.name) in OWNED_OPTIONAL:
                    continue
                ref_ids = set(session.scalars(select(table.c.id).where(column.in_(parent_ids))).all())
                ref_ids -= surviving
                if ref_ids:
                    detach[(table.name, column.name)].update(ref_ids)

    settings = []
    for kind, key in [('temporadas', 'active_season_id'), ('equipos', 'own_team_id')]:
        value = session.scalar(select(entities.AppSetting.value).where(entities.AppSetting.key == key))
        if value is not None and str(value).isdigit() and int(value) in doomed.get(ROOTS[kind], set()):
            settings.append(key)

    external_files = []
    if doomed.get('documents'):
        docs = session.scalars(select(entities.Document).where(entities.Document.id.in_(doomed['documents']))).all()
        external_files = sorted({(str(doc.storage_bucket or ''), str(doc.storage_path or doc.local_path or ''))
                                 for doc in docs if doc.storage_path or doc.local_path})

    rows = {table: tuple(sorted(ids)) for table, ids in doomed.items() if ids}
    detach_rows = {pair: tuple(sorted(ids)) for pair, ids in detach.items() if ids}
    serialized = json.dumps({
        'roots': chosen, 'rows': rows,
        'detach': {'.'.join(key): val for key,val in detach_rows.items()},
        'settings': sorted(settings), 'files': external_files,
    }, sort_keys=True, default=list)
    return DeletionPlan(chosen, rows, detach_rows, tuple(sorted(settings)), tuple(external_files),
                        hashlib.sha256(serialized.encode('utf-8')).hexdigest())


def orphan_player_suggestions(session: Session, plan: DeletionPlan) -> list[tuple[int, str]]:
    """Conservative suggestions, never silently included in the deletion plan."""
    from models.entities import TeamRoster, Participation, Player
    affected = set()
    for model in (TeamRoster, Participation):
        ids = plan.rows.get(model.__tablename__, ())
        if ids:
            affected.update(session.scalars(select(model.player_id).where(model.id.in_(ids))).all())
    affected -= set(plan.rows.get('players', ()))
    result = []
    for pid in sorted(affected):
        # Consider any other foreign-key link independent of this deletion; aliases,
        # league profile and scouting notes are substantial information, not proof of an orphan.
        unowned = False
        for table in Base.metadata.sorted_tables:
            for col in table.columns:
                if not any(fk.column.table.name == 'players' for fk in col.foreign_keys):
                    continue
                if table.name in {'player_aliases', 'player_merge_logs'}:
                    continue
                refs = set(session.scalars(select(table.c.id).where(col == pid)).all())
                if refs - set(plan.rows.get(table.name, ())):
                    unowned = True
                    break
            if unowned:
                break
        player = session.get(Player, pid)
        if player is not None and not unowned:
            result.append((pid, player.full_name))
    return result


def execute_plan(session: Session, roots: dict[str, list[int]], actor_id: int,
                 fingerprint: str) -> dict[str, int]:
    """One transaction, permission checked again; caller commits or rolls back.

    Locks roots to prevent new FK dependents on PostgreSQL during reconciliation.
    An independent production backup is required by the admin confirmation UI.
    """
    assert_role(session, actor_id, 'admin')
    canonical = _canonical_roots(roots)
    for kind, ids in canonical.items():
        if ids:
            table = Base.metadata.tables[ROOTS[kind]]
            session.execute(select(table.c.id).where(table.c.id.in_(ids)).with_for_update()).all()
    plan = build_plan(session, {key: list(values) for key, values in canonical.items()}, actor_id)
    if plan.fingerprint != fingerprint:
        raise ValueError('Los datos vinculados han cambiado desde la vista previa. Revisa el impacto y confirma de nuevo.')
    if not isinstance(fingerprint, str) or len(fingerprint) != 64:
        raise ValueError('No se ha confirmado una vista previa válida.')

    for (table_name, column_name), ids in plan.detach.items():
        table = Base.metadata.tables[table_name]
        session.execute(update(table).where(table.c.id.in_(ids)).values({column_name: None}))
    for key in plan.settings:
        session.execute(update(entities.AppSetting).where(entities.AppSetting.key == key).values(value=None))

    # Reverse topological order: children before parents, including formerly
    # optional links above. No global TRUNCATE and no ORM delete cascades.
    for table in reversed(Base.metadata.sorted_tables):
        ids = plan.rows.get(table.name, ())
        if ids:
            session.execute(delete(table).where(table.c.id.in_(ids)))
    audit(session, actor_id, 'permanent_delete_sporting_records', detail=json.dumps({
        'selected': {k: list(v) for k,v in canonical.items() if v},
        'deleted': {key: len(val) for key,val in plan.rows.items()},
        'detached': {f'{t}.{c}':len(v) for (t,c),v in plan.detach.items()},
        'external_documents_to_review': len(plan.external_files),
    }, ensure_ascii=False))
    session.flush()
    session.expire_all()
    return {table: len(ids) for table, ids in plan.rows.items()}
