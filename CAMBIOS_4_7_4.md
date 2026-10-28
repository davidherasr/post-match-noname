# No Name · Área Técnica — 4.7.4

## Qué se ha corregido respecto a la 4.7.3

Esta actualización se centra en **integridad de valoraciones y facilidad de uso**, no en añadir otra vía de informes colectivos.

1. **Perfil Consulta realmente de solo lectura.** El servidor rechaza valoraciones creadas por cuentas con `participation_profile=viewer`, aunque el cliente envíe una petición directa. Menús y guardado respetan la misma restricción.
2. **Retirar una valoración individual.** El componente móvil muestra «Sin nota individual», envía la retirada explícita y conserva una contribución retractada para auditoría. Las notas retractadas ya no cuentan en medias ni historiales activos. Se puede volver a puntuar después.
3. **Reparación de fusiones.** La fusión de fichas de jugador considera las claves foráneas de los módulos nuevos (aportaciones, propuestas, solicitudes, etc.), ajusta las claves del componente móvil y rechaza uniones con evidencia incompatible. No borra a ciegas registros firmados.
4. **Suplentes participantes.** Una persona autorizada puede incorporar a un suplente que entró tras la publicación, con identidad, dorsal, posición y minuto, sin sobrescribir los 22 titulares. Aparece inmediatamente como jugador valorable. Un suplente no participante permanece excluido de las valoraciones.
5. **Medias consistentes.** Un resumen canónico de notas individuales deduplica por jugador-partido-informador, privilegia la valoración individual vigente y mantiene separados los datos cuantitativos. La ficha de jugador y la tabla de plantilla emplean la misma función; no hay límite artificial de cien aportaciones para calcular medias.
6. **Estadísticas estructuradas opcionales.** Los analistas pueden asociar pases completados/intentados y duelos ganados/disputados a un jugador del partido, con fuente. Se valida que los aciertos no superen los intentos y no se utiliza ese dato para inventar o alterar una nota subjetiva.
7. **Mis valoraciones por encuentro.** El historial personal agrupa puntuaciones por partido, indica cuántos futbolistas se valoraron y permite regresar al encuentro para editarlas.
8. **Recorrido único para el Informador ocasional.** Su ficha de partido abre directamente el nuevo componente móvil de valoración nominal; ya no cae en el formulario colectivo antiguo.
9. **Navegación cotidiana simplificada.** Las funciones narrativas antiguas no se ofrecen como editores alternativos de valoración. Los informes históricos permanecen consultables.
10. **Documentación histórica organizada.** Manuales de versiones anteriores archivados en `docs/history/`, sin borrarlos ni modificar migraciones antiguas.

## Conservado sin cambios de contrato

- Preparación de partido con dos titulares XI completos, nombres, dorsales y posiciones.
- Publicación explícita por editor habilitado; los Informadores no pueden puntuar antes.
- Perfil de Dirección Deportiva, propuestas expresas, privacidad de otros Informadores, solicitudes de seguimiento y consulta histórica.
- Tablas, modelos y migraciones anteriores; **la cabeza Alembic permanece `0019_rating_release_4_7_3`**, sin nueva migración.

## Límites y pendientes

- No se han certificado visualmente todos los recorridos en una sesión completa de Streamlit Cloud/Supabase.
- No se ha implementado todavía un editor específico para **reconciliar errores del XI ya publicado**. Una corrección debe tratarse como incidencia controlada; se prohíbe sustituir masivamente el once publicado.
- La incorporación de suplentes requiere un minuto de entrada conocido; no inventamos minutos no confirmados.
- Los informes históricos no se convierten de forma destructiva a la nueva estructura; se preservan y pueden consultarse.
- El componente móvil de valoración existe, pero no es todavía una aplicación React independiente ni se han eliminado todos los archivos Python heredados: algunos siguen dando soporte a funciones técnicas y compatibilidad.
