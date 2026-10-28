-- Consultas SOLO LECTURA para ejecutar en Supabase SQL Editor.
-- IMPORTANTE: No crear ni modificar supabase_migrations.schema_migrations.
-- El esquema public de la aplicación usa Alembic y public.alembic_version.

-- 1. Revisión Alembic realmente aplicada:
SELECT version_num AS revision_actual
FROM public.alembic_version;

-- 2. Comprobar la tabla nueva y las columnas esperadas (sin acceder a filas de negocio):
SELECT to_regclass('public.unidentified_player_signals') AS tabla_senales_anonimas;

SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND (
    (table_name = 'users' AND column_name = 'participation_profile') OR
    (table_name = 'team_rosters' AND column_name = 'usual_position') OR
    (table_name = 'player_evaluations' AND column_name IN ('highlight_rank','lowlight_rank','attention_signal')) OR
    (table_name = 'match_opinion_players' AND column_name IN ('highlight_rank','attention_signal')) OR
    (table_name = 'player_observation_requests' AND column_name IN
       ('origin_player_evaluation_id','origin_neutral_signal_id','origin_unidentified_signal_id'))
  )
ORDER BY table_name, column_name;
