# Laboratorio de análisis multideporte: del chat a EdgeLab

Implementación v1 en la rama feature/analisis-multideporte-con-fuentes.

## Propósito

Reproducir los *métodos* de análisis empleados en conversaciones, **no** presentar valores históricos del chat como datos vigentes. El repositorio ya procesa calendario y cuotas ESPN Core para algunos mercados; el laboratorio adicional recibe un JSON de estadísticas y cuotas trazables. No está conectado directamente al historial de ChatGPT ni a sus herramientas de búsqueda.

**Flujo:** calendario confirmado → estadísticas previas a la fecha del evento → cuota de la misma línea/casa → predicción con advertencias → probabilidad implícita → cuota justa → EV → revisión de lesiones, minutos y calidad de evidencia.

## Modelos implementados y requisitos

| Deporte | Mercados | Variables requeridas | Enfoque |
|---|---|---|---|
| Fútbol | Over de goles, córners y tarjetas | Al menos 5 totales históricos comparables, línea, odds y fuente | Poisson o binomial negativa con dispersión declarada; el módulo anterior mantiene 1X2 |
| NBA/WNBA | Over puntos, rebotes, asistencias, triples y totales | 5–10 valores históricos, minutos estimados y base, dispersión, rival, probabilidad de blowout si existe | Normal aproximada con mezcla de dos escenarios de minutos |
| NHL | Over tiros, goles, asistencias y puntos | Historial, minutos de hielo previstos/base | Poisson con factor de tiempo sobre hielo |
| CS2 | Ganador BO3, Over 2.5 mapas y hándicaps ±1.5 | Ranking HLTV, últimos 10 BO3 de ambos equipos y victorias/partidos de los siete mapas | Rating de forma ponderado por tiempo y ranking; tasas bayesianas por mapa y veto tentativo |

**Restricciones:** no aplicar sobre/under a líneas no equivalentes, no imputar lesiones, no mostrar cuotas hipotéticas como reales. Probabilidades sin backtest se identifican como exploratorias. La marca de verificación aportada por un usuario en JSON **no demuestra** verificación independiente.

## Fuentes utilizadas o discutidas en los análisis

| Área | Fuentes de referencia | Cómo se usan hoy |
|---|---|---|
| Fixtures/odds base | ESPN, ESPN Core, OpenFootball | Calendar y cuotas base ya integrados en el repositorio |
| Fútbol europeo/Chile | football-data.co.uk, football-data.org, Soccerway, ESPN, datos públicos de ligas | Candidatas a normalizar una vez validados licencia y cobertura |
| xG y fútbol avanzado | FBref, Understat (cuando exista acceso permitido) | Fuentes propuestas, no colectores conectados |
| Probabilidades externas vistas en el chat | TotalOdds, DATA FUT, PredictLix, StakeVista, TACTIX, Forepitch, SoccerGhost, Pizarra Labs | **No conectadas**: no mezclar estimaciones sin metodología o licencia verificables |
| CS2 | HLTV.org (ranking, resultados, mapas y veto), PandaScore, proveedores de estadísticas autorizados | Referencias a investigar; **no hay scraper HLTV integrado** |
| NBA | NBA.com/stats, nba_api, ESPN, Dimers, proyecciones externas | Player stats/lesiones/props **no conectados** |
| NHL | NHL.com, MoneyPuck, ESPN, PuckOdds | Stats/props **no conectados** |
| Cuotas | ESPN Core/DraftKings donde figure; proveedor comercial opcional | ESPN Core ya integrado; props solo donde proveedor autorizado entregue mercado, línea y timestamp |

El uso de páginas públicas no demuestra que permitan scraping o redistribución. Revisar términos y licencias antes de activar pipelines.

## Esquema de importación

Descarga la plantilla desde **Laboratorio · Análisis con contexto**. El archivo admite \`{ "schema": 1, "records": [...] }\` (hasta 1000 registros). Cada registro necesita:

- \`fixture_id\`: ID exacto del encuentro en \`assets/data/calendar.json\`.
- \`sport\`: \`football\`, \`basket\`, \`nhl\` o \`cs2\`.
- \`market\`: objeto \`{kind,side,line}\`, donde kind es específico del deporte.
- \`source\`: nombre, URL HTTPS, \`captured_at\` ISO8601 y opcional \`verified\`.
- \`quote\`: \`{decimal,book,source}\` con fuente y fecha propias.
- Estadísticas del deporte. \`last10\` se ordena desde **más reciente a más antiguo**. En CS2, \`last10_bo3\` requiere \`{win:0|1,opponent_rank}\` y \`maps\` requiere \`{wins,played,ban_rate}\` por mapa.

Un veto confirmado se puede incluir como \`veto_confirmed:{maps:["Mapa1","Mapa2","Mapa3"]}\`; sin él, se utiliza un veto **probable y simplificado**, no oficial. No se ingieren cuotas automáticamente desde capturas del chat.

## Criterios de señal

Solo identifica como *candidato* registros con cuota **estrictamente superior a 1.80**, actualizada en las últimas 8 horas, dos fuentes declaradas verified y EV experimental superior a 2.5%. **Candidato no significa apuesta validada**. La señal no se presenta si no hay modelo, cuota o partido futuro verificable.

## Próximas integraciones

1. Obtener históricos completos con permisos de uso y snapshot por fecha, sin contaminación temporal.
2. Enriquecer con lesiones, probable alineación, minutos, portero inicial, árbitro, tarjetas, córners y datos de mapas/veto.
3. Unificar IDs y timestamps; permitir conectar datos al laboratorio sin JSON manual.
4. Calibrar distribuciones y ajustar pesos contra temporadas históricas mediante rolling-origin, Brier/log-loss y closing-line value.
5. Integrar seguimiento de apuestas individuales, ganancias netas por unidad y resultados sin guardar credenciales en GitHub Pages.
