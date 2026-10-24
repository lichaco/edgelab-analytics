import {LEAGUES,fetchLeague,futureOnly,localDateTime,dayChile,dateOfFixture} from './fixtures.mjs';
import {estimateLambdas,predictMarkets} from './football-model.mjs';
const el=id=>document.getElementById(id);
const plus=(d,n)=>new Date(d.getTime()+n*86400000);
const pct=p=>(100*p).toLocaleString('es-CL',{maximumFractionDigits:1,minimumFractionDigits:1})+'%';
const fmt=(d,options)=>new Intl.DateTimeFormat('es-CL',Object.assign({timeZone:'America/Santiago'},options)).format(d);
let sport='football',fixtures=[],chosenDate='',sequence=0,snapshot=null;
const directCache=new Map();
function clear(node){node.replaceChildren()}
function elem(tag,cls,text){const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n}
function info(text,tone){el('calendarStatus').textContent=text;el('calendarStatus').dataset.tone=tone||'normal'}
function renderDays(){
 const root=el('calendarDaysStrip');clear(root);const horizon=+el('calendarSpan').value;
 function button(label,day){const b=elem('button','calendar-day'+(day===chosenDate?' selected':''));b.type='button';b.dataset.day=day;b.textContent=label;root.append(b)}
 button('Todos','');
 for(let i=0;i<horizon;i++){const dt=plus(new Date(),i);button(fmt(dt,{weekday:'short',day:'numeric'}),dayChile(dt))}
}
function changeSport(s){
 if(!Object.hasOwn(LEAGUES,s))return;
 sport=s;fixtures=[];chosenDate='';
 el('calendar').dataset.sport=s;
 el('calendarTitle').textContent=({football:'⚽ Fútbol',basket:'🏀 NBA y WNBA',cs2:'🎮 CS2',nhl:'🏒 NHL',nfl:'🏈 NFL'})[s];
 const sel=el('calendarLeague');clear(sel);sel.add(new Option('Todas las competencias',''));
 (LEAGUES[s]||[]).forEach(l=>sel.add(new Option(l.label,l.id)));
 el('calendarQuery').value='';
 clear(el('calendarForecast'));el('calendarForecast').hidden=true;
 load();
}
function filtered(){
 const q=el('calendarQuery').value.trim().toLocaleLowerCase('es'),league=el('calendarLeague').value;
 const maxDate=dayChile(plus(new Date(),+el('calendarSpan').value));
 return fixtures.filter(f=>dateOfFixture(f)<maxDate&&(!chosenDate||dateOfFixture(f)===chosenDate)&&(!league||f.competitionId===league)&&(!q||(f.home+' '+f.away+' '+f.league).toLocaleLowerCase('es').includes(q)));
}
function render(){
 renderDays();const list=filtered(),container=el('calendarList');clear(container);
 el('calendarCount').textContent=list.length+' '+(list.length===1?'partido':'partidos');
 if(!list.length){container.append(elem('p','calendar-blank',sport==='cs2'?'No hay proveedor de calendario CS2 conectado. Se necesita una fuente autorizada para BO3/BO5.':'No hay encuentros futuros disponibles con estos filtros. Revisa el estado de las fuentes, cambia el día o amplía el plazo.'));return}
 const grouped=new Map();
 for(const f of list){const day=dateOfFixture(f);if(!grouped.has(day))grouped.set(day,[]);grouped.get(day).push(f)}
 for(const [date,items] of grouped){
  const group=elem('section','calendar-group');
  group.append(elem('h4','calendar-group-title',fmt(new Date(date+'T12:00:00Z'),{timeZone:'UTC',weekday:'long',day:'numeric',month:'long'})));
  const grid=elem('div','calendar-grid');
  for(const f of items){
   const card=elem('article','calendar-match'),meta=elem('div','calendar-match-meta');
   const timeLabel=f.utc?fmt(new Date(f.utc),{hour:'2-digit',minute:'2-digit',hour12:false})+' CL':'Hora por confirmar';
   meta.append(elem('span','',f.league),elem('time','',timeLabel));
   const names=elem('div','calendar-names');
   names.append(elem('strong','',f.home),elem('small','','vs'),elem('strong','',f.away));
   const bottom=elem('div','calendar-bottom');
   bottom.append(elem('span','',f.source||'Fuente pública'));
   const b=elem('button','btn',f.utc?'Analizar ↗':'Pendiente de horario');b.type='button';
   if(f.utc)b.dataset.index=String(fixtures.indexOf(f));else {b.disabled=true;b.title='La fuente aún no publica una hora de inicio verificable'}
   bottom.append(b);card.append(meta,names,bottom);grid.append(card);
  }
  group.append(grid);container.append(group);
 }
}
async function getSnapshot(force=false){
 if(snapshot&&!force)return snapshot;
 const response=await fetch(new URL('../data/calendar.json',import.meta.url),{cache:'no-store'});
 if(!response.ok)throw Error('snapshot HTTP '+response.status);
 const json=await response.json();
 if(json?.schema!==1||!Array.isArray(json.fixtures)||!json.generated_at)throw Error('snapshot de calendario inválido');
 snapshot=json;return json;
}
function snapshotStatus(data,leagues){
 const age=(Date.now()-Date.parse(data.generated_at))/3600000;
 const ds=leagues.map(l=>data.diagnostics?.[l.id]).filter(Boolean);
 const fail=ds.filter(x=>x.errors?.length&&(!x.matches||x.days_ok===0));
 const t=fmt(new Date(data.generated_at),{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'});
 return {age,hasErrors:fail.length>0,message:'Datos precargados '+t+' CL · '+(age>24?'desactualizados · ':'')+(fail.length?fail.length+' competencia(s) con problemas de fuente':'OpenFootball / ESPN')};
}
async function directLoad(leagues,start,end,mine){
 const outcomes=await Promise.allSettled(leagues.map(async league=>{
  const key=league.id+'|'+start.toISOString().slice(0,10)+'|'+end.toISOString().slice(0,10);
  const saved=directCache.get(key);if(saved&&Date.now()-saved.at<300000)return saved.items;
  const items=await fetchLeague(league,start,end);
  directCache.set(key,{items,at:Date.now()});return items;
 }));
 if(mine!==sequence)return;
 const direct=outcomes.flatMap(x=>x.status==='fulfilled'?x.value:[]);
 const failures=outcomes.filter(x=>x.status==='rejected');
 fixtures=futureOnly([...direct,...fixtures]);
 const daysPartial=outcomes.filter(x=>x.status==='fulfilled'&&x.value.errors?.length).length;
 if(failures.length===leagues.length){
  info(fixtures.length?'Fuentes en vivo sin respuesta. Mostrando últimas fechas guardadas.':'Sin respuesta de las fuentes. Consulta los detalles y vuelve a intentar.', 'warning');
  if(!fixtures.length)console.warn('EdgeLab: errores ESPN', failures.map(x=>String(x.reason)));
 }else if(failures.length||daysPartial){
  info('Consulta parcial: '+failures.length+' competiciones sin conexión. Se conservan datos guardados cuando existen.','warning');
 }else info('Calendario actualizado por fechas individuales · ESPN (consulta directa)','success');
 render();
}
async function load(force=false){
 const mine=++sequence,leagues=LEAGUES[sport]||[];
 if(!leagues.length){fixtures=[];info('CS2: no hay proveedor integrado. No se inventan encuentros.','warning');render();return}
 el('calendarRefresh').disabled=true;info('Cargando calendario…');
 const start=plus(new Date(),-1),end=plus(new Date(),+el('calendarSpan').value+1);
 let data;
 try{
  data=await getSnapshot(force);
  if(mine!==sequence)return;
  fixtures=futureOnly(data.fixtures.filter(f=>leagues.some(l=>l.id===f.competitionId)));
  const status=snapshotStatus(data,leagues);
  info(status.message,status.age>24||status.hasErrors?'warning':'success');
  render();
  if(!force&&status.age<=24&&(!status.hasErrors||fixtures.length)){el('calendarRefresh').disabled=false;return;}
 }catch(err){
  if(mine!==sequence)return;
  fixtures=[];info('Calendario precargado no disponible ('+err.message+'). Probando ESPN por día…','warning');render();
 }
 try{await directLoad(leagues,start,end,mine)}
 finally{if(mine===sequence)el('calendarRefresh').disabled=false}
}
function footballForecast(game){
 const panel=el('calendarForecast');panel.hidden=false;clear(panel);
 const history=snapshot?.history?.[game.competitionId];
 if(!Array.isArray(history)||history.length<55){
  panel.append(elem('p','','No hay suficientes resultados históricos verificados para este partido. La selección de equipos y hora está completa.'));return;
 }
 try{
  const rates=estimateLambdas(history,game.home,game.away,dayChile(new Date()));
  if(!rates){panel.append(elem('p','','No hay suficientes datos comparables de estos equipos. No se asignarán goles esperados ficticios.'));return}
  const predictions=predictMarkets(rates.home,rates.away),scores=[
   ['Local (1)',predictions.oneXTwo.home],['Empate (X)',predictions.oneXTwo.draw],
   ['Visitante (2)',predictions.oneXTwo.away],['Over 2,5',predictions.goals['2.5'].over]];
  panel.append(elem('strong','','Poisson experimental · '+rates.trainGames+' resultados históricos'));
  const grid=elem('div','calendar-prob-grid');
  for(const [label,p] of scores){const cell=elem('div','calendar-prob');cell.append(elem('span','',label),elem('b','',pct(p)),elem('small','','Cuota justa '+(1/p).toFixed(2)));grid.append(cell)}
  panel.append(grid,elem('p','calendar-note','Goles esperados: '+rates.home.toFixed(2)+' / '+rates.away.toFixed(2)+'. Sin cuotas reales no se estima valor. Modelo sin calibración externa.'));
  if(el('f_home'))el('f_home').value=rates.home;
  if(el('f_away'))el('f_away').value=rates.away;
 }catch(err){
  panel.append(elem('p','','No se pudo calcular el modelo con estos nombres/datos: '+err.message));
 }
}
function choose(index){
 const game=fixtures[Number(index)];if(!game?.utc)return;
 if(window.EdgeLabUI?.chooseFixture){
  window.EdgeLabUI.chooseFixture({sport:game.sport,league:game.league,event:game.home+' vs '+game.away,starts:localDateTime(new Date(game.utc))})
 }
 window.dispatchEvent(new CustomEvent('edgelab:fixture-select',{detail:{id:game.id,sport:game.sport}}));
 const box=el('calendarForecast');box.hidden=false;clear(box);
 if(game.sport==='football')footballForecast(game);
 else box.append(elem('p','','Partido seleccionado: '+game.home+' vs '+game.away+'. Falta seleccionar jugador y estadísticas para calcular props.'));
 box.scrollIntoView({block:'nearest',behavior:'smooth'});
}
el('calendarRefresh').addEventListener('click',()=>load(true));
el('calendarSpan').addEventListener('change',()=>{chosenDate='';load()});
el('calendarLeague').addEventListener('change',render);
el('calendarQuery').addEventListener('input',render);
el('calendarDaysStrip').addEventListener('click',e=>{const b=e.target.closest('button[data-day]');if(!b)return;chosenDate=b.dataset.day;render()});
el('calendarList').addEventListener('click',e=>{const b=e.target.closest('button[data-index]');if(b)choose(b.dataset.index)});
window.addEventListener('edgelab:sport-change',e=>{if(e.detail?.sport)changeSport(e.detail.sport)});
changeSport('football');
