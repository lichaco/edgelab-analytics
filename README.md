# EdgeLab Analytics

## Nuevo: laboratorio de análisis con fuentes (v0.7, pendiente de revisión)

Se incorpora un módulo que importa observaciones JSON de **goles, córners, tarjetas, player props NBA/NHL y BO3 CS2**. Calcula probabilidad, cuota implícita, cuota justa y valor esperado, con avisos de lesiones, minutos, tiempo en hielo, antigüedad de cuotas y escenarios de veto. Para fútbol, el módulo previo sigue calculando **1X2** y Over de goles.

**No está conectado automáticamente a ChatGPT, HLTV ni a proveedores de props.** Requiere observaciones y cuotas fechadas, verificables, obtenidas de fuentes con permiso de uso. Tampoco incluye automáticamente todas las cifras de conversaciones anteriores. Se puede descargar una plantilla desde la web. Consulta [metodología, fuentes y formato](docs/ANALISIS_CHAT.md).


Panel personal de análisis deportivo, construido inicialmente con **HTML, CSS y JavaScript**, sin framework ni dependencias de ejecución.

> **Estado v0.6:** calendario automático y cuotas de referencia gratuitas de ESPN Core integrados con GitHub Pages. Actualmente se identifican precios de DraftKings donde están publicados. El modelo de fútbol sigue siendo experimental y las probabilidades no están calibradas como predicciones rentables.


## Estadísticas oficiales NBA (v1.0)

**Fuente principal para NBA:** endpoints públicos usados por NBA.com en `cdn.nba.com` (calendario oficial y box scores definitivos). Se extraen hasta los diez partidos recientes de un jugador, con puntos, rebotes, asistencias, triples y minutos; se exige muestra mínima de cinco juegos. Los históricos brutos se cachean internamente en GitHub Actions; **solo se publican probabilidades derivadas**.

Se combinan con cuotas reales de **The Odds API** por evento, jugador, casa y línea; DunkAPI continúa como **respaldo** si las fuentes NBA no responden o hay muestra insuficiente. Este acceso NBA no requiere clave, pero los endpoints son **no oficiales para terceros**, pueden responder HTTP 403 y no garantizan cobertura desde GitHub Actions. Al comienzo de la temporada puede faltar un mínimo de cinco juegos y el modelo muestra *sin muestra suficiente*, sin inventar predicciones.

Consulta [Fuentes NBA oficiales, límites y estados](docs/NBA_OFICIAL.md). Los pronósticos siguen siendo experimentales y no están calibrados fuera de muestra.
## DunkAPI — proyecciones NBA con la cuenta gratuita (v0.9)

Se puede activar **DunkAPI** mediante el secreto de GitHub Actions `DUNKAPI_API_KEY` (cuenta gratuita: 500 créditos/mes). EdgeLab cruza los player props Over >1.80 de The Odds API con estadísticas y minutos recientes de DunkAPI, calcula una probabilidad **exploratoria**, cuota justa, EV y advertencias por lesiones/minutos y blowout no cuantificado.

El plan gratuito se controla con una caché de Actions y un máximo de dos jugadores nuevos por día. **No se publica el histórico bruto de DunkAPI**: solo pronósticos derivados, sujetos a requisitos de muestra y frescura. El sistema no consulta DunkAPI si no hay cuota NBA compatible ni credenciales.

Para activar la clave, revisar costos y límites, consulta [Guía DunkAPI](docs/DUNKAPI.md). Las proyecciones no están calibradas ni garantizan ganancias.
## The Odds API — player props gratuitos (v0.8)

Se añadió `scripts/build_the_odds_api.py` al despliegue de GitHub Pages. Si existe el **secret** `THE_ODDS_API_KEY`, cada actualización consulta los endpoints de eventos gratuitos y realiza como máximo **una** consulta de cuotas de un evento / un mercado / una región (coste máximo esperado: 1 crédito). Alterna entre **NBA: puntos, rebotes, asistencias** y **NHL: tiros a portería, puntos**; sin evento coincidente o sin mercado publicado no se inventan cuotas.

El plan Starter de The Odds API anuncia 500 créditos mensuales. Con un cron de 3 horas, el consumo máximo planificado es ~240 créditos en 30 días; además, el recolector deja una reserva de 40 créditos consultando la cabecera de cuota. Las cuotas se fusionan con las de ESPN Core en `assets/data/odds.json`, **no** se reemplazan las existentes. La clave nunca se incorpora al HTML ni al JSON publicado.

**Falta configurar el secret para activar la integración**: repositorio → Settings → Secrets and variables → Actions → New repository secret → Name: `THE_ODDS_API_KEY` → pegar el valor. Más detalles en [Cuotas](docs/CUOTAS.md).

## Calendario automático

- **Fútbol:** Premier League, La Liga, Serie A, Bundesliga, Ligue 1 y Primera División chilena.
- **Básquetbol:** NBA y WNBA (Euroliga pendiente de proveedor).
- **NHL y NFL:** encuentros futuros.
- **CS2:** el calendario sigue pendiente de una fuente licenciada para uso analítico relacionado con apuestas; no se inventan torneos.
- Puedes filtrar por deporte, liga, equipos y horizonte de 7, 14 o 30 días. Los horarios se convierten a **America/Santiago** y los encuentros iniciados se excluyen.
- Seleccionar **Analizar** autocompleta evento y fecha en el formulario. Para fútbol intenta estimar λ local/visita, 1X2 y Over 2,5 con resultados anteriores; para props de NBA/WNBA/NHL/NFL falta introducir estadísticas del jugador hasta conectar un proveedor.
- **Fuente:** la API web pública/no oficial de ESPN, que puede cambiar o restringir el acceso. No se utiliza una clave privada en GitHub Pages. Si una liga no responde, la aplicación avisa y no inventa fechas.
- Las cuotas de referencia se cargan automáticamente cuando ESPN las publica. Los modelos aún carecen de calibración suficiente para afirmar una ventaja real.

