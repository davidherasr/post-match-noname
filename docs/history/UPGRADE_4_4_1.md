# No Name · Área Técnica — actualización 4.4.1

## Qué resuelve

- Las notas individuales y colectivas se eligen pulsando directamente **1–10** o **Sin evaluar**. El 0 sigue sin computar; las notas decimales guardadas por versiones anteriores se conservan y se muestran sin redondearlas.
- Tras entregar correctamente un informe, se sale del editor, se limpia el estado temporal de ese informe y se vuelve a **Inicio**, donde aparece la confirmación y un acceso a la ficha del partido. Si la entrega falla, el usuario permanece en el formulario y los cambios no se dan por incorporados.
- Un Informador puede **rechazar una asignación pendiente** desde Inicio, Jornada o su lista de trabajo; requiere confirmación y acepta motivo opcional. Deja de contar como tarea o asignación activa. Un borrador existente permanece en PostgreSQL y solo vuelve a editarse si se reactiva; no se pueden rechazar informes ya entregados. Administración puede reactivar una asignación seleccionando al Informador de nuevo.
- Dirección Deportiva **no hereda** permiso de Informador. Un Administrador puede otorgar expresamente ambos roles; entonces la persona podrá elegir voluntariamente cualquier postpartido propio publicado desde Jornada y elaborar su propio informe. Se crea una asignación opcional auditada; los partidos neutrales siguen su lectura independiente. No se crean misiones Scout.

## Preparación de despliegue

1. Conserva una copia del ZIP **4.4** realmente desplegado y realiza un respaldo PostgreSQL **restaurable** más copia separada del bucket. El backup tabular de la app no equivale a `pg_dump`.
2. Sustituye el **proyecto completo** por el ZIP 4.4.1, conservando los Secrets de Streamlit y `DATABASE_URL` fuera del repositorio. No mezcles archivos ni incluyas SQLite local, `secrets.toml`, logs o tokens.
3. El head Alembic sigue siendo `0013_data_governance_4_2_3`: no hay migración nueva. El estado `declined` utiliza la columna `report_assignments.status` ya existente (VARCHAR(30)). Ningún informe, asignación o usuario se modifica automáticamente durante el despliegue.
4. Comprueba VERSION/commit en Streamlit Cloud tras el reinicio y ejecuta el recorrido de aceptación indicado abajo. La app no ha sido conectada desde esta entrega a tu instancia de Supabase.

## Prueba funcional antes de compartir con todo el staff

- Informador: abre un partido asignado, pulsa 7 u 8 en dos jugadores, comprueba nota exacta y que **Sin evaluar** no promedia 0; guarda ambos bloques, confirma entrega y comprueba que vuelve a Inicio con un mensaje y que DD ve el informe incorporado.
- Comprueba un informe con nota decimal histórica: sigue mostrando 8,5 y solo cambia si el usuario elige otra nota.
- Informa de una asignación que no puede realizar: pulsa **No puedo realizar este informe**, confirma rechazo, verifica que desaparece de Inicio y que el borrador (si existía) no se ha eliminado. Administración puede reactivarlo.
- Intenta rechazar un informe ya entregado: el backend debe denegar la operación.
- Usuario solo DD: no debe poder empezar a puntuar. Desde Administración añade el rol Informador a una cuenta DD autorizada; ahora puede abrir Jornada y **Realizar mi propio informe · opcional** en un postpartido propio publicado. No debe poder usar esa acción en neutrales, archivados o partidos de prueba.
- Verifica las operaciones anteriores con dos cuentas distintas y en móvil; comprueba que una nota pulsada se conserva cuando se guarda y se vuelve a abrir.

**Integridad:** no hay operaciones destructivas nuevas. `declined` no borra informes ni estadísticas; los datos en borrador nunca forman parte de agregados oficiales. El borrado definitivo administrativo continúa separado y requiere las salvaguardas existentes.
