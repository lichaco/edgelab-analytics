import {LEAGUES,fetchLeague,futureOnly,historyOnly,localDateTime,dayChile} from './fixtures.mjs';
import {estimateLambdas,predictMarkets} from './football-model.mjs';
const el=id=>document.getElementById(id);
const plus=(d,n)=>new Date(d.getTime()+n*86400000);
const pct=p=>(100*p).toLocaleString('es-CL',{maximumFractionDigits:1,minimumFractionDigits:1})+'%';
const fmt=(d,options)=>new Intl.DateTimeFormat('es-CL',Object.assign({timeZone:'America/Santiago'},options)).format(d);
let sport='football', fixtures=[],chosenDate='',sequence=0;
const cache=new Map();
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
 load(true);
}
function filtered(){
 const q=el('calendarQuery').value.trim().toLocaleLowerCase('es'),league=el('calendarLeague').value;
 return fixtures.filter(f=>(!chosenDate||dayChile(new Date(f.utc))===chosenDate)&&(!league||f.competitionId===league)&&(!q||(f.home+' '+f.away+' '+f.league).toLocaleLowerCase('es').includes(q)));
}
function render(){
 renderDays();const list=filtered(),container=el('calendarList');clear(container);
 el('calendarCount').textContent=list.length+' '+(list.length===1?'partido':'partidos');
 if(!list.length){container.append(elem('p','calendar-blank',sport==='cs2'?'No hay proveedor de calendario CS2 conectado. Se necesita una fuente autorizada para los BO3/BO5.':'No hay encuentros futuros publicados para estos filtros. Cambia el día o amplía el rango.'));return}
 const grouped=new Map();
 for(const f of list){const day=dayChile(new Date(f.utc));if(!grouped.has(day))grouped.set(day,[]);grouped.get(day).push(f)}
 for(const [date,items] of grouped){
  const group=elem('section','calendar-group');
  group.append(elem('h4','calendar-group-title',fmt(new Date(date+'T12:00:00Z'),{timeZone:'UTC',weekday:'long',day:'numeric',month:'long'})));
  const grid=elem('div','calendar-grid');
  for(const f of items){
   const card=elem('article','calendar-match'),meta=elem('div','calendar-match-meta');
   meta.append(elem('span','',f.league),elem('time','',fmt(new Date(f.utc),{hour:'2-digit',minute:'2-digit',hour12:false})+' CL'));
   const names=elem('div','calendar-names');
   names.append(elem('strong','',f.home),elem('small','',''),elem('strong','',f.away));
   names.children[1].textContent='vs';
   const bottom=elem('div','calendar-bottom');
   bottom.append(elem('span','','Por comenzar'));
   const b=elem('button','btn','Analizar ↗');b.type='button';b.dataset.index=String(fixtures.indexOf(f));
   bottom.append(b);card.append(meta,names,bottom);grid.append(card);
  }
  group.append(grid);container.append(group);
 }
}
async function load(force=false){
 const mine=++sequence,leagues=LEAGUES[sport]||[];
 if(!leagues.length){fixtures=[];info('CS2: se requiere un proveedor compatible y autorización de uso para análisis de apuestas.','warning');render();return}
 info('Cargando partidos desde la fuente…');el('calendarRefresh').disabled=true;
 const start=plus(new Date(),-1),end=plus(new Date(),+el('calendarSpan').value+1);
 const outcomes=await Promise.allSettled(leagues.map(async league=>{
  const key=league.id+'|'+dayChile(start)+'|'+dayChile(end);
  const saved=cache.get(key);
  if(!force&&saved&&Date.now()-saved.at<600000)return saved.items;
  const items=await fetchLeague(league,start,end);
  cache.set(key,{items,at:Date.now()});return items
 }));
 if(mine!==sequence)return;
 fixtures=futureOnly(outcomes.flatMap(x=>x.status==='fulfilled'?x.value:[]));
 const failed=outcomes.filter(x=>x.status==='rejected').length;
 info(failed?'Calendario parcial: '+failed+' competencia(s) sin respuesta. Reintenta más tarde.':'Actualizado · fuente ESPN no oficial · horarios de Chile',failed?'warning':'success');
 el('calendarRefresh').disabled=false;render();
}
async function footballForecast(game){
 const panel=el('calendarForecast');panel.hidden=false;clear(panel);
 panel.append(elem('p','','Calculando probabilidades con resultados anteriores…'));
 const league=LEAGUES.football.find(x=>x.id===game.competitionId);
 const now=new Date();
 try{
  const recent=await fetchLeague(league,plus(now,-180),now);
  let matches=historyOnly(recent,now);
  if(matches.length<65){
   const older=await fetchLeague(league,plus(now,-490),plus(now,-181));
   matches=matches.concat(historyOnly(older,now));
  }
  const unique=[...new Map(matches.map(m=>[m.date+'|'+m.home+'|'+m.away,m])).values()];
  const rates=estimateLambdas(unique,game.home,game.away,dayChile(now));
  clear(panel);
  if(!rates){panel.append(elem('p','','Histórico insuficiente para estimar este encuentro. Los equipos y la fecha sí quedaron seleccionados.'));return}
  const predictions=predictMarkets(rates.home,rates.away),scores=[
   ['Local (1)',predictions.oneXTwo.home],['Empate (X)',predictions.oneXTwo.draw],
   ['Visitante (2)',predictions.oneXTwo.away],['Over 2,5',predictions.goals['2.5'].over]];
  panel.append(elem('strong','','Probabilidades Poisson experimentales · '+rates.trainGames+' partidos de referencia'));
  const grid=elem('div','calendar-prob-grid');
  for(const [label,p] of scores){const cell=elem('div','calendar-prob');cell.append(elem('span','',label),elem('b','',pct(p)),elem('small','','Cuota justa '+(1/p).toFixed(2)));grid.append(cell)}
  panel.append(grid,elem('p','calendar-note','Goles esperados: '+rates.home.toFixed(2)+' / '+rates.away.toFixed(2)+'. Sin cuotas reales no se estima valor. Modelo sin calibración externa.'));
  if(el('f_home'))el('f_home').value=rates.home;
  if(el('f_away'))el('f_away').value=rates.away;
 }catch(err){
  clear(panel);panel.append(elem('p','','No se pudieron obtener resultados para proyectar goles: '+err.message+'. El encuentro ya está seleccionado.'));
 }
}
async function choose(index){
 const game=fixtures[Number(index)];if(!game)return;
 if(window.EdgeLabUI?.chooseFixture){
  window.EdgeLabUI.chooseFixture({sport:game.sport,league:game.league,event:game.home+' vs '+game.away,starts:localDateTime(new Date(game.utc))})
 }
 const box=el('calendarForecast');box.hidden=false;clear(box);
 if(game.sport==='football')await footballForecast(game);
 else box.append(elem('p','','Partido seleccionado: '+game.home+' vs '+game.away+'. Falta seleccionar jugador y estadísticas para calcular sus props.'));
 box.scrollIntoView({block:'nearest',behavior:'smooth'});
}
el('calendarRefresh').addEventListener('click',()=>load(true));
el('calendarSpan').addEventListener('change',()=>{chosenDate='';load(true)});
el('calendarLeague').addEventListener('change',render);
el('calendarQuery').addEventListener('input',render);
el('calendarDaysStrip').addEventListener('click',e=>{const b=e.target.closest('button[data-day]');if(!b)return;chosenDate=b.dataset.day;render()});
el('calendarList').addEventListener('click',e=>{const b=e.target.closest('button[data-index]');if(b)choose(b.dataset.index)});
window.addEventListener('edgelab:sport-change',e=>{if(e.detail?.sport)changeSport(e.detail.sport)});
changeSport('football');
