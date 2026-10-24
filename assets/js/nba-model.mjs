// Proyecciones NBA: mezcla SOLO la línea, cuota, jugador y encuentro exactos.
// El JSON de DunkAPI contiene resultados DERIVADOS, no logs brutos del proveedor.
const finite=n=>typeof n==='number'&&Number.isFinite(n);
export function attachDunkapiModels(event,rows,snapshot,now=new Date(),provider='dunkapi'){
 if(event?.sport!=='basket'||event?.competition_id!=='nba'||snapshot?.schema!==1||
  !Array.isArray(snapshot?.forecasts))return rows;
 const at=Date.parse(snapshot.generated_at);
 if(!Number.isFinite(at)||at>now.getTime()+300000||now.getTime()-at>8*3600000)return rows;
 const forecasts=snapshot.forecasts.filter(x=>x.fixture_id===event.fixture_id&&x.calibrated===false);
 return rows.map(row=>{
  if(row.kind!=='prop'||row.side!=='over'||!(row.price>1.80)||row.analysis?.type==='nba_oficial_exploratorio')return row;
  const forecast=forecasts.find(x=>
   x.market_label===row.label&&x.market_line===row.line&&x.book===row.book&&
   finite(x.quote)&&Math.abs(x.quote-row.price)<.001);
  if(!forecast||!(forecast.p>0&&forecast.p<1)||!Number.isInteger(forecast.sample_size)||
    forecast.sample_size<5||!finite(forecast.minutes_reference)||forecast.minutes_reference<12||
    !finite(forecast.projected_mean))return row;
  const quoteUpdated=Date.parse(forecast.quote_updated_at);
  const checked=Date.parse(forecast.stats_checked_at);
  if(!Number.isFinite(quoteUpdated)||!Number.isFinite(checked)||
    now.getTime()-quoteUpdated>8*3600000||quoteUpdated>now.getTime()+300000||
    now.getTime()-checked>48*3600000||checked>now.getTime()+300000)return row;
  const analysis={
   type:provider==='nba_oficial'?'nba_oficial_exploratorio':'dunkapi_exploratorio',p:forecast.p,ev:forecast.p*row.price-1,
   fair:1/forecast.p,edge:forecast.p-1/row.price,
  };
  return {...row,analysis,model_context:{
   mean:forecast.projected_mean,minutes:forecast.minutes_reference,
   sample:forecast.sample_size,injuries_fresh:forecast.injuries_fresh,
   injury_status:forecast.injury_status,model:forecast.model,
   warnings:Array.isArray(forecast.warnings)?forecast.warnings:[],
   last_game:forecast.last_game,source:provider==='nba_oficial'?'NBA oficial (CDN)':'DunkAPI',
  }};
 });
}
export function explanatoryLabel(row){
 const c=row?.model_context;
 if(!c)return '';
 const parts=['Fuente stats: '+(c.source||'s/d'),'Proy. '+c.mean,'minutos ref. '+c.minutes,c.sample+' partidos',
  c.injuries_fresh?'Lesiones verificadas en snapshot':'Reporte lesiones no actualizado'];
 if(c.injury_status)parts.push('Estado: '+c.injury_status);
 if(c.warnings?.length)parts.push(c.warnings.join(' · '));
 parts.push('Sin calibración; confirmar minutos y blowout');
 return parts.join(' · ');
}
export function candidateIsExploratory(row){
 const c=row?.model_context;
 return row?.analysis?.type==='dunkapi_exploratorio'&&row.side==='over'&&
 row.price>1.80&&row.analysis.ev>=.08&&c?.sample>=8&&c?.injuries_fresh===true&&
 !/questionable|day-to-day|out|doubtful/i.test(c.injury_status||'');
}

// NBA official CDN takes precedence when there is enough official history.
export function attachOfficialNbaModels(event,rows,snapshot,now=new Date()){
 return attachDunkapiModels(event,rows,snapshot,now,'nba_oficial');
}
