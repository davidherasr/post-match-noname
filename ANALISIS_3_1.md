# Auditoría de rendimiento, accesibilidad y simpleza · 3.1.0

## Problema de partida

La versión 3.0 ya resolvía correctamente el dominio de No Name, pero conservaba un coste típico de Streamlit conectado a una base remota: demasiadas ejecuciones completas del script y demasiadas oportunidades de volver a consultar PostgreSQL durante tareas de edición.

El objetivo de 3.1 es que la base remota sea **persistencia**, no el estado vivo de cada slider.

## Cambios con mayor impacto

### 1. Evaluar un equipo ya no significa guardar jugador por jugador

Antes, el diseño podía provocar una secuencia repetitiva de lectura/edición/escritura. En 3.1 cada plantilla funciona como una unidad de trabajo:

- la pantalla carga partido, participaciones y evaluaciones;
- los widgets se editan dentro de un `st.form`;
- Streamlit no envía los cambios al servidor hasta pulsar Guardar;
- una única función de repositorio precarga las evaluaciones existentes y actualiza todo el bloque en una transacción;
- autorización, control de concurrencia y auditoría se resuelven una vez por bloque.

### 2. Secciones realmente perezosas

Se eliminaron `st.tabs` del flujo principal. Streamlit ejecuta el contenido de pestañas aunque no estén visibles; la aplicación usa ahora radios/rutas que ejecutan únicamente la sección seleccionada.

Esto afecta a informes, dirección deportiva, mantenimiento, partidos y jugadores.

### 3. Menos consultas repetidas

- sesión de usuario revalidada como máximo cada 90 s salvo acciones sensibles;
- bootstrap memorizado por proceso;
- configuración visual/operativa cacheada 180 s;
- progreso de varios partidos del dashboard resuelto en lote;
- fichas de jugadores de No Name recuperadas con una consulta `IN` en lugar de una consulta por jugador;
- historial de rival cargado solo cuando el usuario lo solicita;
- documentos y versiones consultados solo en su sección;
- PDF Completo bajo demanda.

### 4. Administración guiada por formación

Una formación conocida genera una estructura conocida. La aplicación no pide al usuario volver a describirla.

El once rápido de No Name fija las 11 posiciones y solo pide nombres. Para el rival genera la misma plantilla de posiciones editable.

### 5. Accesibilidad

Se revisaron:

- contraste;
- foco visible;
- tamaño mínimo de interacción;
- etiquetas de controles;
- lectura móvil;
- reducción de movimiento;
- texto de ayuda orientado a acción;
- campos bloqueados cuando el informador no debe editarlos.

## Principio de diseño resultante

**Preparar → trabajar en local → guardar en bloque → persistir.**

El usuario no debe notar Supabase mientras puntúa. Solo debe esperar cuando abre datos nuevos o cuando decide guardarlos.

## Qué sigue siendo deliberadamente remoto

No se cachean de forma agresiva borradores compartidos, aprobaciones o datos que puedan cambiar por otro usuario. En esos puntos se prioriza consistencia sobre una falsa sensación de velocidad.

## Objetivo de uso

Para un partido ya preparado, un informador que solo quiera poner notas debería poder completar una plantilla en aproximadamente un minuto, sin apartados colectivos obligatorios y sin esperas entre jugadores.
