> **Estado posterior / hotfix 4.2.3.1:** en las capturas del Informador (La Cistérniga – C.D. Noname J1) se observó `Informes 0/0`, sin botón de informe ni tareas. Causa de código: 4.2.3 permitía publicar sin Informadores (solo warning) y luego Inicio/Jornada requieren asignación. La 4.2.3.1 exige informador para nuevas publicaciones, añade asignación/reasignación desde Match Hub del partido **ya publicado**, permite abrir el editor directamente desde Inicio y explica falta de asignación. 117 tests OK; Alembic sigue 0013. ZIP de 4.2.3.1 es la nueva candidata; Cloud + Supabase reales sin probar. Consultar `UPGRADE_4_2_3_1.md` y `VALIDACION_4_2_3_1.md`. No borrar el partido J1 ni hacer SQL manual para repartir informes.

> Actualización 4.2.3: Admin selecciona C.D. Noname real por ID; el equipo «Noname Club» y dos encuentros ficticios contra Santa Marta se gestionan como prueba exclusivamente mediante selección administrativa por ID y archivo reversible. Jugadores se rediseña con equipo/temporada/filtros y paginación; entrega de informes pasa directamente a estadísticas y DD (sin aprobación obligatoria). El botón PUBLICAR POSTPARTIDO se hace localizable en el asistente. Head nuevo 0013, sin tocar producción automáticamente.

# CONTEXTO DE CONTINUIDAD — No Name PostMatch

## Qué debe hacer el nuevo chat

Este documento sirve para continuar el desarrollo de **No Name PostMatch** sin reconstruir decisiones anteriores. **Nueva release candidata: 4.2.3**, construida íntegramente desde 4.2.2 (sin mezclar archivos del repositorio desplegado 4.2.1). La 4.2.3 no se ha desplegado ni validado en Cloud/Supabase reales. Tras aceptación y confirmación del despliegue, su ZIP completo pasará a ser la base del siguiente cambio; hasta entonces conservar el ZIP 4.2.2 como retorno y el repo actual 4.2.1 como referencia de despliegue anterior. Leer `UPGRADE_4_2_3.md` y `VALIDACION_4_2_3.md`.

Regla de trabajo: **no inventar datos deportivos, no resetear Supabase, no borrar histórico y no afirmar que una release está validada si no se ha ejecutado realmente la validación**. Cuando se entregue una versión nueva, el usuario prefiere un ZIP completo, no parches de archivos sueltos.

---

## 1. Producto

Aplicación interna de fútbol para **No Name** construida con **Python + Streamlit + SQLAlchemy + Alembic + PostgreSQL/Supabase**.

Navegación visible actual:

- **Inicio**
- **Jornada**
- **Jugadores**
- **Dirección Deportiva**
- **Administración** (solo Admin)

No debe existir un directorio físico `pages/`, porque Streamlit lo interpreta como navegación multipágina automática. Las pantallas internas están en `views/`.

---

## 2. Filosofía deportiva actual (4.2)

### Partidos de No Name

Se tratan como **postpartidos**, no como scouting.

Objetivo:

- evaluar el rendimiento de No Name;
- valorar al rival;
- valorar jugadores propios y rivales cuando corresponda;
- recoger opiniones del staff;
- detectar consenso y discrepancias;
- construir histórico de rendimiento de plantilla.

Un jugador de No Name **nunca** debe aparecer como candidato de mercado ni ofrecer un botón del tipo “iniciar seguimiento del #9 de No Name”. Los jugadores propios se leen como **rendimiento/evolución de plantilla**.

### Partidos neutrales

Son partidos en los que No Name no participa. No requieren un postpartido completo.

Cada Informador puede dejar una **lectura ligera**:

- valoración del equipo local;
- valoración del visitante;
- comentario/resumen;
- jugadores externos que le hayan llamado la atención;
- nota/comentario opcional de esos jugadores.

Señalar un jugador crea una **señal**, no un seguimiento automático.

Flujo deseado:

**staff observa → DD agrega y compara → aparecen señales repetidas → una persona autorizada inicia seguimiento individual → Player Report 360 acumula evidencia → DD decide.**

---

## 3. Roles y permisos

Los roles organizativos visibles son únicamente:

- **Administrador**
- **Dirección Deportiva**
- **Informador**

Los roles son **independientes y acumulables**. No existe “rol principal” visible y un Admin no hereda automáticamente DD o Informador.

### Administrador

Administra la aplicación:

- usuarios;
- roles y accesos;
- calendario;
- equipos;
- plantillas;
- horarios;
- calidad de datos;
- configuración.

Un **Admin puro no debe poder escribir postpartidos ni lecturas neutrales**. Para hacerlo necesita además el rol Informador.

### Dirección Deportiva

No asigna “misiones Scout”. La arquitectura anterior `DD → Scout → Barrido/Observación/Dossier` fue descartada porque no representa cómo funciona el staff real.

