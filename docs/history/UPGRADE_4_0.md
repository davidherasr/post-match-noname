# Actualización a No Name PostMatch 4.0.0

## Antes de actualizar

Genera un backup técnico desde Administración. **No cambies de proyecto Supabase, `DATABASE_URL` ni Secrets.**

## Migración

4.0.0 incorpora una migración aditiva y no destructiva:

```text
0007_product_consolidation_3_8
        ↓
0008_match_study_4_0
```

Añade contexto de estudio a `matches` y conserva todos los partidos, jugadores, plantillas, informes, observaciones Scout, misiones, decisiones y documentos existentes.

Las formaciones ya guardadas se marcan automáticamente como conocidas. No se crea ninguna formación ficticia para los lados que no tengan una.

## Qué cambia al abrir un partido neutral

Dentro de **Jornada → partido** aparece `Estudio del partido`:

- Vídeo disponible: Sí/No.
- Formación local: Sí/No.
- Formación visitante: Sí/No.
- Referencia de vídeo opcional.
- Notas generales.

Si una formación es conocida, se elige el sistema y se puede construir el XI sobre campograma. Si no se conoce, la aplicación muestra la plantilla de temporada ordenada por dorsal y permite pegar directamente la lista de la Federación.

## Formatos de plantilla Federación

Una línea por jugador. Se aceptan, entre otros:

```text
1;Ángel Pérez;POR
7 Mario López
10 - Carlos Gómez
Pedro García
```

No se inventan dorsales ni posiciones que no estén presentes.

## Despliegue

Sustituye **todo** el contenido del repositorio por el ZIP 4.0.0.

```bash
git add -A
git commit -m "No Name PostMatch 4.0.0 - Match Study"
git push origin main
```

Después realiza **Reboot app** en Streamlit Community Cloud. Mantén `RUN_MIGRATIONS=true` para que Alembic aplique `0008_match_study_4_0` automáticamente.
