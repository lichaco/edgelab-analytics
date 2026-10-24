# Flujo de trabajo para desarrollar EdgeLab

1. Crea o actualiza tu repositorio con el contenido de esta carpeta.
2. Cada mejora, en una rama: `feature/football-model`, `feature/nba-data`, `fix/cs2-handicap`, etc.
3. Haz cambios pequeños. Ejecuta `npm test` y `npm run check` (Node.js 20+).
4. Guarda un commit claro: `feat: añadir filtro por liga`, `fix: corregir probabilidad de over`.
5. Abre Pull Request a `main`. Anota: objetivo, capturas, datos fuente y cómo validar el cálculo.
6. Tras aprobar, fusiona a `main` y comprueba el panel.

## Reglas para fuentes nuevas

- Documenta proveedor, licencia, mercado, cobertura, fecha/hora UTC, actualización y límites.
- Valida IDs de partidos/jugadores y evita mezclar estadísticas de temporadas o calendarios distintos.
- No comprometas claves o cookies; mételas exclusivamente en un backend con variables de entorno.
- Mantén separados: datos originales, features, predicciones, líneas de bookmakers y resultados finales.
- Registra versiones del modelo para backtesting cronológico, calibración y comparación de cuotas.