## Cuotas de referencia sin API de pago

**Funcionando sin clave:** GitHub Actions ejecuta `scripts/build_public_odds.py` y consulta el feed público no oficial **ESPN Core**. El resultado se publica como `assets/data/odds.json` junto con el calendario. En la primera ejecución verificada se obtuvieron cuotas de **DraftKings para 56 de 93 partidos considerados**. La cobertura puede variar en cada actualización.

El navegador muestra la casa, cuotas en formato decimal, mercados disponibles y fecha de la instantánea. También muestra cuotas en las tarjetas de partido. Para fútbol, compara líneas 1X2 (solo si hay precio de empate) y totales de goles con el modelo Poisson cuando hay suficiente histórico. Sin modelo independiente, **no inventa valor ni porcentaje de acierto**.

No necesitas `ODDS_API_IO_KEY`. Conservamos el colector comercial anterior `scripts/build_odds.py` como alternativa **no activada**, para un eventual futuro con más mercados y Player Props. La actualización gratuita se ejecuta normalmente cada 3 horas.

Los feeds ESPN son públicos **pero no oficiales ni garantizados**, y su accesibilidad no implica licencia de redistribución. La página es pública; revisar derechos de uso antes de convertirla en un producto comercial.

Consulta [fuente, límites, validaciones y funcionamiento](docs/CUOTAS.md).

## Mercados

| Módulo | Cobertura | Modelo inicial |
|---|---|---|
| ⚽ Fútbol (verde) | Premier League, La Liga, Serie A, Bundesliga, Ligue 1, Chile; 1X2, Over goles, córners, tarjetas | Poisson base |
| 🏀 Básquet (naranja) | NBA, WNBA, Euroliga; puntos, rebotes, asistencias, triples | Aproximación normal |
| 🎮 CS2 (amarillo) | BO3/BO5; ganador serie y hándicaps de mapas | Binomial simple por mapas independientes |
| 🏒 NHL (azul) | Props de tiros, goles, asistencias | Poisson base |
| 🏈 NFL (morado) | Props de yardas, recepciones y touchdowns | Aproximación normal (reemplazar donde proceda) |

## Cómo probar la web

1. Abre `index.html` en un navegador, **o** usa un servidor local:

   ```bash
   python -m http.server 8000
   ```

2. Entra en <http://localhost:8000>.
3. Elige deporte y selecciona un partido futuro en el **calendario automático**; no necesitas escribir los equipos ni la fecha. Completa el mercado y la cuota decimal si deseas guardar una selección.
4. Exporta tus análisis a CSV o JSON. Los datos permanecen en el `localStorage` de *ese navegador* y *ese origen*; no se sincronizan con GitHub ni con otros dispositivos.

## Publicar cambios en GitHub

Lee [CONTRIBUTING.md](CONTRIBUTING.md). Para empezar:

```bash
# Sustituye TU_USUARIO por tu cuenta de GitHub
git clone https://github.com/TU_USUARIO/edgelab-analytics.git
cd edgelab-analytics
# edita archivos
git checkout -b feature/mi-mejora
git add .
git commit -m "feat: primera mejora"
git push -u origin feature/mi-mejora
```

Crea un **Pull Request** de tu rama a `main`. GitHub Actions revisa la sintaxis JS y ejecuta tests sin dependencias externas.

### Primera subida a repositorio vacío (opción Git local)

```bash
cd edgelab-analytics-github
git init
git branch -M main
git add .
git commit -m "chore: iniciar EdgeLab Analytics"
git remote add origin https://github.com/TU_USUARIO/edgelab-analytics.git
git push -u origin main
```

Alternativamente, usa **Add file → Upload files** en GitHub para subir los archivos descomprimidos. Para que se incluyan carpetas ocultas como `.github`, es más fiable usar Git local.

## Opcional: GitHub Pages

Si no necesitas mantener el sitio privado, configura **Settings → Pages → Deploy from a branch → main / (root)**. El sitio se visualizará en la dirección que proporciona GitHub Pages. Ten presente que las páginas publicadas son accesibles en Internet; no es un sistema de acceso personal protegido. En GitHub Free, Pages está disponible para repositorios **públicos**. Para mantener el código privado y la página accesible solo para ti, conserva el repositorio privado y ejecuta la página localmente o usa hosting con autenticación.

## Seguridad

- **No publiques claves API** en JS, HTML, commits, `.env`, tickets ni archivos de exportación.
- `.gitignore` evita incluir `.env` y `private-data/`, pero comprueba siempre el resultado de `git status`.
- GitHub Pages **no** ejecuta un backend Python ni puede almacenar claves de proveedor en secreto: para estadísticas y cuotas reales necesitaremos una API backend protegida.
- Los partidos se obtienen automáticamente, pero las cuotas continúan siendo manuales; no se muestran odds ficticias.

## Documentación

- [Arquitectura y decisiones](docs/ARQUITECTURA.md)
- [Plan de desarrollo](docs/ROADMAP.md)
- [Fuentes y APIs a validar](docs/FUENTES.md)
- [Cómo contribuir](CONTRIBUTING.md)

## Cálculos

- Probabilidad implícita: `1 / cuota_decimal`.
- Valor esperado por unidad: `p_modelo * cuota_decimal - 1`.
- **No hay calibración histórica** todavía. Un EV positivo bajo supuestos arbitrarios no demuestra una ventaja real.
