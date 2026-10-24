import {analyzeRecord,validateSnapshot,MODEL_VERSION} from './research-engine.mjs';

const root=document.createElement('section');
root.id='researchLab';root.className='panel research-lab';
root.innerHTML='<div class="sectionhead"><div><h3>🔬 Laboratorio · Análisis con contexto</h3><p class="desc">Estadísticas, minutos, lesiones, forma, veto y fuente por selección. No sustituye el detector automático de cuotas.</p></div><span class="pill">Modelo experimental</span></div><p class="odds-footnote">Importa un JSON con estadísticas comprobables y cuotas de la misma línea. Los registros no están incluidos ni se obtienen automáticamente de este chat. Se procesan localmente sin subir datos a GitHub.</p><div class="research-controls"><label for="researchImport" class="btn">Importar análisis JSON <input type="file" id="researchImport" accept=".json,application/json" hidden></label><button type="button" class="btn" id="researchExample">Descargar plantilla</button><button type="button" class="btn" id="researchClear">Limpiar sesión</button></div><p id="researchStatus" class="odds-notice" role="status">Todavía no has importado observaciones. Los mercados sin datos seguirán sin predicción.</p><div id="researchContent"></div><p class="odds-footnote">Los modelos usan estadísticas proporcionadas por el usuario o un proveedor futuro. La marca verified en JSON no constituye comprobación independiente. El EV es una estimación, no una promesa de rentabilidad.</p>';
document.getElementById('autoOdds')?.insertAdjacentElement('afterend',root);
let records=[],selected='',fixtures=[],quotes=null;
const el=id=>document.getElementById(id);
const node=(tag,cls,text)=>{const x=document.createElement(tag);if(cls)x.className=cls;if(text!==undefined)x.textContent=String(text);return x};
const fmt=x=>Number(x).toLocaleString('es-CL',{maximumFractionDigits:2,minimumFractionDigits:2});
const pct=p=>(100*p).toLocaleString('es-CL',{maximumFractionDigits:1,minimumFractionDigits:1})+'%';
const txt=(value)=>value===null||value===undefined?'—':value;
const shorten=s=>typeof s==='string'?s.slice(0,115):'';
const verifyURL=url=>{try{const u=new URL(url);return u.protocol==='https:'?u.href:null}catch{return null}};
const selectFile=async e=>{
 const file=e.target.files?.[0];if(!file)return;
 try{
  if(file.size>1500000)throw Error('Archivo demasiado grande (máximo 1,5 MB).');
  const parsed=validateSnapshot(JSON.parse(await file.text()));
  records=parsed.records;selected='';
  el('researchStatus').textContent='Se importaron '+records.length+' observaciones. Busca un partido del calendario o examina los resultados completos.';
  el('researchStatus').dataset.tone='success';
 }catch(err){el('researchStatus').textContent='Importación rechazada: '+err.message;el('researchStatus').dataset.tone='warning'}
 e.target.value='';render();
};
el('researchImport').addEventListener('change',selectFile);
el('researchClear').addEventListener('click',()=>{records=[];selected='';el('researchStatus').textContent='Sesión limpiada; no se almacenan estadísticas privadas en el servidor.';render()});
el('researchExample').addEventListener('click',()=>{
 const file={schema:1,records:[{
  fixture_id:'REEMPLAZAR_POR_ID_CALENDARIO',sport:'basket',
  player:'Jugador de ejemplo',market:{kind:'points',side:'over',line:24.5},
  last10:[22,27,31,25,20,30,24,26,21,29],sample_size:10,
  baseline_minutes:33,expected_minutes:34,sd:6.3,
  opponent_factor:1.0,blowout_probability:.15,blowout_minutes_cut:.25,
  availability:'active',
  source:{name:'Proveedor estadístico autorizado',url:'https://example.org/estadisticas',captured_at:'2026-10-24T12:00:00Z',verified:false},
  quote:{decimal:1.93,book:'Casa de ejemplo (NO REAL)',
   source:{name:'Precio de ejemplo, reemplazar',url:'https://example.org/cuotas',captured_at:'2026-10-24T12:00:00Z',verified:false}}
 }]};
 const blob=new Blob([JSON.stringify(file,null,2)],{type:'application/json'});
 const url=URL.createObjectURL(blob),a=node('a');a.href=url;a.download='edgelab-plantilla-analisis.json';a.click();URL.revokeObjectURL(url);
});
const hasFixture=fixtureId=>fixtures.find(f=>f.id===fixtureId);
function render(){
 const container=el('researchContent');container.replaceChildren();
 if(!records.length){container.append(node('p','odds-empty','Sin observaciones. Descarga la plantilla o importa datos normalizados del partido.'));return}
 const filter=node('div','research-controls'),label=node('label','', 'Partido: ');
 const select=node('select');select.append(new Option('Todos los registros',''));
 const eventIds=new Set(records.map(r=>r.fixture_id));
 for(const id of eventIds){const f=hasFixture(id);select.add(new Option(f?f.home+' vs '+f.away:id,id))}
 select.value=selected;select.addEventListener('change',()=>{selected=select.value;render()});
 label.append(select);filter.append(label);container.append(filter);
 const entries=records.filter(r=>!selected||r.fixture_id===selected);
 const table=node('table','research-table'),head=node('thead'),hr=node('tr');
 for(const name of ['Evento / jugador','Mercado','Cuota / casa','Prob. modelo','Cuota justa / EV','Estado / evidencia'])hr.append(node('th','',name));
 head.append(hr);table.append(head);
 const body=node('tbody');
 for(const r of entries.slice(0,200)){
  const fixture=hasFixture(r.fixture_id),result=analyzeRecord(r,fixture||null);
  const tr=node('tr'),name=fixture?fixture.home+' vs '+fixture.away:r.fixture_id;
  tr.append(node('td','',name+(r.player?' · '+r.player:'')));
  tr.append(node('td','',r.market.kind+' · '+txt(r.market.side)+' '+txt(r.market.line)));
  tr.append(node('td','',r.quote?.decimal?fmt(r.quote.decimal)+' · '+shorten(r.quote.book):'—'));
  tr.append(node('td','',result.p===null?'—':pct(result.p)));
  tr.append(node('td','',result.metrics?fmt(result.metrics.fair)+' / '+(result.metrics.ev>0?'+':'')+pct(result.metrics.ev):'—'));
  const cell=node('td');
  cell.append(node('strong',result.status==='candidato'?'research-positive':'',result.status));
  for(const line of [...(result.errors||[]),...(result.warnings||[])])cell.append(node('p','research-note',line));
  if(result.veto)cell.append(node('p','research-note','Veto '+(result.veto.predicted?'proyectado':'confirmado')+': '+result.veto.maps.join(' / ')));
  for(const source of [r.source,r.quote?.source]){
   const url=verifyURL(source?.url);
   if(!url)continue;
   const a=node('a','research-link',shorten(source.name)+' · '+shorten(source.captured_at));
   a.href=url;a.target='_blank';a.rel='noopener noreferrer';cell.append(a);
  }
  tr.append(cell);body.append(tr);
 }
 table.append(body);const scroll=node('div','odds-scroll');scroll.append(table);container.append(scroll);
 container.append(node('p','odds-footnote','Modelo '+MODEL_VERSION+' · '+entries.length+' registros · sin calibración retrospectiva certificada.'));
}
async function loadCalendar(){
 try{const res=await fetch(new URL('../data/calendar.json',import.meta.url),{cache:'no-store'});if(!res.ok)throw Error('HTTP '+res.status);
  const data=await res.json();fixtures=Array.isArray(data.fixtures)?data.fixtures:[];render();
 }catch{el('researchStatus').textContent='Sin calendario precargado: el laboratorio requiere partido futuro verificable.';el('researchStatus').dataset.tone='warning'}
}
window.addEventListener('edgelab:fixture-select',e=>{selected=e.detail?.id||'';render();root.scrollIntoView({behavior:'smooth',block:'start'})});
loadCalendar();render();
