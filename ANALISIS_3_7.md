# Análisis funcional y técnico · No Name PostMatch 3.7.0

## Motivo de la versión

La 3.7.0 elimina del flujo normal el concepto de rango de fin de semana (`12/09/2026-13/09/2026`). La Federación publica una fecha de jornada, normalmente domingo, pero esa fecha no garantiza que el encuentro se dispute ese día ni aporta una hora definitiva. Mantener dos fechas en el importador añadía complejidad sin aportar una decisión operativa real y generaba un punto de fallo innecesario.

La nueva regla es deliberadamente simple:

1. El calendario se importa con **una fecha orientativa de jornada**.
2. Mientras no exista hora, el partido está **provisional / horario pendiente**.
3. Administración confirma después **fecha definitiva + hora definitiva**.
4. Hasta entonces se puede planificar scouting, pero no se puede registrar el visionado ni preparar/publicar un postpartido nuevo desde ese partido.

Ejemplo:

```text
1;13/09/2026;La Cistérniga C.F.;C.D. Noname
```

No significa que se juegue el 13. Significa: `Jornada 1 · referencia federativa 13/09 · horario pendiente`.

Cuando se confirme:

```text
12/09/2026 · 18:00
```

el partido pasa a estado operativo.

## Qué se ha revisado

Se ha auditado el flujo completo actual, no solo el importador:

- autenticación y multirol;
- navegación por perfil;
- calendario de toda la liga;
- postpartido;
- informes de Informador;
- Scout y misiones DD;
- observaciones rápidas y avanzadas;
- Modelo No Name;
- plantilla sombra y necesidades;
- Player Report 360;
- Dirección Deportiva;
- calidad de datos;
- backups, auditoría y rendimiento;
- repositorios y validaciones de escritura;
- tests y contrato de release.

El código funcional revisado suma aproximadamente 12.000 líneas Python en `pages/`, `repositories/`, `services/`, `reports/`, `core/` y `ui/`.

## Cambios implementados en 3.7.0

### 1. Calendario sin rangos

El importador 3.7.0 acepta como formato principal:

```text
jornada;fecha_orientativa;local;visitante
```

Y, solo si ya se conoce el horario exacto:

```text
jornada;fecha_definitiva;hora;local;visitante
```

Las líneas con rango se rechazan con un mensaje explícito que indica usar una sola fecha. De esta manera desaparece por completo la ambigüedad de meses con 30/31 días o fines de semana que cruzan de mes/año.

### 2. Nuevo estado operativo: provisional

Una línea sin hora crea:

- `match_date`: fecha orientativa publicada;
- `kickoff_at`: vacío;
- `schedule_status`: `provisional`;
- `window_start/window_end`: vacíos en los nuevos datos.

Las columnas antiguas de ventana se conservan en la base por compatibilidad con 3.5/3.6; no hace falta migración ni se destruyen datos anteriores.

### 3. Fecha + hora obligatorias para activar trabajo real

Se centraliza la regla de disponibilidad del partido:

```text
schedule_status == confirmed
AND kickoff_at existe
```

Mientras no se cumpla:

- DD sí puede planificar una misión Scout;
- el Scout ve la misión como planificada;
- no puede iniciar una observación específica;
- no puede guardar un barrido rápido del partido;
- no puede completar un análisis rival asociado al encuentro;
- Administración no puede abrir el postpartido desde ese partido del calendario;
- un partido nuevo en flujo operativo exige una hora antes de publicarse.

Así el calendario sirve para planificar con meses de antelación sin convertir una fecha orientativa en un dato falso.

### 4. Confirmación de horario simplificada

En `Calendario → Horarios pendientes` ya no existe el estado intermedio de “día confirmado pero hora pendiente” como flujo principal.

Administración introduce:

- fecha definitiva;
- hora definitiva;
- campo opcional.

Y pulsa **Confirmar fecha y hora**.

### 5. Las misiones Scout se sincronizan con el horario

Una misión puede crearse cuando el partido todavía está provisional. En ese momento `due_at` queda vacío.

Cuando Administración confirma o modifica el horario, las misiones `pending/in_progress` vinculadas al partido actualizan automáticamente su hora operativa.

### 6. Reimportar el calendario ya no destruye horarios confirmados

Se detectó durante la auditoría un riesgo importante: si Administración confirmaba manualmente un sábado a las 18:00 y más tarde volvía a importar el calendario federativo, el importador anterior podía reescribir la programación con la información provisional.

En 3.7.0:

> una reimportación provisional nunca sustituye un `kickoff_at` ya confirmado.

Esto permite usar el calendario federativo como sincronización segura sin miedo a perder trabajo manual.

### 7. Postpartido manual con hora real

