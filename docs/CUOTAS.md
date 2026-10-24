# Cuotas públicas y The Odds API en EdgeLab (v0.8)

## DunkAPI: estadísticas para los player props NBA

Además de The Odds API, el motor NBA puede conectarse a **DunkAPI** por `DUNKAPI_API_KEY` (secreto independiente). Se importan hasta dos perfiles diarios con los últimos diez juegos y reporte de lesiones, para estimar probabilidades y riesgos. No publica los datos brutos del proveedor y no mezcla porcentajes implícitos del bookmaker con probabilidades predictivas. El saldo gratuito es de 500 créditos/mes; su actualización se limita a un máximo nominal de 14 créditos diarios. Consulta [Guía de instalación DunkAPI](DUNKAPI.md).

## The Odds API para player props

El flujo de ESPN Core continúa funcionando sin clave. The Odds API es una integración **opcional** para obtener player props NBA/NHL. Configura un secret de Actions llamado `THE_ODDS_API_KEY`. Nunca escribas esa clave en README, HTML, JavaScript, tests, commits o URLs de páginas públicas.

**Protocolo:** https://api.the-odds-api.com/v4 (distinto de odds-api.io y theoddsapi.com). El endpoint `/sports/{sport}/events` descubre eventos sin consumo de créditos. El endpoint `/sports/{sport}/events/{id}/odds` consulta un partido con `markets=<prop>`, `regions=us`, `oddsFormat=decimal`.

**Control de gasto:** cada despliegue solicita como máximo un mercado de un solo encuentro, con coste máximo esperado de un crédito; se leen las cabeceras `x-requests-remaining` y `x-requests-last`. Se reserva un mínimo de 40 créditos; ante cuota desconocida se evita la solicitud de pago. El despliegue actual corre cada tres horas (~240 créditos/30 días de 30 días si siempre hay un mercado publicado). La API puede responder sin mercados disponibles; un status `market_not_available` no es error de autenticación.

**Cobertura inicial:** NBA (`player_points`, `player_rebounds`, `player_assists`) y NHL (`player_shots_on_goal`, `player_points`), alternando un mercado por actualización. Estos precios se integran con ESPN Core en el mismo `odds.json`. Un fixture debe coincidir por fecha, liga, local y visita; si hay ambigüedad se omite. Se conservan las líneas y nombres de cada jugador y de cada casa, sin asumir probabilidades predictivas para props. El panel muestra `Sin modelo` hasta proporcionar estadísticas de jugadores.

**Activación:** GitHub → `lichaco/edgelab-analytics` → Settings → Secrets and variables → Actions → New repository secret → `THE_ODDS_API_KEY`. Pega la clave en ese campo. Después, `Actions` → `Publicar EdgeLab en GitHub Pages` → Run workflow para activar una publicación; cron cada tres horas. El contenido del secret **no puede recuperarse** desde GitHub.

**Seguimiento:** en `assets/data/odds.json`, `diagnostics.the_odds_api` contiene el estado, mercado consultado, props añadidas, créditos consumidos y restantes, sin revelar la clave. Una configuración ausente devuelve `not_configured`, sin afectar a ESPN Core. Comprueba las condiciones de redistribución de The Odds API antes de publicar las cuotas en un sitio público.

