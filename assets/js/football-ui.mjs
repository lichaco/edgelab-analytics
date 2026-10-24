import {LEAGUES,normalizeOpenFootball,evaluateMatch,oddsAnalysis,noVigThreeWay,backtest} from './football-model.mjs';
const $=id=>document.getElementById(id);
const fmtP=n=>(100*n).toFixed(1).replace('.',',')+'%';
const fmtD=n=>Number(n).toFixed(2).replace('.',',');
const today=()=>new Intl.DateTimeFormat('sv-SE',{timeZone:'America/Santiago',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
const base='https://raw.githubusercontent.com/openfootball/football.json/master';
const cache=new Map();
let league='premier',all=[],fixtures=[],current=null,asOf='';
function status(message,tone=''){$('autoStatus').textContent=message;$('autoStatus').dataset.tone=tone}
async function fetchSeason(code,season){
 const ctl=new AbortController(),t=setTimeout(()=>ctl.abort(),16000);
 try{
  const r=await fetch(base+'/'+season+'/'+code+'.json',{cache:'no-store',signal:ctl.signal});
  if(!r.ok)throw Error('HTTP '+r.status);
  return normalizeOpenFootball(await r.json(),season);
 }finally{clearTimeout(t)}
}
function fixturesAhead(matches,date){
 const ids=new Set();
 return matches.filter(m=>m.season==='2026-27'&&m.date>date&&m.hg===null).filter(m=>{
  const key=[m.date,m.home,m.away].join('|');if(ids.has(key))return false;ids.add(key);return true;
 }).sort((a,b)=>a.date.localeCompare(b.date)).slice(0,120);
}
function reset(){current=null;$('autoResult').hidden=true;$('autoSummary').textContent='';$('autoFixture').replaceChildren()}
async function load(force=false){
 league=$('autoLeague').value;
 reset();
 if(!LEAGUES[league].code){status('Chile pendiente: no se integrará una fuente de calidad insuficiente. Se mantiene el modo manual.','warn');return}
 $('autoRefresh').disabled=true;status('Descargando resultados públicos de '+LEAGUES[league].label+'…');
 try{
  let data=cache.get(league);
  if(!data||force){
   const responses=await Promise.allSettled(['2025-26','2026-27'].map(s=>fetchSeason(LEAGUES[league].code,s)));
   const ok=responses.filter(r=>r.status==='fulfilled');
   if(!ok.length)throw Error('Fuente externa no disponible; verifica conexión o bloqueo del navegador.');
   data={rows:ok.flatMap(r=>r.value),partial:ok.length<2};cache.set(league,data);
  }
  asOf=today();all=data.rows;
  fixtures=fixturesAhead(all,asOf);
  const played=all.filter(m=>m.hg!==null&&m.ag!==null&&m.date<asOf);
  const last=played.reduce((v,m)=>m.date>v?m.date:v,'');
  const bt=backtest(all,asOf,65);
  $('autoSummary').textContent=played.length+' partidos terminados verificables · '+fixtures.length+
   ' próximos en fuente · último marcador: '+(last||'no informado')+
   ' · Backtest cronológico: '+bt.games+' partidos · Brier '+(bt.brier??'—')+
   ' · Referencia fija '+(bt.baselineBrier??'—')+'.';
  for(const [i,m] of fixtures.entries()){
   const op=document.createElement('option');op.value=String(i);op.textContent=m.date+' · '+m.home+' — '+m.away;$('autoFixture').append(op);
  }
  if(data.partial)status('Datos parciales: uno de los dos archivos de temporada no respondió.','warn');
  else if(!fixtures.length)status('La fuente no incluye futuros partidos disponibles; prueba otra liga.','warn');
  else status('Datos cargados. Se excluyen los partidos de hoy por no poder confirmar su horario. Comprueba fixtures antes de operar.','ok');
  renderMatch();
 }catch(e){status('No se pudieron cargar datos: '+e.message+'. El panel manual continúa disponible.','warn')}
 finally{$('autoRefresh').disabled=false}
}
function statCard(label,p){
 const node=document.createElement('div');node.className='prediction';
 const name=document.createElement('span');name.textContent=label;
 const prob=document.createElement('strong');prob.textContent=fmtP(p);
 const fair=document.createElement('small');fair.textContent='Cuota justa '+fmtD(1/p);
 node.append(name,prob,fair);return node;
}
function renderMatch(){
 $('autoResult').hidden=true;current=null;
 const fixture=fixtures[Number($('autoFixture').value)||0];
 if(!fixture)return;
 current=evaluateMatch(all,fixture,asOf);
 if(!current){status('No hay muestra suficiente para estimar '+fixture.home+' — '+fixture.away+'. Selecciona otro encuentro.','warn');return}
 const p=current.oneXTwo;
 $('autoMatchTitle').textContent=fixture.home+' — '+fixture.away;
 $('autoModelInfo').textContent=fixture.date+' · λ local '+fmtD(current.lambdas.home)+
 ' · λ visitante '+fmtD(current.lambdas.away)+' · '+current.lambdas.trainGames+
 ' partidos previos ('+current.lambdas.homeSamples+' local, '+current.lambdas.awaySamples+
 ' visitante). Modelo Poisson de goles independientes, aún no calibrado.';
 $('autoProbCards').replaceChildren(
  statCard('1 · Local',p.home),statCard('X · Empate',p.draw),
  statCard('2 · Visitante',p.away),statCard('Over 2,5 goles',current.goals['2.5'].over)
 );
 $('autoResult').hidden=false;renderOdds();
}
function addCell(tr,value,cls=''){const td=document.createElement('td');td.textContent=value;td.className=cls;tr.append(td);return td}
function renderOdds(){
 if(!current)return;
 const p=current.oneXTwo;
 const markets=[
  {name:'Local',key:'home',p:p.home,input:'autoOddsHome'},
  {name:'Empate',key:'draw',p:p.draw,input:'autoOddsDraw'},
  {name:'Visitante',key:'away',p:p.away,input:'autoOddsAway'},
  {name:'Over 2,5 goles',key:'over25',p:current.goals['2.5'].over,input:'autoOddsOver'}
 ];
 const tbody=$('autoCompare');tbody.replaceChildren();
 for(const m of markets){
  const o=oddsAnalysis(m.p,$(m.input).value);
  const tr=document.createElement('tr');
  addCell(tr,m.name);addCell(tr,fmtP(m.p));addCell(tr,fmtD(1/m.p));
  addCell(tr,o?fmtP(o.implicit):'—');
  addCell(tr,o?(o.ev>=0?'+':'')+fmtP(o.ev):'—',o?(o.ev>=0?'value':'neg'):'');
  const cell=addCell(tr,'');
  if(o){
   const btn=document.createElement('button');btn.className='btn';btn.type='button';btn.textContent='Guardar';
   btn.onclick=()=>{
    window.dispatchEvent(new CustomEvent('edgelab:add-selection',{detail:{
     sport:'football',league:LEAGUES[league].label,event:current.fixture.home+' vs '+current.fixture.away,
     starts:current.fixture.date,market:m.name,p:m.p,odds:o.decimal,
     source:'OpenFootball; Poisson experimental, sin calibrar'
    }}));
    status('Selección enviada al historial local (valor estimado, no resultado garantizado).','ok');
   };cell.append(btn);
  }
  tbody.append(tr);
 }
 const novig=noVigThreeWay(['autoOddsHome','autoOddsDraw','autoOddsAway'].map(id=>$(id).value));
 $('autoVig').textContent=novig?'Probabilidad 1X2 sin margen (una misma casa): 1 '+fmtP(novig[0])+
  ' / X '+fmtP(novig[1])+' / 2 '+fmtP(novig[2])+'.':
  'Introduce las 3 cuotas 1X2 de la misma casa para comparar sin margen.';
}
$('autoLeague').addEventListener('change',()=>load());
$('autoRefresh').addEventListener('click',()=>load(true));
$('autoFixture').addEventListener('change',renderMatch);
for(const id of ['autoOddsHome','autoOddsDraw','autoOddsAway','autoOddsOver'])$(id).addEventListener('input',renderOdds);
load();
