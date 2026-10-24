# Hoja de ruta de EdgeLab

## 0. Repositorio y pruebas
- [x] Panel HTML, CSS y JS separado en archivos
- [x] README, .gitignore y prueba de integridad automatizada
- [ ] Crear repo en GitHub y subir `main`
- [ ] Opcional: vista web hospedada y protegida

## 1. Fútbol (verde)
- [ ] Datos históricos para cinco grandes ligas y Chile, con validación de licencias
- [ ] 1X2, over goles, córners, tarjetas: Poisson bivariante/negative-binomial donde proceda
- [ ] Variables: localía, forma, xG, cuotas históricas, árbitros, lesiones
- [ ] Backtesting temporal y calibración por liga y mercado

## 2. Básquet (naranja)
- [ ] NBA, WNBA, Euroliga: estadísticas de jugadores y minutos proyectados
- [ ] Props: puntos/rebotes/asistencias/triples y distribución coherente con el tipo de conteo
- [ ] Validar mercado y cobertura de lesiones/lineups

## 3. CS2 (amarillo)
- [ ] Filtrar Tier B/A/S y BO3/BO5
- [ ] Ranking, forma, mapa, veto, H2H y mapas favoritos
- [ ] Ganador serie, resultados exactos e hándicaps

## 4. NHL y NFL
- [ ] NHL: tiros a puerta, goles, asistencias; proyecciones de tiempo sobre hielo
- [ ] NFL: yardas, recepciones, TD; snaps, objetivos, clima y ausencias

## 5. Plataforma de valor
- [ ] API backend privada + caché y control de créditos
- [ ] Histórico de cuotas con timestamps y bookmakers
- [ ] Calibración, sesgos y seguimiento de valor esperado vs resultado
- [ ] Dashboard para comparar cambios en líneas y distinguir valor estimado vs apuesta real
