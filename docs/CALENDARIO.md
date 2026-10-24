# Calendario automático (v0.4)

EdgeLab obtiene encuentros desde **OpenFootball** (temporadas 2025-26 y 2026-27 para Premier League, La Liga, Serie A, Bundesliga y Ligue 1) y desde los scoreboards diarios no oficiales de **ESPN** (Primera División Chile, NBA, WNBA, NHL y NFL).

## Por qué se cambió

En septiembre de 2026 ESPN dejó de aceptar `dates=YYYYMMDD-YYYYMMDD` y empezó a responder HTTP 400. Ahora cada consulta a ESPN utiliza **una fecha única**, `dates=YYYYMMDD`.

GitHub Actions ejecuta `scripts/build_calendar.py` en cada publicación y, adicionalmente, cada 6 horas. Genera `assets/data/calendar.json` **durante el despliegue**, sin escribir resultados en la rama ni exponer claves. En la página se usa ese archivo estático, con una consulta directa de respaldo cuando falta o falla una fuente. Al pulsar **Actualizar** se intenta refrescar los resultados de las ligas disponibles directamente desde ESPN (por fecha), manteniendo la copia precargada si algún endpoint está temporalmente caído.

## Campos y validaciones

- Los encuentros **finalizados, en curso o con inicio anterior a la hora actual** no se muestran.
- Horario mostrado en la zona **America/Santiago**; cuando una fuente solo publica la fecha, se visualiza «Hora por confirmar» y se **desactiva Analizar** (no se inventa la hora).
- Si una competición no tiene encuentros, la aplicación informa si hubo fallos al consultar la fuente, diferenciando el error de una agenda genuinamente vacía.
- Los datos OpenFootball sirven también para calcular Poisson preliminar; los nombres de equipos y los registros pueden diferir entre proveedores. Las cuotas y player props **no** se cargan automáticamente.
- La información se distribuye mediante GitHub Pages de forma pública. El consumo de proveedor y el número de partidos se guardan en `diagnostics` junto a `generated_at` en el JSON.

## Comprobar publicación

1. Ejecutar `node --test tests/*.test.mjs` y `PYTHONPATH=. python3 -m unittest discover -s tests -p 'test_*.py'`.
2. En **Actions → Publicar EdgeLab en GitHub Pages**, comprobar que se ejecutó el paso **Construir calendario desde fuentes públicas** sin excepciones.
3. Abrir `https://lichaco.github.io/edgelab-analytics/assets/data/calendar.json`; verificar `generated_at`, `fixtures` y `diagnostics`.
4. Abrir `https://lichaco.github.io/edgelab-analytics/` y pulsar **Actualizar** si el calendario figura desactualizado.

Si todos los proveedores fallan, el archivo mostrará diagnósticos y la interfaz mantendrá la opción de consulta directa. No debe presentarse un error de conexión como «no hay partidos».

Fuentes:
- https://github.com/openfootball/football.json
- https://site.api.espn.com (API no oficial; condiciones y disponibilidad pueden cambiar)