El flujo excepcional `Nuevo postpartido` ahora solicita también la **hora definitiva del partido**. No se precarga una hora ficticia: el administrador debe escribirla en formato `HH:MM`.

Los partidos recuperados desde Calendario ya llegan con su hora confirmada.

Al publicar, `matches.kickoff_at` y `schedule_status=confirmed` quedan persistidos.

### 8. Corrección de permisos multirol

La auditoría detectó un fallo sutil: algunas operaciones privilegiadas de informe comprobaban solo `User.role` (perfil principal) en vez de todas las capacidades de `user_roles`.

Ejemplo problemático:

```text
Perfil principal: Scout
Perfiles: Scout + Dirección Deportiva
```

Ese usuario podía entrar como DD en la interfaz, pero una comprobación de repositorio podía rechazar una acción sobre el informe de otro usuario.

3.7.0 valida todos los roles persistidos, no solo el principal.

### 9. Ficha Scout: rol y criterios ya no se pierden al editar

En la observación avanzada se detectó otro problema de UX:

- el rol No Name estaba dentro de un `st.form`;
- cambiarlo no refrescaba inmediatamente los criterios;
- al reabrir un borrador, los criterios del modelo podían aparecer a 0 aunque estuvieran guardados.

Ahora:

- el selector de rol está fuera del formulario;
- al cambiar de rol aparecen inmediatamente sus criterios;
- `model_role_id` se recupera de `attributes_json`;
- cada criterio recupera su puntuación guardada;
- la recomendación también conserva su valor anterior.

Esto evita pérdidas silenciosas de trabajo Scout.

### 10. Acceso directo a incidencias

El botón `Resolver` del dashboard de Administración abre directamente `Calendario → Horarios pendientes`, no la vista genérica del calendario.

## Estado global de la aplicación tras la auditoría

### Muy sólido / mantener

- arquitectura por roles y multirol;
- Informador ligero y separado del Scout;
- calendario de toda la liga;
- planificación DD sobre partidos neutrales;
- múltiples observaciones Scout por jugador;
- Modelo No Name configurable;
- criterios ponderados reales;
- plantilla sombra;
- Player Report 360 sin datos inventados;
- decisiones por temporada;
- búsquedas SQL en zonas de volumen;
- cierre de sesión limpiando contexto local;
- centro de calidad de datos;
- backup técnico y auditoría;
- generación PDF bajo demanda;
- capa robusta de tendencias/decisión DD unificada.

### Mejoras futuras recomendadas, no urgentes

#### A. Dividir repositorios demasiado grandes

`repositories/scouting.py` sigue siendo el mayor punto de mantenimiento (aprox. 1.465 líneas). Funciona y está cubierto por tests, pero conviene dividirlo por dominio cuando hagamos una refactorización dedicada.

#### B. Reducir sesiones en pantallas DD/Scout

`pages/director.py` y `pages/scout.py` tienen varias aperturas `session_scope()` por render. Muchas están condicionadas por sección y no se ejecutan todas a la vez, pero hay margen para agrupar lecturas y reducir latencia con Supabase.

No se ha forzado esta refactorización en 3.7 porque tocarla junto con el cambio de calendario aumentaría el riesgo sin beneficio funcional inmediato.

#### C. Historial visual de cambios de horario

Los cambios ya quedan en `audit_logs`, pero todavía no existe una línea temporal específica visible en la ficha del partido (`domingo provisional → sábado 18:00 → domingo 12:00`). Puede añadirse más adelante sin cambiar el modelo de datos.

#### D. Posiciones por tramos

La aplicación conserva una posición observada por participación. Ya se corrigió la posición del suplente, pero un futbolista que juega 45' de MC y 45' de lateral sigue teniendo una sola posición final de participación. Solo merece una migración si el uso real demuestra que DD necesita ese nivel de precisión.

#### E. Análisis rival estructurado

El formulario de equipo/rival es útil, pero su resultado consolidado se guarda principalmente en `result_summary`. Si con el uso diario se convierte en una pieza central, podría evolucionar a un modelo estructurado propio para comparar rivales entre jornadas.

## Conclusión

La 3.7.0 no intenta “arreglar otro formato de rango”. Elimina la causa de complejidad.

La regla queda alineada con el funcionamiento real de una competición regional:

```text
Federación publica jornada y fecha de referencia
              ↓
Partido provisional · horario pendiente
              ↓
DD puede planificar qué observar
              ↓
Administración recibe el horario real
              ↓
Confirma fecha + hora
              ↓
Se habilitan postpartido, informes y observaciones Scout
```

Es más simple, más difícil de romper y representa mejor lo que realmente sabemos en cada momento.
