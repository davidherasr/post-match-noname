# Publicación y valoración individual · No Name Área Técnica 4.7.3

## Regla principal

Un encuentro del calendario **no es un encuentro disponible para valorar**. Solo los partidos con publicación explícita en `match_rating_releases_473` se muestran como abiertos a los Informadores. La publicación exige **los once titulares identificados de ambos equipos, con dorsal, nombre y posición de ese encuentro**. Ni horario, ni resultado, ni suplentes, ni descripción colectiva son obligatorios.

El usuario con permiso entra en Administración → «Preparar y publicar partido», o desde Partidos. Pega los dos XI o sube un `.txt` / `.csv` por equipo. Cada fichero se interpreta como el XI del equipo seleccionado. Primero aparece la vista previa; solo la segunda confirmación publica. No se publica media alineación.

## Formatos admitidos

Por cada equipo, once líneas `dorsal;nombre;posición`; `TITULARES` puede ser cabecera opcional. También se admite `dorsal;nombre;posición;T` o `;S`, o bloque `SUPLENTES` opcional (suplentes pueden carecer de posición):

```text
TITULARES
1;Chuchi;POR
2;Yago;LD
15;Asiel;DCD
5;Aziz;DCI
3;Brian;LI
14;Jacobo;MCD
8;Barbero;MCI
11;Migui;ED
18;Cruz;MP
17;Jymbox;EI
19;Adri;DC
SUPLENTES
9;León
```

Una lista parcial, con dorsal duplicado, nombres duplicados, posiciones erróneas o distinto de once titulares **no se publica**. El nombre de equipo no se repite en las filas. Se admiten `POR`, `LD`, `LI`, `DCD`, `DCC`, `DCI`, `DFC` (heredado), `CAD`, `CAI`, `MCD`, `MCC`, `MCI`, `MC`, `MD`, `MI`, `MP`, `ED`, `EI`, `SD`, `DC`. En este esquema **MCD = mediocentro derecho** y **MCI = mediocentro izquierdo**. Se requiere exactamente un `POR` por XI y números de dorsal únicos por equipo.

Las posiciones son **del partido**, no necesariamente el puesto habitual de cada futbolista. No se infiere ningún sistema táctico ni se coloca a nadie de manera automática por orden de pegado. El diagrama de campo refleja solamente los códigos suministrados.

## Perfiles y permisos

- **Administrador**: puede preparar y publicar; dispone de enlace principal desde Administración.
- **Dirección Deportiva**: puede preparar y publicar con su permiso DD; puede valorar si también tiene rol Informador.
- **Analistas** con perfil completo o libre: pueden preparar/publicar, además de valorar.
- **Informador ocasional `own_only`** y **perfil consulta**: no pueden preparar ni publicar.

El permiso se comprueba en el repositorio, no solo por botones. Solo se publica un partido no aplazado ni suspendido, una vez disputado.

## Después de publicar

- Para Informadores aparece el **último encuentro publicado** de Noname. Los no publicados no se convierten en formularios disponibles. Hay acceso secundario a encuentros anteriores ya publicados.
- Una única pantalla de valoración individual muestra a los titulares de Noname por nombre, dorsal y posición, con pestaña secundaria para el rival. No se exige puntuar a todos, ni una nota colectiva, ni texto sobre el sistema del equipo.
- Cada nota está firmada por autor y partido, se puede corregir sin duplicar opiniones, y es privada para autor y DD/administración según la política anterior. Marcar favorito es la única vía de propuesta explícita a DD.
- DD puede comparar notas acumuladas desde Plantilla / Jugadores. La media muestra su muestra real: no convierte jugadores sin nota en cero ni duplica una misma valoración editada.
- Los suplentes listados como convocados sin constancia de entrada no figuran como jugadores evaluables. Las notas de suplentes solo son válidas cuando la participación se acredita.
- La alineación publicada queda protegida frente a reemplazos masivos: cualquier cambio de identidad que pueda afectar a observaciones firmadas requiere una corrección auditable, no volver a importar el XI. No hay todavía un flujo visual completo de reconciliación posterior a publicación.

## Migración desde versiones anteriores

`0019_rating_release_4_7_3` añade una tabla, sin borrar ni modificar informes, observaciones o alineaciones de versiones previas. **No habilita automáticamente partidos históricos**, aunque tengan una alineación; deben publicarse expresamente. Si un partido ya tiene dos XI correctos y posiciones, Administración puede publicarlo sin volver a pegar su texto. No se cambian manualmente los estados `public.alembic_version` ni las tablas de Supabase.