DD funciona como **centro de inteligencia deportiva**:

- lectura transversal entre jornadas;
- jugadores señalados;
- equipos;
- discrepancias;
- partidos recientes;
- consenso ponderado;
- tendencias;
- criterio/peso de cada miembro del staff;
- plantilla y Modelo No Name.

### Informador

Es quien **puntúa y documenta** lo observado:

- postpartidos de No Name;
- lectura de partidos neutrales;
- notas y valoraciones.

Un DD puro tampoco puntúa por el hecho de ser DD: necesita Informador si quiere escribir valoraciones.

### Seguimiento individual

**No existe rol Scout activo.**

Existe un permiso independiente por usuario:

`Puede realizar seguimiento individual de jugadores` (`can_track_players`)

En la práctica, el usuario principal puede tener este permiso y el resto del staff no.

Solo un usuario con este permiso puede transformar una señal de un jugador externo en seguimiento real y alimentar el **Player Report 360**.

Los antiguos datos Scout pueden conservarse históricamente en base de datos, pero no deben reaparecer como flujo operativo activo.

---

## 4. Dirección Deportiva 4.2.1+

Se añadió lectura **transversal**, no solo partido a partido.

Debe incluir como mínimo:

- **Panorama**
- **Jugadores señalados**
- **Equipos**
- **Discrepancias**
- **Partidos recientes**

Para jugadores señalados debe poder calcular/mostrar, cuando existan datos:

- número de partidos distintos en que aparece;
- número de menciones;
- número de miembros del staff distintos;
- quiénes lo señalaron;
- nota ponderada;
- tendencia;
- origen de las señales (neutral/postpartido);
- repetición entre jornadas.

Las discrepancias deben traducirse a lenguaje útil, por ejemplo `Consenso alto`, `Opiniones divididas`, `Discrepancia alta`, y permitir volver al partido de origen.

Inicio debe enlazar directamente a **DD → Lectura deportiva → Jugadores señalados** cuando haya señales pendientes/relevantes.

---

## 5. Peso de las opiniones del staff

Dirección Deportiva puede configurar pesos diferentes por persona para:

- **Partidos de No Name**
- **Partidos neutrales**

El peso es una decisión deportiva, no administrativa.

Las medias/consensos importantes deben ser **ponderados**, no simples, cuando existan pesos configurados.

---

## 6. Jornada, Federación, convocatoria y formación

Conceptos separados:

- **Plantilla** = jugadores conocidos del equipo en la temporada.
- **Convocatoria** = jugadores que estuvieron disponibles/convocados para ese partido.
- **Titulares** = XI inicial.
- **Suplentes** = banquillo.
- **Formación** = colocación táctica de los 11 titulares.

La Federación **no siempre aporta formación o XI fiable**, por lo que la app no debe inventarlos.

### Formación conocida por equipo de forma independiente

En un partido neutral puede ocurrir:

- local: formación conocida;
- visitante: formación desconocida;

Si formación conocida:

- mostrar campograma;
- seleccionar exactamente 11 titulares;
- guardar también suplentes/banquillo.

Si formación desconocida:

- mostrar lista de jugadores/convocados;
- ordenar por dorsal cuando sea posible;
- permitir estudio sin inventar posiciones tácticas.

### Desplegables del XI

- Los jugadores ya seleccionados desaparecen de los otros selectores para impedir duplicados y facilitar el trabajo.
- El jugador actual sigue disponible en su propio selector para poder cambiarlo.
- Backend también valida que no haya duplicados.
- Diferenciar visualmente:
  - `TIT`
  - `SUP`
  - `PLANTILLA`

### Texto plano Federación

Formato preferido:

```text
TITULARES
1;NOMBRE;POR
2;NOMBRE;LD
...

SUPLENTES
12;NOMBRE;POR
14;NOMBRE;MC
```

También se admite formato compacto:

```text
T;1;NOMBRE;POR
S;12;NOMBRE;POR
```

Si se pega solo:

```text
1;NOMBRE
2;NOMBRE
3;NOMBRE
```

se trata como **plantilla/lista sin estado conocido**. Nunca inferir que los primeros 11 son titulares.

---

## 7. Usuarios y contraseñas

Administración dispone de gestión completa de usuarios:

- Listado
- Añadir
- Editar
- Eliminar (soft delete)
- Restaurar eliminados
- Activar/desactivar
- Cambiar roles y accesos
- Cambiar contraseña
- Activar/desactivar `can_track_players`

La eliminación es **lógica/soft delete** para preservar observaciones, informes y auditoría.

Protecciones:

- no eliminar/desactivar la propia cuenta conectada;
- no eliminar o quitar el último Administrador activo.

### Contraseñas

Por decisión del usuario, **no hay política de complejidad**.

Cualquier contraseña **no vacía** es válida, incluso `1` o `1234`.

Cambiar contraseña es opcional; no existe cambio obligatorio en primer acceso.

---

