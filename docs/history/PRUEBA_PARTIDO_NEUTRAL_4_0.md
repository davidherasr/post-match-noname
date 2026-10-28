# Prueba rápida 4.0 · partido neutral

Para comprobar el nuevo flujo sin crear datos falsos:

1. Despliega 4.0 sobre el mismo Supabase.
2. Abre **Jornada** y entra en un partido que no sea de No Name.
3. En **Estudio del partido**, marca si existe vídeo.
4. Marca la formación de cada equipo de forma independiente.
5. Para un equipo con formación conocida, selecciona el sistema, carga/actualiza su plantilla si hace falta y guarda el XI observado. Debe aparecer el campograma.
6. Para un equipo sin formación conocida, pega la lista de la Federación. Debe mostrarse como lista ordenada por dorsal y **no** debe convertirse automáticamente en una alineación del partido.
7. En **Scouting**, comprueba que puedes filtrar `Ambos / Local / Visitante` antes de hacer Barrido, Observación o Dossier.
8. Vuelve a Jornada: el partido debe indicar vídeo sí/no y `formaciones X/2`.

Caso esperado similar a Sarego-Cubillos:

```text
Vídeo: según disponibilidad real
Sarego: formación conocida → campograma
Cubillos: formación desconocida → plantilla/dorsal
```

La aplicación no debe exigir una formación de Cubillos para poder estudiar sus jugadores.
