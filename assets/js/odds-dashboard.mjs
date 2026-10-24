import {estimateLambdas,predictMarkets} from './football-model.mjs';
import {reportForEvent} from './value-engine.mjs';
import {attachDunkapiModels,candidateIsExploratory,explanatoryLabel} from './nba-model.mjs';

const fmt=n=>Number(n).toLocaleString('es-CL',{maximumFractionDigits:2,minimumFractionDigits:2});
const pct=n=>(n*100).toLocaleString('es-CL',{minimumFractionDigits:1,maximumFractionDigits:1})+'%';
const markets={result:'Ganador',goals:'Goles totales',totals:'Total del partido',corners:'Córners',cards:'Tarjetas',spread:'Hándicap',prop:'Player prop'};
const sides={home:'Local',away:'Visita',draw:'Empate',over:'Over',under:'Under'};
const $=id=>document.getElementById(id);
const make=(tag,value,cls)=>{const e=document.createElement(tag);if(value!==null)e.textContent=String(value);if(cls)e.className=cls;return e};
const panel=make('section',null,'panel odds-panel');
panel.id='autoOdds';
panel.innerHTML='<div class="sectionhead"><div><h3>📈 Cuotas automáticas y detector de valor</h3><p class="desc">ESPN Core + The Odds API (si está configurada) · cuotas prepartido de referencia</p></div><span class="pill">Actualización programada</span></div><div class="odds-filters"><label>Casa <select id="oddsBook"><option value="">Todas las casas disponibles</option></select></label><label>Mercado <select id="oddsMarket"><option value="">Todos</option><option value="result">Ganador</option><option value="goals">Goles</option><option value="totals">Totales</option><option value="prop">Props</option><option value="spread">Hándicap</option><option value="corners">Córners</option><option value="cards">Tarjetas</option></select></label></div><div id="oddsNotice" role="status" class="odds-notice">Comprobando cuotas…</div><div class="odds-stats"><span id="oddsEventCount">0 partidos con cuotas</span><span id="oddsSignalCount">0 señales</span></div><div id="oddsSignals"></div><details class="odds-all"><summary>Ver todas las cuotas disponibles por partido</summary><div id="oddsBoards"></div></details><p class="odds-footnote">EV modelo: probabilidad Poisson × cuota − 1. Comparación entre casas: precio frente a probabilidad sin margen de la otra casa, no equivale a pronóstico validado. Cuotas de referencia desde ESPN Core y The Odds API cuando esté activada. Las props NBA se contrastan con proyecciones DunkAPI cuando hay mínimo cinco juegos recientes, cuota idéntica y reporte de riesgos; probabilidades experimentales sin calibración. No son precios ejecutables.</p>';
document.getElementById('calendar')?.insertAdjacentElement('afterend',panel);
let sport='football',odds=null,calendar=null,nbaForecasts=null,focusFixture='',loadedAt=0;
const active=()=>Number.isFinite(loadedAt)&&Date.now()-loadedAt<8*3600*1000;
const dateChile=v=>v?new Intl.DateTimeFormat('es-CL',{timeZone:'America/Santiago',day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(v)):'s/d';
const note=(msg,tone='normal')=>{const node=$('oddsNotice');node.textContent=msg;node.dataset.tone=tone};
function labelRow(row){
 const parts=[markets[row.kind]||row.kind];
 if(row.label)parts.push(row.label);
 if(row.line!==null&&row.line!==undefined)parts.push(String(row.line));
 parts.push(sides[row.side]||row.side);
 return parts.join(' · ');
}
function eventRows(){
 if(!odds||!calendar)return [];
 const lookup=new Map((calendar.fixtures||[]).map(f=>[f.id,f]));
 const result=[];
 for(const ev of odds.events||[]){
  if(ev.sport!==sport||!ev.utc||Date.parse(ev.utc)<=Date.now())continue;
  const fixture=lookup.get(ev.fixture_id);
  if(!fixture)continue;
  const history=calendar.history?.[ev.competition_id]||[];
  const report=reportForEvent(ev,fixture,history,{estimateLambdas,predictMarkets});
  result.push({...ev,fixture,rows:attachDunkapiModels(ev,report.rows,nbaForecasts),rates:report.rates});
 }
 return result;
}
function selectedRows(ev){
 const book=$('oddsBook').value,market=$('oddsMarket').value;
 return ev.rows.filter(r=>(!book||r.book===book)&&(!market||r.kind===market));
}
function opportunity(r){
 const age=r.updated_at?Date.now()-Date.parse(r.updated_at):null;
 if(age!==null&&(!Number.isFinite(age)||age<0||age>8*3600*1000))return false;
 if(!active()||!r.analysis||r.analysis.p===null)return false;
 if(r.analysis.type==='dunkapi_exploratorio')return candidateIsExploratory(r);
 return r.analysis.ev>=(r.analysis.type==='modelo'?.025:.04);
}
function appendHead(table,labels){
 const h=make('thead');const row=make('tr');
 for(const label of labels)row.append(make('th',label));
 h.append(row);table.append(h);
}
function render(){
 if(!odds||!calendar)return;
 const all=eventRows();
 const chosen=focusFixture?all.filter(e=>e.fixture_id===focusFixture):all;
 const signals=[];
 for(const game of chosen)for(const r of selectedRows(game))if(opportunity(r))signals.push({...r,event:game});
 signals.sort((a,b)=>b.analysis.ev-a.analysis.ev);
 $('oddsEventCount').textContent=chosen.length+' partidos con cuotas';
 $('oddsSignalCount').textContent=signals.length+' señales detectadas';
 const diag=odds.diagnostics||{};
 const stamp='Instantánea '+dateChile(odds.generated_at)+' CL';
 if(diag.status==='not_configured')note('No hay datos públicos de cuotas todavía; no hace falta contratar ni configurar una API.','warning');
 else if(!active())note(stamp+'. Datos superiores a 8 horas: señales desactivadas hasta próxima actualización.','warning');
 else if(!all.length)note(stamp+'. ESPN no publica cuotas verificables para los próximos partidos de este deporte. No se inventarán precios.','warning');
 else note(stamp+' · '+chosen.length+' partidos · '+(odds.provider||'fuente pública')+'. Verifica siempre la cotización vigente.',diag.status==='ok'?'success':'warning');
 const root=$('oddsSignals');root.replaceChildren();
 if(focusFixture){
  const button=make('button','Mostrar todos los partidos','btn');button.type='button';
  button.addEventListener('click',()=>{focusFixture='';render()});root.append(button);
 }
 if(nbaForecasts){
  const d=nbaForecasts.diagnostics||{};
  root.append(make('p','odds-meta','DunkAPI NBA: '+(nbaForecasts.status||'sin estado')+' · proyecciones derivadas: '+(nbaForecasts.forecasts?.length||0)+' · créditos restantes: '+(d.remaining_credits??'s/d')));
 }
 if(diag.the_odds_api){
  const api=diag.the_odds_api;
  root.append(make('p', 'odds-meta', 'The Odds API: '+(api.status||'sin estado')+' · props añadidas: '+(api.props_added||0)+' · créditos restantes: '+(api.remaining_credits??'s/d')));
 }
 if(diag.errors?.length)root.append(make('p','Incidencias: '+diag.errors.slice(0,2).join(' · '),'odds-error'));
 if(!signals.length)root.append(make('p','No hay señales positivas calculables con las cuotas actuales. Consulta todas las líneas más abajo.','odds-empty'));
 else{
  root.append(make('h4','Señales y candidatos exploratorios · ordenar por EV teórico; NO son predicciones validadas'));
  const scroller=make('div',null,'odds-scroll');const table=make('table');
  appendHead(table,['Partido','Casa','Mercado','Cuota','Prob. referencia','EV relativo','Base','Fuente','Contexto']);
  const body=make('tbody');
  for(const r of signals.slice(0,50)){
   const tr=make('tr');
   for(const value of [r.event.home+' vs '+r.event.away,r.book,labelRow(r),fmt(r.price),pct(r.analysis.p),'+'+pct(r.analysis.ev),r.analysis.type,r.analysis.type==='dunkapi_exploratorio'?'DunkAPI + '+(r.source||'Cuotas'):(r.source||'s/d'),explanatoryLabel(r)])tr.append(make('td',value));
   tr.children[5].className='value';body.append(tr);
  }
  table.append(body);scroller.append(table);root.append(scroller);
 }
 const boards=$('oddsBoards');boards.replaceChildren();
 const listing=chosen.filter(e=>selectedRows(e).length).slice(0,70);
 if(!listing.length){boards.append(make('p','Sin cuotas publicadas para estos filtros.','odds-empty'));return;}
 for(const game of listing){
  const details=make('details');details.className='odds-match';details.open=!!focusFixture||listing.length===1;
  details.append(make('summary',game.home+' vs '+game.away+' · '+game.competition_id+' · '+dateChile(game.utc)+' CL'));
  if(game.rates)details.append(make('p','Goles esperados Poisson: '+fmt(game.rates.home)+' / '+fmt(game.rates.away)+' · histórico: '+game.rates.trainGames+' partidos.','odds-meta'));
  const box=make('div',null,'odds-scroll'),table=make('table');
  appendHead(table,['Casa','Mercado / selección','Cuota','Prob. referencia','Cuota justa','EV relativo','Base','Fuente / hora','Contexto / riesgo']);
  const body=make('tbody');
  for(const r of selectedRows(game).slice(0,240)){
   const tr=make('tr'),a=r.analysis,p=a?.p;
   for(const val of [r.book,labelRow(r),fmt(r.price),p?pct(p):'—',p?fmt(a.fair):'—',p?(a.ev>=0?'+':'')+pct(a.ev):'—',p?a.type:'Sin modelo',(r.source||'Sin fuente')+' · '+(r.updated_at?dateChile(r.updated_at)+' CL':'sin hora'),explanatoryLabel(r)])tr.append(make('td',val));
   if(p)tr.children[5].className=a.ev>=0?'value':'neg';
   body.append(tr);
  }
  table.append(body);box.append(table);details.append(box);boards.append(details);
 }
}
async function load(){
 const [a,b,d]=await Promise.allSettled([
  fetch(new URL('../data/odds.json',import.meta.url),{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('HTTP '+r.status);return r.json()}),
  fetch(new URL('../data/calendar.json',import.meta.url),{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('HTTP '+r.status);return r.json()}),
  fetch(new URL('../data/nba_predictions.json',import.meta.url),{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('HTTP '+r.status);return r.json()})
 ]);
 if(a.status!=='fulfilled'||b.status!=='fulfilled'){note('No se han publicado datos de cuotas o calendario; revisa el despliegue de GitHub Actions.','warning');return;}
 if(!Array.isArray(a.value?.events)||!Array.isArray(b.value?.fixtures)){note('La respuesta de cuotas no tiene el formato esperado.','warning');return;}
 odds=a.value;calendar=b.value;nbaForecasts=d.status==='fulfilled'&&d.value?.schema===1?d.value:null;loadedAt=Date.parse(odds.generated_at);
 const select=$('oddsBook'),previous=select.value,books=[...new Set(odds.events.flatMap(ev=>Object.keys(ev.books||{})))].sort();
 select.replaceChildren(new Option('Todas las casas disponibles',''));
 for(const name of books)select.add(new Option(name,name));
 if(books.includes(previous))select.value=previous;
 window.dispatchEvent(new CustomEvent('edgelab:odds-loaded',{detail:{events:odds.events,generated_at:odds.generated_at}}));
 render();
}
for(const id of ['oddsBook','oddsMarket'])$(id).addEventListener('change',render);
window.addEventListener('edgelab:sport-change',e=>{if(e.detail?.sport){sport=e.detail.sport;focusFixture='';render();}});
window.addEventListener('edgelab:fixture-select',e=>{focusFixture=e.detail?.id||'';if(e.detail?.sport)sport=e.detail.sport;render();panel.scrollIntoView({behavior:'smooth',block:'start'});});
$('calendarRefresh')?.addEventListener('click',load);
load();
