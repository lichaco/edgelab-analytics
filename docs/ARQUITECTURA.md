# Arquitectura — evolución por etapas

## Hoy (v0.1)

`index.html` → `assets/css/styles.css` + `assets/js/app.js` → `localStorage`.

UI manual, sin llamadas de red ni secretos. Modelos de ejemplo (Poisson/normal/mapas) para probar el flujo de análisis.

## Mañana (v0.2+)

```text
Fuentes estadísticas públicas ──┐
                               ├→ ETL Python → Datos normalizados → Features → Modelo validado
Proveedor de cuotas/odds ──────┘                                        │
                                                                          ↓
Navegador HTML ← API segura con autenticación ← Predicciones + Odds + EV + trazabilidad
```

Elementos del backend futuro: ingesta programada, SQLite para prototipo/PostgreSQL después, caché para controlar costos, ETL y APIs `/events`, `/props`, `/predictions`, `/odds` y `/value`. Las claves solo en el servidor. Los datos deben tener `event_id`, `player_id`, `market_id`, `source`, `captured_at_utc`, `model_version`.

**Privacidad:** GitHub sirve para versionar **código**, no guardar análisis privados ni cuotas con licencias restrictivas. Un sitio público (incluido GitHub Pages) no protege secretos ni historial.

**Predictibilidad:** evaluar por rolling origin y temporadas futuras; métricas Brier score/log loss, calibración, ROI con intervalos de confianza, resultado frente a closing line. Evitar contaminación temporal (look-ahead bias).