## 8. Player Report 360

El dossier no se selecciona como “nivel de scouting”. Se construye con el historial real del jugador externo:

- observaciones;
- partidos vistos;
- señales;
- evolución;
- fortalezas/riesgos;
- encaje;
- decisiones por temporada.

No reintroducir un selector `Barrido / Observación / Dossier` como paso obligatorio.

---

## 9. Base de datos y Alembic

Producción usa PostgreSQL/Supabase.

Head esperado en 4.2.2:

`0012_sporting_reading_4_2`

Historial reciente:

- `0010_core_workspace_schema_repair_4_0_4`
- `0011_user_lifecycle_4_1_1`
- `0012_sporting_reading_4_2`

En una incidencia anterior se confirmó que `alembic_version.version_num` de Supabase necesitaba más de 32 caracteres y se amplió a **VARCHAR(128)**. No volver a diseñar revision IDs que dependan de VARCHAR(32) sin tenerlo en cuenta.

4.2.2 **no añade migración**.

### Hotfix de arranque 4.2.2

En producción, 4.2.1 mostró:

`Tipo de error: KeyError · Versión 4.2.1`

durante el arranque de base de datos.

No se obtuvo todavía el traceback completo de Manage app → Logs, por lo que no debe afirmarse una causa exacta no confirmada.

4.2.2 endurece el arranque de forma segura:

- lee el head incluido en la release;
- lee directamente `alembic_version`;
- si Supabase ya está exactamente en el head, **no invoca `alembic upgrade` otra vez**;
- aun así valida el contrato físico del esquema;
- si la base está por detrás, Alembic se ejecuta normalmente;
- un `KeyError` solo puede recuperarse si después se verifica head correcto + esquema físico completo;
- los logs indican la fase exacta del fallo: configuración, migraciones/esquema, bootstrap o carga de ajustes.

Si 4.2.2 vuelve a fallar en producción, pedir **el traceback completo de Manage app → Logs** antes de hacer más cambios.

---

## 10. Despliegue

Streamlit Cloud + repositorio GitHub.

Al actualizar:

1. sustituir **todo** el contenido de código por la release completa;
2. no mezclar archivos de distintas versiones;
3. conservar `.git/` en el repositorio;
4. conservar Secrets en Streamlit Cloud, nunca incluir credenciales reales en el ZIP/repo;
5. no tener `pages/`;
6. no subir SQLite local (`postmatch_scout.db`, `-wal`, `-shm`);
7. commit/push;
8. `Manage app → Reboot app`.

`RUN_MIGRATIONS = true` es el comportamiento esperado en producción, pero 4.2.2 evita ejecutar Alembic si la base ya está en el head.

Usar preferentemente la **Session pooler connection string** de Supabase.

---

## 11. Seguridad / secretos

No incluir en nuevos chats, ZIPs, documentación o respuestas:

- contraseña real de Supabase;
- contraseña real de Administrador;
- service role key;
- cualquier Secret de producción.

Los artefactos deben contener únicamente `.streamlit/secrets.example.toml` con placeholders.

En conversaciones anteriores se llegaron a pegar credenciales reales; si aún no se han rotado, conviene hacerlo, pero no repetirlas en texto.

---

## 12. Validación de release esperada

Antes de decir al usuario que una release está validada, ejecutar realmente:

- `pytest`
- `compileall`
- `scripts/check_release_consistency.py`
- migración fresh hasta head
- cuando aplique, prueba de upgrade desde la revisión anterior
- reextraer el ZIP final y volver a comprobarlo
- verificar ausencia de:
  - `pages/`
  - SQLite de usuario
  - `secrets.toml` real
  - caches innecesarias

Para 4.2.2, en la carpeta de trabajo se obtuvieron:

- **109 tests passed**
- `compileall` OK
- consistencia OK
- fresh migration hasta `0012` OK
- `0011 → 0012` OK

La prueba final del ZIP extraído debe mantenerse como requisito antes de afirmar validación definitiva.

---

## 13. Estilo de colaboración con el usuario

- Responder en español.
- Ser directo y práctico.
- El usuario prefiere decisiones claras y que se le contradiga cuando el diseño no tiene sentido.
- No vender como “arreglado” algo que no se ha probado.
- Ante errores, trabajar con el traceback exacto y no adivinar.
- Para releases, entregar **ZIP completo** y explicar si hay o no migración.
- No pedir una captura por cada pequeño dato si se puede agrupar la información necesaria.

---

## 14. Estado al abrir el nuevo chat

Base funcional objetivo: **No Name PostMatch 4.2.2**.

Prioridad inmediata:

1. desplegar 4.2.2 completa;
2. reiniciar Streamlit;
3. comprobar si desaparece el `KeyError` de arranque;
4. si falla, copiar el traceback completo de `Manage app → Logs`;
5. después continuar el desarrollo funcional desde 4.2.2 sin recuperar el modelo antiguo de Scouts/misiones.

