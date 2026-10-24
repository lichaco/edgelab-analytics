# DunkAPI NBA — integración gratuita en EdgeLab (v0.9)

DunkAPI es **una API distinta de The Odds API**. The Odds API aporta cuotas; DunkAPI aporta estadísticas NBA de jugador para proyectar el Over de puntos, rebotes y asistencias.

- Crear cuenta gratuita: https://dunkapi.com/signup
- Documentación REST: https://dunkapi.com/docs/get-player
- Precios: https://dunkapi.com/pricing
- Condiciones de uso: https://dunkapi.com/terms

## Activación

1. Regístrate en DunkAPI, verifica tu correo y genera una clave de su panel (500 créditos gratuitos mensuales, sin tarjeta).
2. Abre https://github.com/lichaco/edgelab-analytics/settings/secrets/actions
3. **New repository secret** → nombre exacto **DUNKAPI_API_KEY** → pega tu clave. No la compartas en chats, commits ni archivos.
4. Ejecuta **Actions → Publicar EdgeLab en GitHub Pages → Run workflow**, o deja que el cron se ejecute. El colector actualiza perfiles exclusivamente en la ventana prevista a las **15:37 UTC** una vez al día si hay props NBA calificadas.

Si no has activado The Odds API, el calendario y las cuotas de ESPN continúan funcionando, pero probablemente DunkAPI no encuentre props individuales; no inventará precios.

## Qué obtiene

- \`search_players\` (1 crédito) resuelve el nombre exacto del atleta y comprueba que pertenece a uno de los dos equipos del partido.
- \`get_player\` (5 créditos) aporta hasta diez partidos recientes, minutos y puntos/rebotes/asistencias.
- \`get_injuries\` (2 créditos) ofrece el reporte de lesiones NBA, si está disponible.
- Solo se analizan Overs **estrictamente superiores a 1.80**, de un **partido futuro de NBA**, con identificación segura de equipos, y coincidencia exacta de **jugador, mercado, casa, línea y precio** respecto de \`odds.json\`.

## Control de gastos del nivel gratuito

- Hasta **dos nuevos jugadores por día**.
- A lo sumo 2 × (1 + 5) + 2 = **14 créditos por día**, o alrededor de **420 créditos en 30 días**, frente a 500 disponibles gratuitamente.
- Se reserva un mínimo de 70 créditos del saldo conocido; las respuestas de DunkAPI informan \`X-Credits-Remaining\`.
- Las estadísticas se mantienen en una **caché interna de GitHub Actions** para evitar facturación en cada despliegue de tres horas.
- Las consultas facturables se limitan a la actualización de **15:37 UTC**; el resto de ejecuciones usa caché. Si la caché se pierde, un reintento dentro de la misma ventana puede gastar créditos adicionales; el proveedor sigue aplicando su propio saldo.
- El primer día solo se estudian hasta dos jugadores. Puede haber partidos sin estimación porque la cobertura es deliberadamente parcial. DunkAPI tampoco se consulta cuando no existe un Over >1.80 publicado.
- El plan gratuito **no acumula** 500 créditos adicionales automáticamente cada mes: según sus términos, después del aniversario de registro recarga hasta 500 si el saldo es menor, para cuentas elegibles.

## Modelo (experimental, no calibrado)

Para un atleta se exigen **al menos cinco juegos con participación y estadísticas válidas en los últimos 45 días**, anteriores al encuentro:

1. Media ponderada exponencialmente de puntos, rebotes o asistencias (hasta diez registros) y desviación estándar muestral con límites conservadores.
2. Minutos de referencia calculados de los cinco partidos más recientes. No son minutos confirmados por entrenador, alineación ni una predicción independiente.
3. Aproximación normal para superar la línea x.5, con su cuota justa = \`1 / P\` y EV = \`P * cuota - 1\`.
4. Revisa reporte de lesiones. Jugadores marcados Out/Doubtful/Inactive **no reciben** pronóstico. Questionable/Day-to-Day muestran alerta, pero no se convierten en señales automáticas.
5. El blowout **no** se cuantifica sin spread y modelo específico. Se advierte al usuario que puede reducir los minutos.
6. No se marca como candidato automático si hay menos de ocho partidos o un reporte de lesiones no reciente, y exige al menos **+8% EV teórico** para evitar señales por diferencias pequeñas.

Estos pesos y supuestos no están calibrados ni validados retrospectivamente; no convierten la frecuencia de los últimos 10 encuentros en probabilidad garantizada. El inicio de una temporada con pocos partidos puede dejar todos los mercados como «sin modelo».

## Publicación y licencia

DunkAPI permite mostrar datos derivados en una aplicación, pero **prohíbe redistribuir datos brutos como feeds, archivos o datasets independientes**, y restringe la redistribución de cuotas masivas.

Por eso:
- La respuesta bruta del proveedor solo está en \`.edgelab-cache/dunkapi-private.json\` de GitHub Actions, que **no se copia a GitHub Pages**.
- La página publica \`assets/data/nba_predictions.json\` con **proyecciones derivadas**, riesgos y fuentes. Nunca publica diez boxscores completos, claves, identificadores internos privados ni respuestas brutas.
- La página sigue mostrando la cuota de origen obtenida previamente de ESPN Core/The Odds API, y la probabilidad independiente si hay datos suficientes.

## Diagnóstico

El archivo público \`https://lichaco.github.io/edgelab-analytics/assets/data/nba_predictions.json\` incluye:
- \`status\`: \`not_configured\`, \`outside_refresh_window\`, \`no_prop_markets\`, \`cached_today\`, \`ok\`, \`no_profiles\` o \`quota_reserved\`.
- \`diagnostics.players_fetched\`, \`credits_estimated_max\`, \`remaining_credits\`.
- \`forecasts\`: solo previsiones con una línea, casa y cuota verificables.

Un JSON vacío **no significa** que la API esté caída: puede faltar la clave, no haber mercados NBA publicados, no haberse alcanzado la hora de actualización o faltar suficientes partidos recientes.

Fuente oficial: https://dunkapi.com/docs/get-player
