# Fuentes potenciales (pendientes de evaluar)

| Área | Ejemplo de fuente | Uso previsto | Riesgo por confirmar |
|---|---|---|---|
| Fútbol | https://www.football-data.co.uk/data.php | Históricos resultados y cuotas | Condiciones de acceso, reuso y cobertura tarjetas/córners |
| Fútbol | https://www.football-data.org/ | Calendario y resultados | Cobertura plan gratuito y Chile |
| NBA | https://github.com/swar/nba_api | Stats NBA | API no oficial y límites |
| WNBA / Euroliga | Estadísticas oficiales | Boxscores | Acceso automatizado y licencia |
| CS2 | https://cs2-api.org/ | Mapas y resultados | Histórico, ligas y cuotas |
| NHL | https://www.moneypuck.com/data.htm | Estadísticas y tiros | Licencia y formato de archivos |
| NFL | https://github.com/nflverse/nflverse-data | Play-by-play, jugadores | Frecuencia y disponibilidad |
| Odds | https://the-odds-api.com/ | Cuotas | Precio, endpoints props, históricos, deportes |

La inclusión en la lista **no** significa que ya esté conectado, disponible en un plan gratuito o autorizado para todas las operaciones. Antes de pagar, comprobar una muestra real de las ligas/mercados requeridos, frecuencia de captura, límites y reglas de uso.

## Fuente NBA conectada en v1.0

- **NBA oficial CDN (primaria):** `https://cdn.nba.com/static/json/staticData/scheduleLeagueV2_1.json` y `https://cdn.nba.com/static/json/liveData/boxscore/boxscore_{gameId}.json`, sin clave pero con posibles respuestas 403 o límites de red. Se derivan puntos, rebotes, asistencias, triples y minutos de partidos finalizados; no se replica el dataset bruto. [Documentación](NBA_OFICIAL.md).
- **DunkAPI (respaldo):** si no hay muestra NBA verificable o el CDN está inaccesible, el módulo conserva las proyecciones DunkAPI preexistentes bajo las reglas de su plan gratuito.
- **The Odds API (precios):** cuotas de NBA individuales, incluido el mercado `player_threes`, condicionadas a publicación y límites de créditos.
