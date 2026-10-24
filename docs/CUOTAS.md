# Cuotas automáticas y detector de valor (v0.5)

EdgeLab consulta el proveedor **Odds-API.io** exclusivamente desde GitHub Actions. El navegador de GitHub Pages consume el resultado estático 'assets/data/odds.json'; **la clave nunca se incorpora al HTML, JavaScript ni archivo JSON**.

## Activación (única acción manual del propietario)

1. Consigue una clave válida de Odds-API.io que permita acceder a **Betano** y **DraftKings**. La creación de nuevas claves gratis está pausada, según la página del proveedor (consulta condiciones vigentes).
2. Abre GitHub > repositorio > **Settings > Secrets and variables > Actions > New repository secret**.
3. Nombre exacto: **ODDS_API_IO_KEY**. Valor: tu clave real. No la escribas en issues, commits, GitHub Pages ni en un mensaje.
4. Abre **Actions > Publicar EdgeLab en GitHub Pages > Run workflow** para generar el primer snapshot.
5. En 'https://lichaco.github.io/edgelab-analytics/' busca **Cuotas automáticas y detector de valor**. Para diagnosticar, abre '/assets/data/odds.json' y revisa únicamente 'diagnostics', que no contiene la clave.

Sin una clave funcional, el sitio muestra el aviso **not_configured** y ninguna cuota. No hay datos ficticios de prueba.

## Qué está automatizado

- Consulta los eventos prepartido anunciados por el proveedor para los deportes soportados, usando sus identificadores y hasta 10 eventos en cada solicitud de 'odds/multi'.
- Filtra eventos que ya comenzaron y **empareja por local/visita + hora ±14 h**. Las coincidencias ambiguas se descartan.
- Registra únicamente líneas efectivamente recibidas de Betano/DraftKings en **formato decimal**, con mercado, línea, selección, casa y fecha de actualización cuando el proveedor la informa.
- Ordena señales automáticamente, sin introducir cuotas manualmente.
- **Fútbol:** usa Poisson de resultados históricos y calcula EV solo para 1X2 completo (incluido empate) y totales de goles con línea **x.5**. Córners y tarjetas se listan pero aún no tienen modelo predictivo independiente.
- **NBA/WNBA/NFL/NHL:** muestra las cuotas disponibles; si **ambas casas** cotizan exactamente el mismo mercado, jugador y línea, calcula una *referencia de precio relativa* quitando el margen de la otra casa. Esa comparación **no equivale a una probabilidad predictiva validada**.
- No etiqueta como positiva una señal con diferencia inferior a 2,5 % en modelo o 4 % en referencia de mercado. Son umbrales ilustrativos que deben validarse, no promesa de acierto.
- Suspende las señales cuando el snapshot tiene más de 8 horas. GitHub Actions actualiza aproximadamente cada 3 horas, sujeto al programador de GitHub, límites del proveedor y fallos de red.

## Limitaciones reales

- GitHub Pages no puede guardar secretos del lado cliente ni consultar un proveedor de cuotas de pago directamente de forma privada.
- Las cuotas son **instantáneas**, no precios de ejecución en tiempo real. Pueden cambiar antes de abrir una casa de apuestas.
- Ninguna fuente garantiza presencia de DraftKings y Betano en todas las ligas. Si no hay partidos coincidentes, datos o mercados accesibles, el panel permanece sin cuotas.
- No hay apuestas automatizadas ni conexión a cuentas de casas de apuestas.
- CS2 no tiene calendario integrado, y por tanto tampoco hay matching de cuotas CS2. Euroliga y props con datos históricos siguen pendientes.
- La ausencia de pronóstico de un deporte nunca se sustituye por una probabilidad inventada. La referencia de otra casa se presenta con su propia etiqueta.
- La página y el archivo de cuotas serán públicos mientras este GitHub Pages esté publicado. Nunca se exponen credenciales, pero los **precios** se vuelven públicos; confirma que el plan y contrato del proveedor permiten redistribuirlos públicamente antes de usarlo.

## Costos y llamadas

Se hacen a lo sumo dos consultas de eventos por deporte que aparezca en el calendario más una consulta por cada 10 eventos emparejados, con máximo 70 partidos por actualización. Son hasta aproximadamente 17 solicitudes en un ciclo que cubre los cinco deportes. Si no hay clave, son cero solicitudes.

Revisa límites concretos de tu plan y ajusta 'MAX_EVENTS', 'SPORTS' o el horario del workflow si fuera necesario.

## Desarrollo y pruebas

- Backend: 'scripts/build_odds.py'
- Motor de comparación: 'assets/js/value-engine.mjs'
- Interfaz: 'assets/js/odds-dashboard.mjs', 'assets/css/odds.css'
- Pruebas: 'tests/test_build_odds.py' y 'tests/value-engine.test.mjs'
- Despliegue: '.github/workflows/pages.yml'

Comprobar: 'npm test', 'npm run check', 'PYTHONPATH=. python3 -m unittest discover -s tests -p "test_*.py"'.

**Fuentes y documentación de API:**
- https://odds-api.io/integrations/betano
- https://odds-api.io/blog/draftkings-api
- https://odds-api.io/blog/compare-odds-multiple-bookmakers-api
- https://odds-api.io/pricing/free
