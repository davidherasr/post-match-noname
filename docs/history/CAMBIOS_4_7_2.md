# No Name · Área Técnica 4.7.2 — Rediseño real

**Base:** 4.7.1 completa. **Fecha:** 28/10/2026. **Tipo:** revisión de interfaz y flujos; no cambia el esquema PostgreSQL, mantiene `0018_workspaces_4_7`.

## Entregado en la aplicación (no en un prototipo aislado)

- **Valoración móvil con Streamlit Components v2:** interfaz HTML/CSS/JS integrada bidireccionalmente en `ui/mobile472.py`. Se abre desde Mis partidos/Partidos. Nota de Noname con deslizador grande, lista de jugadores por nombre y dorsal, valoración individual y comentario. Un único botón de guardado; persistencia real en `sporting_contributions_47` mediante `repositories/mobile472.py`.
- **Alineaciones desde el teléfono:** en cada partido, «＋ Cargar alineación». Pegar texto `dorsal;nombre` o subir `.txt`/`.csv`; revisión previa de los jugadores reconocidos; confirmación y guardado con permisos. La importación reutiliza las funciones de Federación existentes. Si hay cabeceras `TITULARES`/`SUPLENTES`, registra los participantes indicados. Sin esas cabeceras actualiza **solo la plantilla de temporada**; no inventa quién jugó.
- **Nuestro equipo vs. rival:** si se conoce la alineación, salen jugadores reales; en Noname sin XI se muestra la plantilla con advertencia de que no confirma participación. En el rival sin XI se ofrecen *posiciones provisionales*, con dibujo orientativo configurable; no se crean jugadores ficticios ni participaciones al evaluarlas. La vista cambia entre ambos equipos sin exigir formularios paralelos.
- **Favoritos:** la marca «Destacar expresamente para Aarón» genera una propuesta privada solo después de guardar una observación compartida. Una nota elevada no equivale a una propuesta o decisión de seguimiento. El servidor evita duplicar la misma propuesta por reintentos.
- **Postpartido:** editor visual Components v2 con campos principales para Noname y adversario; detalle opcional, guardar borrador privado o compartir con DD. Conserva la política de inmutabilidad de informes completos una vez compartidos.
- **Bandeja DD/Inicio:** lista visual compacta integrada con eventos reales. Abrir, marcar visto (X), deshacer, guardar y quitar de guardados mantienen el estado de cada usuario. Sin filtros de tipo visibles por defecto.
- **Administración/Jugadores:** selector de resultados visual de una fila por jugador; después, formulario de corrección y eliminación con vista previa de dependencias y confirmación. No se ha debilitado la protección del borrado.
- **Interfaz general:** tipografía editorial sobria, fondo cálido, navegación verde oscura, acción primaria rojo apagado y estilos responsivos; no se usa una fila de 10 botones como selección de nota.
- **Partidos:** los aplazados/cancelados dejan de entrar como «último partido» de la semana. Una fecha pasada sin resultado **no prueba por sí sola que se haya disputado**; el partido sigue abierto a consulta.
- **Síntesis de rival:** se elige el equipo que se está estudiando; solo se sugieren sus encuentros, evitando mezclar automáticamente otros clubes.
- **Conservación de histórico y permisos:** se mantienen documentos, entidades antiguas, decisiones, solicitudes, roles y base Supabase. Operaciones sensibles verificadas en el repositorio, no solo mediante controles ocultos.

## Límites conocidos / qué no debe interpretarse como implementado

- ChatGPT transcribe las capturas **fuera de la app**: debes pegar o subir el texto ya preparado. **No hay OCR de capturas integrado** ni subida automática de fotos al servidor de ChatGPT.
- El backend no interpreta por IA si una posición evaluada del rival corresponde a un nombre real. Su identificación sigue siendo manual y verificable.
- La visualización con controles modernos está implantada en los recorridos principales; **módulos históricos y herramientas avanzadas aún conservan formularios de Streamlit**. No se ha convertido toda la aplicación a React.
- No existe editor de cortes de vídeo integrado ni importación automática del CSV de pases.
- No se ha podido ejecutar la aplicación Streamlit completa con Supabase real desde este entorno. Las pruebas de navegador realizadas corresponden al JS/CSS de los componentes extraídos y montados con datos simulados. Requiere la prueba de despliegue descrita en `VALIDACION_4_7_2.md`.

## Código principal

- `ui/mobile472.py`: componentes Streamlit v2, sin interpolar datos del usuario en HTML.
- `repositories/mobile472.py`: listado de jugadores/puestos, idempotencia, validación de permisos, identidad y persistencia.
- `views/experience47.py`: integración en las rutas reales de la aplicación.
- `core/match_priority472.py`: selección segura de último y próximo partido.
- `core/config.py`, `app.py`, `views/reports.py`, `VERSION`, `scripts/check_release_consistency.py`: control coherente de versión.
- `tests/test_release_4_7_2.py`: pruebas específicas.
