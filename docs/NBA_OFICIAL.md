# Estadísticas NBA oficiales — EdgeLab v1.0

## Qué se conectó

Fuente primaria, cuando está accesible:

- Calendario NBA: `https://cdn.nba.com/static/json/staticData/scheduleLeagueV2_1.json`, con respaldo al nombre `scheduleLeagueV2.json`.
- Box score final: `https://cdn.nba.com/static/json/liveData/boxscore/boxscore_{GAME_ID}.json`.
- Campos: `points`, `reboundsTotal`, `assists`, `threePointersMade`, `minutes` / `minutesCalculated` y `personId`.
- Solo se aceptan partidos NBA de temporada regular con `gameStatus=3`, ID oficial `002xxxxxxx`, fecha anterior a la predicción, información de dos equipos coincidente y **al menos cinco juegos del mismo jugador**. Se excluyen DNP y partidos con menos de 12 minutos. Los últimos 10 box scores disponibles se ponderan por recencia.

El proveedor no garantiza estos endpoints como API pública de terceros; **403 Forbidden y bloqueos a IP de GitHub Actions son posibles**. No se usan proxies ni procedimientos para evitar restricciones. En ese caso el colector emite `nba_cdn_unavailable` y el panel utiliza proyecciones DunkAPI si están configuradas y cumplen los requisitos.

## Mercado, muestras y cálculo

**The Odds API** proporciona cuotas de player props `player_points`, `player_rebounds`, `player_assists` y ahora `player_threes`. El modelo conecta las cuotas con sus resultados utilizando ID de fixture, nombre exacto de jugador, línea numérica, tipo de mercado y misma casa, respetando el timestamp. Si aún no hay cuotas Over **mayores que 1.80**, el colector igualmente **precarga en caché privada los box scores oficiales** correspondientes a los dos próximos partidos NBA del calendario dentro de 48 horas. No publica pronósticos hasta contar con una cuota coincidente y suficientes partidos.

El modelo es **experimental**: medias ponderadas de los últimos 5–10 partidos oficiales y desviación estándar muestral con piso mínimo, ajuste moderado de media por tendencia de minutos y aproximación normal. **No está validado retrospectivamente**; su EV positivo puede estar sobreestimado.

Importante: no se estima automáticamente una probabilidad de blowout; tampoco se extraen informes oficiales de lesiones mediante el CDN de box scores. Las estimaciones de NBA oficial son visibles como *exploratorias*, pero **no** se promocionan a señales automáticas hasta verificar el estado del jugador. Los modelos de DunkAPI conservan sus comprobaciones existentes.

Al inicio de temporada puede haber menos de cinco partidos nuevos de un mismo jugador. El modelo marca `insufficient_sample`, no rellena estadísticas ni mezcla automáticamente otros torneos.

## Fuente e integridad

- Solo se solicitan encuentros cuyo calendario oficial esté en estado final, hasta 75 días atrás.
- Límite **24 box scores nuevos por despliegue**; respuestas de partidos finalizados quedan en la caché privada de GitHub Actions, nunca en el directorio de publicación.
- El colector escribe `assets/data/nba_official_predictions.json` con **predicciones derivadas**, no box scores brutos ni datos personales de acceso.
- Sin clave adicional. La actualización se ejecuta después del proceso normal de calendario, ESPN, The Odds API y DunkAPI.
- Si el calendario oficial falla, **no** se tratan viejos datos cacheados como nuevos para fabricar estimaciones.
- Hay dos archivos cacheados bajo `.edgelab-cache`: `dunkapi-private.json` y `nba-official-private.json`. Se restauran por GitHub Actions y no se copian a Pages.

## Diagnóstico

Consulta `https://lichaco.github.io/edgelab-analytics/assets/data/nba_official_predictions.json`, cuyos estados posibles incluyen:

| Estado | Significado |
|---|---|
| `no_prop_markets` | Sin cuotas NBA compatibles ni encuentros próximos para precargar |
| `preload_ready` | Box scores oficiales cacheados para próximos partidos; sin cuota compatible todavía |
| `nba_cdn_unavailable` | Fuentes NBA bloqueadas/no disponibles; DunkAPI puede funcionar como respaldo |
| `no_final_games` | No se encontraron box scores definitivos pertinentes |
| `insufficient_sample` | No hay cinco juegos oficiales por jugador |
| `ok` | Se generaron al menos una o más probabilidades experimentales |

Los datos descargados deben emplearse respetando términos y derechos de NBA.com; su visibilidad en un CDN no equivale a licencia de redistribución comercial.

## Referencias

- <https://github.com/swar/nba_api/blob/master/docs/nba_api/live/endpoints/boxscore.md>
- <https://github.com/swar/nba_api/blob/master/docs/nba_api/live/endpoints/scoreboard.md>
- <https://github.com/swar/nba_api>
- <https://www.nba.com/stats>
