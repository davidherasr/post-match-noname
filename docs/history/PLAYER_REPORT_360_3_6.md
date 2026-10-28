# Player Report 360 · Diseño funcional 3.6

## 1. Cabecera

Cada expediente muestra primero la información que permite entender al jugador sin navegar por tablas:

- nombre;
- equipo observado;
- posición principal;
- rol propuesto dentro del Modelo No Name;
- valoración media postpartido;
- encaje No Name;
- confianza 0–100.

Los KPI se acompañan siempre de contexto. Una nota media no oculta el tamaño de muestra y el encaje no aparece si Dirección Deportiva/Scout todavía no lo ha evaluado.

## 2. Resumen

El Resumen está pensado para que Dirección Deportiva pueda decidir en segundos. Reúne:

- conclusión consolidada;
- fortalezas;
- dudas/riesgos;
- recomendación;
- técnico, táctico, físico y mental cuando realmente han sido valorados;
- nivel actual;
- proyección;
- media de scouting específico.

## 3. Modelo No Name

El radar no utiliza atributos genéricos. Utiliza los criterios configurados en el rol del **Modelo No Name**.

Ejemplo:

```text
DC · Profundidad
- Desmarque de ruptura · peso 5
- Ataque de profundidad · peso 5
- Ataque de área · peso 4
- Presión · peso 4
- Juego de espaldas · peso 3
```

Si existen menos de tres criterios puntuados, el radar no se dibuja y se informa de que todavía no hay evidencia suficiente.

Dirección Deportiva puede consolidar sus propias puntuaciones de criterios por temporada. Si no existen, el expediente utiliza las observaciones Scout disponibles para resumir los criterios realmente puntuados.

## 4. Evolución

La línea temporal diferencia claramente:

- `Postpartido`: valoración surgida de un partido de No Name;
- `Scout específico`: visionado intencionado;
- partido;
- fecha;
- posición observada;
- nota;
- observador;
- comentario.

No se ponderan artificialmente las notas Scout. La mayor calidad de un visionado específico se representa mediante el nivel de evidencia, no multiplicando la puntuación.

## 5. Observaciones y confianza

La ficha explica la evidencia que sostiene la decisión:

- postpartidos aprobados;
- observaciones Scout enviadas;
- número de observadores;
- dispersión/consenso;
- recencia;
- confianza 0–100;
- fuerza de evidencia Scout específica.

## 6. Comparativa

### Nuestra plantilla

Dirección Deportiva puede mapear futbolistas actuales de No Name a un rol y puntuar:

- encaje;
- nivel actual;
- proyección;
- criterios configurados.

El candidato se compara únicamente con jugadores internos asignados al mismo rol.

### Perfiles similares de nuestra liga

Se muestran candidatos que comparten el mismo rol y cuya similitud puede sostenerse con criterios reales. Cuando no existen suficientes criterios comunes, se utiliza únicamente la proximidad de encaje disponible y se indica como contexto; nunca se inventan atributos.

## 7. Datos

Solo aparecen datos almacenados realmente en la base:

- nombre;
- equipo;
- posición;
- fecha de nacimiento/edad si existe;
- pie si existe;
- nacionalidad si existe;
- decisión actual.

No se generan valor de mercado, altura, goles, asistencias ni otras estadísticas externas.

## 8. Decisión DD

Dirección Deportiva dispone de un cierre propio por temporada:

- posición/rol No Name;
- encaje;
- nivel actual;
- proyección;
- criterios del modelo;
- estado de seguimiento;
- prioridad;
- conclusión de DD.

Esto permite conservar opiniones distintas en temporadas posteriores sin borrar el historial anterior.

## 9. Documentos

### Ficha Scout Ejecutiva

Documento compacto para compartir internamente. Incluye:

- cabecera y KPI;
- conclusión;
- fortalezas/riesgos;
- radar y criterios si hay datos suficientes;
- recomendación/decisión;
- nivel actual y proyección.

### Dossier Player Report 360

Añade:

- perfil Scout;
- posiciones observadas;
- evolución completa;
- comparativa contextual;
- datos disponibles;
- trazabilidad de fuentes internas.

Ambos documentos se generan bajo demanda para no añadir latencia al flujo habitual.
