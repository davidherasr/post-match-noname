# Dirección Deportiva 3.3 · Liga + scouting de segundo nivel

## Flujo de producto

```text
PARTIDO
  ↓
INFORME POSTPARTIDO RÁPIDO
  ↓
JUGADOR DESTACADO / REPETIDO / INTERESANTE
  ↓
DIRECCIÓN DEPORTIVA
  ├─ descarta / mantiene en base
  ├─ lo ubica provisionalmente en el modelo
  └─ solicita FICHA SCOUT
          ↓
     INFORMADOR / SCOUT
          ↓
     FICHA AVANZADA
          ↓
     DIRECCIÓN DEPORTIVA
          ↓
     OJEADO + DECISIÓN FINAL
```

## Dirección Deportiva

La navegación principal mantiene:

- Panorama
- Jugadores
- Por posiciones
- Equipos
- Seguimiento
- Comparador
- XI de la liga
- Consenso
- Informes
- Listas

Y se conecta con el nuevo apartado global **Jugadores ojeados**.

### Panorama

Prioriza decisiones, no estadísticas decorativas:

- jugadores conocidos;
- perfiles repetidos;
- fichas scout abiertas;
- destacados recientes;
- tendencias sostenidas;
- perfiles con opiniones divididas;
- jugadores con muestra suficiente pero sin decisión.

### Jugador 360

Resume lo que sabemos de verdad:

- equipo y posición observada;
- media, última nota y muestra;
- informadores distintos;
- dispersión;
- confianza 0–100;
- evolución;
- comentarios postpartido;
- decisión DD y seguimiento.

Desde aquí DD puede pulsar **Abrir ficha scout / ubicar en nuestro modelo**.

## Jugadores ojeados

### Observados

Todos los rivales con informes aprobados. Es una puerta de entrada al scouting avanzado, no una segunda base de datos.

### Fichas solicitadas

Dirección Deportiva define inicialmente:

- posición en nuestro modelo;
- rol previsto;
- responsable de la ficha.

El informador recibe esa ficha en su propio menú y rellena solo aquello que realmente puede sostener.

### Ficha scout del informador

Bloques:

- posición observada;
- nivel actual;
- proyección;
- encaje en el modelo;
- técnico/táctico/físico/mental;
- atributos específicos de la posición opcionales;
- fortalezas;
- aspectos a mejorar/riesgos;
- resumen;
- recomendación.

No se exige rellenar atributos que no hayan podido observarse.

### Cierre DD

Dirección Deportiva conserva la última palabra:

- posición definitiva en el modelo;
- rol;
- encaje DD;
- nivel/proyección DD;
- decisión final;
- conclusión propia.

Al cerrar, el jugador pasa a **Ojeados** y queda como expediente reutilizable.

## Modelo de No Name

No se intenta crear una taxonomía universal. Los roles son internos y simples: central dominante/corrector/iniciador, pivote/recuperador/organizador, extremo vertical/asociativo, delantero referencia/móvil/profundidad, etc. El objetivo es responder:

> Si nos interesase este jugador, ¿dónde y para qué lo utilizaríamos nosotros?
