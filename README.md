# EdgeLab Analytics

Panel personal de análisis deportivo, construido inicialmente con **HTML, CSS y JavaScript**, sin framework ni dependencias de ejecución.

> **Estado:** prototipo funcional de escenarios matemáticos manuales. No contiene un modelo entrenado ni conexión con proveedores de datos/odds. No se deben interpretar las probabilidades como pronósticos validados.

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
3. Elige deporte, introduce **estadísticas verificadas** y **cuota decimal**, y registra un evento futuro.
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
- En su estado actual las cuotas/proyecciones son manuales; no existe ingestión automática.

## Documentación

- [Arquitectura y decisiones](docs/ARQUITECTURA.md)
- [Plan de desarrollo](docs/ROADMAP.md)
- [Fuentes y APIs a validar](docs/FUENTES.md)
- [Cómo contribuir](CONTRIBUTING.md)

## Cálculos

- Probabilidad implícita: `1 / cuota_decimal`.
- Valor esperado por unidad: `p_modelo * cuota_decimal - 1`.
- **No hay calibración histórica** todavía. Un EV positivo bajo supuestos arbitrarios no demuestra una ventaja real.
