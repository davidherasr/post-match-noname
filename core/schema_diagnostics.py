"""Read-only comparison of a public schema with this release's ORM schema.

This module never inspects or creates ``supabase_migrations``.  The Supabase
CLI's migration history and No Name's Alembic history are separate systems.
"""
from __future__ import annotations

import re
from typing import Mapping

from models import Base

ALEMBIC_HEAD_4511 = "0017_lowlight_compact_4_5_1"
BASELINE_HEAD_4441 = "0015_observation_requests_4_4_3"


class SchemaManifestError(ValueError):
    pass


def parse_public_manifest(content: str) -> dict[str, set[str]]:
    """Parse the public-only table/column listing exported from Supabase.

    This is *not* proof of a particular Alembic revision: the revision value is
    not part of the manifest and must be read separately from alembic_version.
    """
    current = None
    schema: dict[str, set[str]] = {}
    for line in content.splitlines():
        header = re.fullmatch(r"([a-z][a-z0-9_]*)\s+\((\d+)\s+campos?\)", line.strip())
        if header:
            current = header.group(1)
            if current in schema:
                raise SchemaManifestError(f"Tabla repetida: {current}")
            schema[current] = set()
            continue
        field = re.match(r"\s{2,}([a-z][a-z0-9_]*)\s+\S+", line)
        if field and current is not None:
            if field.group(1) in schema[current]:
                raise SchemaManifestError(f"Columna repetida: {current}.{field.group(1)}")
            schema[current].add(field.group(1))
    if not schema:
        raise SchemaManifestError("No se han encontrado tablas en el listado.")
    return schema


def expected_public_columns() -> dict[str, set[str]]:
    """Current ORM contract, including Alembic's separately managed table."""
    tables = {table.name: {column.name for column in table.columns}
              for table in Base.metadata.sorted_tables}
    tables["alembic_version"] = {"version_num"}
    return tables


def describe_public_schema(actual: Mapping[str, set[str]]) -> dict:
    expected = expected_public_columns()
    missing = {name: sorted(cols - actual.get(name, set()))
               for name, cols in expected.items() if cols - actual.get(name, set())}
    extra = {name: sorted(cols - expected.get(name, set()))
             for name, cols in actual.items() if cols - expected.get(name, set())}
    missing_tables = sorted(set(expected) - set(actual))
    extra_tables = sorted(set(actual) - set(expected))
    result = {
        "tables": len(actual), "columns": sum(map(len, actual.values())),
        "expected_tables": len(expected), "expected_columns": sum(map(len, expected.values())),
        "missing_tables": missing_tables, "extra_tables": extra_tables,
        "missing_columns": missing, "extra_columns": extra,
        "schema_matches_orm": not missing and not extra,
    }
    # Backward-compatible signature against the 4.5.1.1 baseline only:
    # newly added 4.7 tables must not invalidate recognition of a real 0015 dump.
    legacy_expected = {t: columns for t, columns in expected.items() if not t.endswith(('_47','_473'))}
    legacy_missing = {t: sorted(columns - actual.get(t, set())) for t, columns in legacy_expected.items()
                      if columns - actual.get(t, set())}
    legacy_missing_tables = sorted(set(legacy_expected)-set(actual))
    result['matches_4441_public_shape'] = (
        result['tables'] == 43 and result['columns'] == 461
        and legacy_missing_tables == ['unidentified_player_signals']
        and not extra_tables and not extra
        and legacy_missing == {
            'users': ['participation_profile'],
            'team_rosters': ['usual_position'],
            'player_evaluations': ['attention_signal', 'highlight_rank', 'lowlight_rank'],
            'match_opinion_players': ['attention_signal', 'highlight_rank'],
            'player_observation_requests': ['origin_neutral_signal_id', 'origin_player_evaluation_id', 'origin_unidentified_signal_id'],
            'unidentified_player_signals': sorted(legacy_expected['unidentified_player_signals']),
        }
    )
    return result
