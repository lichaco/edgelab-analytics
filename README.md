# EdgeLab Analytics

Panel personal de análisis deportivo, construido inicialmente con **HTML, CSS y JavaScript**, sin framework ni dependencias de ejecución.

> **Estado v0.3:** calendario automático de partidos, basado en los endpoints públicos (no oficiales) de ESPN. Incluye un estimador Poisson experimental para fútbol cuando hay suficiente histórico. **No** hay cuotas en directo ni modelos de props validados; no se deben interpretar los porcentajes como pronósticos calibrados.


## Calendario automático

- **Fútbol:** Premier League, La Liga, Serie A, Bundesliga, Ligue 1 y Primera División chilena.
- **Básquetbol:** NBA y WNBA (Euroliga pendiente de proveedor).
- **NHL y NFL:** encuentros futuros.
- **CS2:** el calendario sigue pendiente de una fuente licenciada para uso analítico relacionado con apuestas; no se inventan torneos.
- Puedes filtrar por deporte, liga, equipos y horizonte de 7, 14 o 30 días. Los horarios se convierten a **America/Santiago** y los encuentros iniciados se excluyen.
- Seleccionar **Analizar** autocompleta evento y fecha en el formulario. Para fútbol intenta estimar λ local/visita, 1X2 y Over 2,5 con resultados anteriores; para props de NBA/WNBA/NHL/NFL falta introducir estadísticas del jugador hasta conectar un proveedor.
- **Fuente:** la API web pública/no oficial de ESPN, que puede cambiar o restringir el acceso. No se utiliza una clave privada en GitHub Pages. Si una liga no responde, la aplicación avisa y no inventa fechas.
- Los modelos no tienen cuotas actuales automatizadas ni backtest/calibración suficientes para afirmar una ventaja real.

## Cuotas y detección automática de valor

La página contiene una sección **Cuotas automáticas**. Desde GitHub Actions se ejecuta `scripts/build_odds.py`, que obtiene mercados y precios de Betano y DraftKings de Odds-API.io, identifica los partidos del calendario y genera `assets/data/odds.json`. **No es necesario ingresar las cuotas manualmente.**

Para activarlo, agrega en el repositorio **Settings > Secrets and variables > Actions** el secreto `ODDS_API_IO_KEY` con la clave que te entrega **Odds-API.io**, y después ejecuta manualmente **Actions > Publicar EdgeLab en GitHub Pages > Run workflow**. La clave de DunkAPI no sirve para esta integración.

El detector aplica Poisson a 1X2 completo y goles de fútbol cuando hay histórico suficiente. En NBA/WNBA/NHL/NFL compara cotizaciones iguales de ambas casas, mostrando una **señal de precio relativa, no un modelo predictivo**. Las líneas que carezcan de modelo se muestran sin una probabilidad inventada. Los datos son instantáneas y no cotizaciones en vivo.

Consulta los [detalles de seguridad, costes y limitaciones](docs/CUOTAS.md).

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
