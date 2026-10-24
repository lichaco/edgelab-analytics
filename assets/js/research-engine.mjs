// EdgeLab Research v1: modelo de referencia con entradas fechadas y trazables.
// Sin estadísticas verificables no produce probabilidades independientes.
export const MODEL_VERSION='research-1.0';
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const validDate=s=>typeof s==='string'&&Number.isFinite(Date.parse(s));
const logistic=x=>1/(1+Math.exp(-x));
const logit=x=>Math.log(clamp(x,.0001,.9999)/(1-clamp(x,.0001,.9999)));
const integerLine=x=>finite(x)&&x>=0&&Math.abs(x-Math.floor(x)-.5)<1e-7;

export function poissonOver(mean,line){
 if(!(finite(mean)&&mean>=0&&integerLine(line)))return null;
 let term=Math.exp(-mean),cdf=term;
 for(let i=1;i<=Math.floor(line);i++){term*=mean/i;cdf+=term}
 return clamp(1-cdf,0,1);
}

// Varianza = media + media^2 / dispersion. Dispersión pequeña -> mayor cola.
// Recurrencia de la binomial negativa, sin librerías externas.
export function negativeBinomialOver(mean,line,dispersion){
 if(!(finite(mean)&&mean>0&&finite(dispersion)&&dispersion>0&&integerLine(line)))return null;
 const q=mean/(dispersion+mean);
 let term=Math.pow(1-q,dispersion),cdf=term;
 for(let i=1;i<=Math.floor(line);i++){
  term*=((i-1+dispersion)/i)*q;
  cdf+=term;
 }
 return clamp(1-cdf,0,1);
}
function erf(x){
 const sign=x<0?-1:1;const a=Math.abs(x),t=1/(1+.3275911*a);
 return sign*(1-(((((1.061405429*t-1.453152027)*t)+1.421413741)*t-.284496736)*t+.254829592)*t*Math.exp(-a*a));
}
export function normalOver(mean,sd,line){
 if(!(finite(mean)&&finite(sd)&&sd>0&&finite(line)&&line>=0))return null;
 return clamp((1-erf((line+.5-mean)/(sd*Math.SQRT2)))/2,0,1);
}
export function oddsMetrics(p,quote){
 if(!(finite(p)&&p>0&&p<1&&finite(quote)&&quote>1))return null;
 return {probability:p,implied:1/quote,fair:1/p,edge:p-1/quote,ev:p*quote-1};
}
function validEvidence(r){
 return !!(r&&typeof r.name==='string'&&r.name.trim()&&
  /^https:\/\/[^ ]+$/.test(r.url||'')&&validDate(r.captured_at));
}
function countValid(a){
 return Array.isArray(a)&&a.length>=5&&a.every(x=>finite(x)&&x>=0);
}
function recentMean(a){
 if(!countValid(a))return null;
 // 60% últimos cinco, 40% resto si hay al menos diez.
 const v=a.slice(0,10),first=v.slice(0,5);
 const avg=x=>x.reduce((s,y)=>s+y,0)/x.length;
 return v.length>=10?.6*avg(first)+.4*avg(v.slice(5)):avg(v);
}
function fromCountHistory(record){
 if(countValid(record.last10))return {mean:recentMean(record.last10),size:Math.min(10,record.last10.length)};
 if(finite(record.mean)&&record.mean>=0&&Number.isInteger(record.sample_size)&&record.sample_size>=5)
  return {mean:record.mean,size:record.sample_size};
 return null;
}
function mixture(p0,p1,blowout){
 return (1-blowout)*p0+blowout*p1;
}
function probabilityForPlayer(record){
 const sample=fromCountHistory(record);
 if(!sample)return {p:null,warning:'Faltan al menos 5 partidos o media y tamaño de muestra verificables.'};
 if(record.availability==='out')return {p:null,warning:'Jugador descartado por lesión/ausencia.'};
 const mean=sample.mean,market=record.market,kind=market.kind,side=market.side||'over',line=market.line;
 if(side!=='over')return {p:null,warning:'El laboratorio de props solo evalúa overs.'};
 let p=null,adjusted=mean;
 if(record.sport==='basket'){
  if(!['points','rebounds','assists','threes','team_points','game_total'].includes(kind))
   return {p:null,warning:'Prop de básquet no compatible.'};
  if(!finite(record.expected_minutes)||record.expected_minutes<=0||!finite(record.baseline_minutes)||record.baseline_minutes<=0)
   return {p:null,warning:'Faltan minutos previstos y minutos base; no se supone tiempo en pista.'};
  const factor=clamp(record.expected_minutes/record.baseline_minutes,.5,1.6);
  const opponent=finite(record.opponent_factor)?clamp(record.opponent_factor,.7,1.3):1;
  adjusted=mean*factor*opponent;
  // La desviación estándar es obligatoria: no convertir media en confianza ficticia.
  const sd=record.sd;
  if(!(finite(sd)&&sd>0))return {p:null,warning:'Falta dispersión (sd) del jugador.'};
  const blowout=finite(record.blowout_probability)?clamp(record.blowout_probability,0,.65):0;
  const cut=finite(record.blowout_minutes_cut)?clamp(record.blowout_minutes_cut,0,.6):.2;
  p=mixture(normalOver(adjusted,sd,line),normalOver(adjusted*(1-cut),sd,line),blowout);
 }else if(record.sport==='nhl'){
  if(!['shots','goals','assists','points'].includes(kind))
   return {p:null,warning:'Prop NHL no compatible.'};
  if(!(finite(record.expected_toi)&&record.expected_toi>0&&finite(record.baseline_toi)&&record.baseline_toi>0))
   return {p:null,warning:'Falta proyección de tiempo en hielo.'};
  const factor=clamp(record.expected_toi/record.baseline_toi,.55,1.45);
  const opponent=finite(record.opponent_factor)?clamp(record.opponent_factor,.7,1.3):1;
  adjusted=mean*factor*opponent;
  p=poissonOver(adjusted,line);
 }else return {p:null,warning:'Deporte no compatible.'};
 return {p,mean:adjusted,sample_size:sample.size,model:record.sport==='basket'?'normal-con-minutos-y-blowout':'poisson-con-tiempo-en-hielo'};
}
function probabilityForFootball(record){
 const sample=fromCountHistory(record);
 if(!sample)return {p:null,warning:'Falta histórico de al menos 5 partidos para este mercado.'};
 if(!['goals','corners','cards'].includes(record.market?.kind)||record.market.side!=='over')
  return {p:null,warning:'Selecciona Over de goles, córners o tarjetas.'};
 const m=sample.mean;
 const p=finite(record.dispersion)&&record.dispersion>0
  ?negativeBinomialOver(m,record.market.line,record.dispersion)
  :poissonOver(m,record.market.line);
 return {p,mean:m,sample_size:sample.size,
  model:finite(record.dispersion)?'binomial-negativa':'poisson-conteos'};
}
function lastTenForm(team){
 const rows=team.last10_bo3;
 if(!Array.isArray(rows)||rows.length<10)return null;
 let won=0,weight=0;
 for(const [index,game] of rows.slice(0,10).entries()){
  if(![0,1].includes(game.win)||!(Number.isInteger(game.opponent_rank)&&game.opponent_rank>0))return null;
  const recency=Math.pow(.87,index);
  const difficulty=clamp(Math.pow(team.hltv_rank/game.opponent_rank,.25),.65,1.5);
  const w=recency*difficulty;
  won+=w*game.win;weight+=w;
 }
 return (won+2)/(weight+4);
}
function mapRates(team,name){
 const stats=team.maps&&team.maps[name];
 if(!stats||!Number.isInteger(stats.wins)||!Number.isInteger(stats.played)||
  stats.played<stats.wins||stats.wins<0)return null;
 return (stats.wins+4)/(stats.played+8);
}
export function mapWinProbability(teamA,teamB,name){
 if(!(Number.isInteger(teamA?.hltv_rank)&&teamA.hltv_rank>0&&
  Number.isInteger(teamB?.hltv_rank)&&teamB.hltv_rank>0))return null;
 const a=mapRates(teamA,name),b=mapRates(teamB,name);
 const formA=lastTenForm(teamA),formB=lastTenForm(teamB);
 if(a===null||b===null||formA===null||formB===null)return null;
 const ranking=clamp(Math.log(teamB.hltv_rank/teamA.hltv_rank),-2,2);
 return clamp(logistic(.47*(logit(a)-logit(b))+.23*ranking+.32*(logit(formA)-logit(formB))),.08,.92);
}
// Veto PROBABLE, no oficial: los bans se basan en debilidad por mapa y
// los picks en probabilidad de ganar el mapa. El orden BO3 es A ban/B ban,
// A pick/B pick/A ban/B ban, y último mapa restante.
export function likelyVeto(teamA,teamB,pool){
 if(!Array.isArray(pool)||pool.length!==7||new Set(pool).size!==7)return null;
 if(pool.some(m=>mapWinProbability(teamA,teamB,m)===null))return null;
 const left=[...pool],ban=[],pick=[];
 const remove=name=>{const i=left.indexOf(name);if(i<0)return false;left.splice(i,1);return true};
 const chosen=(side,mode)=>{
  const ordered=[...left].sort((a,b)=>{
   const pa=mapWinProbability(teamA,teamB,a),pb=mapWinProbability(teamA,teamB,b);
   const sa=side==='a'?pa:1-pa,sb=side==='a'?pb:1-pb;
   if(mode==='ban'){
    const team=side==='a'?teamA:teamB;
    const ra=finite(team.maps[a]?.ban_rate)?team.maps[a].ban_rate:0;
    const rb=finite(team.maps[b]?.ban_rate)?team.maps[b].ban_rate:0;
    return (rb-sb*.5)-(ra-sa*.5)||sa-sb;
   }
   return sb-sa;
  });
  return ordered[0];
 };
 for(const side of ['a','b']){const name=chosen(side,'ban');ban.push({team:side,map:name});remove(name)}
 for(const side of ['a','b']){const name=chosen(side,'pick');pick.push({team:side,map:name});remove(name)}
 for(const side of ['a','b']){const name=chosen(side,'ban');ban.push({team:side,map:name});remove(name)}
 return {bans:ban,picks:pick,decider:left[0],maps:[pick[0].map,pick[1].map,left[0]],predicted:true};
}
export function bestOfThree(a,b,c){
 if([a,b,c].some(x=>!finite(x)||x<0||x>1))return null;
 const twoZero=a*b,third=(a*(1-b)+(1-a)*b);
 return {a20:twoZero,a21:third*c,b21:third*(1-c),b20:(1-a)*(1-b),
  aWin:twoZero+third*c,bWin:1-twoZero-third*c,over25:third,
  aPlus15:1-(1-a)*(1-b),bPlus15:1-a*b};
}
export function probabilityForCS2(record){
 const teams=record.teams,pool=record.map_pool;
 if(!teams?.a||!teams?.b)return {p:null,warning:'Faltan equipos y estadísticas CS2.'};
 const veto=likelyVeto(teams.a,teams.b,pool);
 if(!veto)return {p:null,warning:'Se requieren los últimos 10 BO3, ranking HLTV y datos de los 7 mapas para ambos equipos.'};
 const maps=record.veto_confirmed?.maps||veto.maps;
 if(maps.length!==3||new Set(maps).size!==3||maps.some(m=>!pool.includes(m)))
  return {p:null,warning:'Veto confirmado inválido.'};
 const ps=maps.map(m=>mapWinProbability(teams.a,teams.b,m));
 const series=bestOfThree(...ps),kind=record.market?.kind;
 const values={winner_a:series.aWin,winner_b:series.bWin,over_2_5_maps:series.over25,
  handicap_a_minus_1_5:series.a20,handicap_b_minus_1_5:series.b20,
  handicap_a_plus_1_5:series.aPlus15,handicap_b_plus_1_5:series.bPlus15};
 return {p:values[kind]??null,model:'bo3-veto-mapas-ranking-forma',veto:record.veto_confirmed?{...veto,maps,predicted:false}:veto,series,
  warning:record.veto_confirmed?null:'Veto proyectado, todavía no confirmado.'};
}
export function analyzeRecord(record,fixture,now=new Date()){
 const errors=[];
 if(!['football','basket','nhl','cs2'].includes(record?.sport))errors.push('Deporte no compatible.');
 if(!record?.market||typeof record.market.kind!=='string')errors.push('Mercado ausente.');
 if(!validEvidence(record?.source))errors.push('Fuente estadística sin URL HTTPS y fecha de captura.');
 if(!fixture?.utc||!validDate(fixture.utc)||Date.parse(fixture.utc)<=now.getTime())
  errors.push('Partido no verificado como futuro.');
 if(fixture?.sport!==record?.sport)errors.push('Deporte del partido no coincide.');
 const quoted=record?.quote,quote=quoted?.decimal;
 if(!validEvidence(quoted?.source)||!finite(quote)||quote<=1)errors.push('Cuota sin fuente verificable.');
 if(record?.market?.kind!=='over_2_5_maps'&&record?.sport!=='cs2'&&record?.market?.side!=='over')
  errors.push('Solo se admiten overs de jugador o conteos.');
 if(errors.length)return {status:'sin_datos',errors,p:null,metrics:null};
 let outcome;
 if(record.sport==='football')outcome=probabilityForFootball(record);
 else if(record.sport==='cs2')outcome=probabilityForCS2(record);
 else outcome=probabilityForPlayer(record);
 if(!(outcome.p>0&&outcome.p<1))return {status:'sin_modelo',errors:[outcome.warning||'Probabilidad no calculable.'],p:null,metrics:null};
 const metrics=oddsMetrics(outcome.p,quote);
 const age=(now.getTime()-Date.parse(quoted.source.captured_at))/3600000;
 const aged=!Number.isFinite(age)||age<0||age>8;
 const quoteThreshold=quote>1.8;
 const evidential=record.source.verified===true&&quoted.source.verified===true;
 const qualified=quoteThreshold&&!aged&&evidential&&metrics.ev>.025;
 const warnings=[...(outcome.warning?[outcome.warning]:[]),
  ...(aged?['Cuota desactualizada: más de ocho horas o fecha futura.']:[]),
  ...(!quoteThreshold?['Cuota fuera del filtro > 1.80.']:[]),
  ...(!evidential?['Datos importados sin verificación documental.']:[])];
 return {...outcome,metrics,p:outcome.p,status:qualified?'candidato':'exploratorio',warnings,
  // verified=true es una afirmación de la fuente importada, no auditoría de EdgeLab.
  independently_verified:false,model_version:MODEL_VERSION};
}
export function validateSnapshot(input){
 if(!input||input.schema!==1||!Array.isArray(input.records)||input.records.length>1000)
  throw Error('Formato inválido: se requiere {schema:1,records:[]} (máximo 1000).');
 return {schema:1,records:input.records.filter(r=>r&&typeof r.fixture_id==='string'&&
  ['football','basket','nhl','cs2'].includes(r.sport)&&r.market&&typeof r.market==='object')};
}