Fuentes: [docs oficiales v4](https://the-odds-api.com/liveapi/guides/v4/), [mercados disponibles](https://the-odds-api.com/sports-odds-data/betting-markets.html), [planes](https://the-odds-api.com/).

## ¿Necesito pagar o tener una clave?
**No.** El proveedor principal de EdgeLab es **ESPN Core**, con datos públicos de cuotas prepartido de casas que ESPN identifica en cada encuentro. No necesitas `ODDS_API_IO_KEY` ni otra cuenta.

El sitio se puede abrir en [GitHub Pages](https://lichaco.github.io/edgelab-analytics/). El workflow `.github/workflows/pages.yml` actualiza aproximadamente cada tres horas el calendario y el archivo `assets/data/odds.json`. No se consulta ESPN directamente desde el navegador para mostrar las cuotas.

En la primera consulta real del 24 de octubre de 2026, se revisaron **93 encuentros** y ESPN entregó cuotas de referencia para **56**, identificadas como **DraftKings**. Es un dato histórico de verificación, no una promesa de disponibilidad permanente.

## Mercados y análisis

- **Ganador / moneyline:** se muestran las cuotas decimales de ambos lados cuando la fuente publica precios. En fútbol solo se considera `1X2` si también publica el empate.
- **Over/Under del partido:** se muestran línea y precios solo si ambos aparecen realmente en la fuente. Para fútbol los totales de goles con líneas x.5 pueden compararse con Poisson.
- **Hándicap (spread):** línea desde la perspectiva del equipo local, con precios de cada lado cuando ESPN los comunica.
- **Córners, tarjetas y props individuales:** no se inventan. ESPN Core no garantiza estos mercados; permanecen ausentes si no aparecen.
- **Detección de valor:** EV = P(modelo) × cuota decimal − 1, exclusivamente para modelos disponibles. Cuando hay más de una casa con el **mismo mercado y línea**, EdgeLab puede mostrar una comparación de referencia entre casas y debe etiquetarla de forma diferente. Ninguna señal garantiza rentabilidad.

## Cómo se comprueba cada cuota

1. El calendario genera próximos partidos de fuentes públicas.
2. El recolector busca identificadores de encuentro publicados por ESPN; para las ligas europeas empareja partidos por equipos y fecha/hora con umbrales conservadores.
3. Solicita las cuotas por encuentro a `sports.core.api.espn.com/v2/sports/{sport}/leagues/{liga}/events/{id}/competitions/{id}/odds`.
4. Convierte los precios americanos a decimales solo cuando ESPN comunica un valor numérico válido.
5. Publica casa, línea, selección, precio, referencia y hora de actualización disponible. No añade precios por defecto (como -110).

**Fuentes:** [documentación comunitaria de ESPN Core](https://github.com/pseudo-r/Public-ESPN-API) y [ESPN sobre DraftKings](https://support.espn.com/hc/en-us/articles/20503151864852-How-to-use-ESPN-with-DraftKings). Son endpoints **no oficiales**: pueden cambiar, omitir cuotas o quedar inaccesibles.

## Límites prácticos y de uso

- Referencias prepartido, **no cuotas ejecutables en directo**. Pueden variar según la región, casa y momento.
- La primera cobertura real de 56/93 no representa un porcentaje garantizado en fechas futuras.
- El recolector limita los partidos y las consultas por ciclo para evitar consultas masivas; no accede a cuentas de apuestas ni sortea bloqueos.
- **La accesibilidad pública no equivale a autorización de reutilización o redistribución.** La web y el archivo JSON son públicos. Para un sitio comercial o redistribución amplia, se requiere verificar condiciones con los titulares de los datos o contratar una fuente licenciada.
- CS2 y Euroliga continúan pendientes. Los player props NBA/NHL se pueden enriquecer con The Odds API cuando el secret esté configurado; ESPN por sí solo no los garantiza.
- El modelo Poisson de fútbol aún necesita calibración y evaluación histórica por competición.

## Archivos

| Archivo | Función |
|---|---|
| `scripts/build_public_odds.py` | Descarga y normaliza precios de ESPN sin clave |
| `scripts/build_the_odds_api.py` | Enriquece con props NBA/NHL y controla el consumo de créditos |
| `assets/js/odds-dashboard.mjs` | Tablero de cuotas, filtros dinámicos por casa y señales |
| `assets/js/value-engine.mjs` | Compara probabilidades y mercados equivalentes |
| `assets/js/calendar.mjs` | Muestra cuotas de referencia en las tarjetas de partidos |
| `tests/test_public_odds.py` | Pruebas de conversión, mercados, emparejamiento y lectura segura |
| `.github/workflows/pages.yml` | Actualización programada y publicación |

**Alternativa desactivada:** `scripts/build_odds.py` mantiene una integración de pago opcional con Odds-API.io para cuando se necesiten más mercados. **No se ejecuta** en GitHub Pages por defecto.

## Diagnóstico

Consulta el estado en `https://lichaco.github.io/edgelab-analytics/assets/data/odds.json`; en `diagnostics` están el número de eventos consultados, las casas encontradas y las incidencias. El archivo solo contiene cuotas que la fuente devolvió y datos públicos de partidos.

Si no ves la versión nueva, haz una recarga completa del navegador (Ctrl + Shift + R).
