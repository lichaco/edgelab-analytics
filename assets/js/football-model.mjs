// EdgeLab Football — modelo Poisson experimental, sin dependencia de cuotas.
const HALF_LIFE_DAYS=155,MAX_TRAIN_DAYS=510,PRIOR=5,MAX_GOALS=20;
export const LEAGUES=Object.freeze({
 premier:{label:'Premier League',code:'en.1'},
 laliga:{label:'La Liga',code:'es.1'},
 seriea:{label:'Serie A',code:'it.1'},
 bundesliga:{label:'Bundesliga',code:'de.1'},
 ligue1:{label:'Ligue 1',code:'fr.1'},
 chile:{label:'Primera División Chile',code:null}
});
const dayOk=s=>typeof s==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(s)&&!Number.isNaN(Date.parse(s+'T12:00:00Z'));
const days=(a,b)=>(Date.parse(b+'T12:00:00Z')-Date.parse(a+'T12:00:00Z'))/86400000;
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const round=(x,n=4)=>Number(x.toFixed(n));
export function normalizeOpenFootball(data,season){
 if(!Array.isArray(data?.matches))throw Error('Formato de datos de la fuente inválido');
 return data.matches.map(m=>{
  // El proveedor representa algunos resultados sin confirmar como arrays:
  // se aceptan SOLO marcadores explícitos score.ft.
  const ft=m?.score&&!Array.isArray(m.score)?m.score.ft:null;
  const valid=Array.isArray(ft)&&ft.length===2&&ft.every(x=>Number.isInteger(x)&&x>=0&&x<30);
  return {date:m.date,home:m.team1,away:m.team2,season,hg:valid?ft[0]:null,ag:valid?ft[1]:null};
 }).filter(m=>dayOk(m.date)&&typeof m.home==='string'&&m.home.trim().length&&typeof m.away==='string'&&m.away.trim().length&&m.home!==m.away);
}
function historyBefore(data,asOf){
 return data.filter(m=>m.hg!==null&&m.ag!==null&&m.date<asOf&&days(m.date,asOf)<=MAX_TRAIN_DAYS)
 .map(m=>({...m,w:Math.pow(.5,days(m.date,asOf)/HALF_LIFE_DAYS)}));
}
export function estimateLambdas(data,home,away,asOf){
 if(!dayOk(asOf)||!home||!away||home===away)throw Error('Fecha/equipos inválidos');
 const hist=historyBefore(data,asOf);
 if(hist.length<55)return null;
 const weight=hist.reduce((s,m)=>s+m.w,0);
 const leagueHome=hist.reduce((s,m)=>s+m.w*m.hg,0)/weight;
 const leagueAway=hist.reduce((s,m)=>s+m.w*m.ag,0)/weight;
 if(leagueHome<=0||leagueAway<=0)return null;
 const teamStats=(t,side)=>{
  const ms=hist.filter(m=>side==='home'?m.home===t:m.away===t);
  const n=ms.reduce((s,m)=>s+m.w,0);
  return {games:ms.length,weight:n,
   gf:ms.reduce((s,m)=>s+m.w*(side==='home'?m.hg:m.ag),0),
   ga:ms.reduce((s,m)=>s+m.w*(side==='home'?m.ag:m.hg),0)};
 };
 const h=teamStats(home,'home'),a=teamStats(away,'away');
 if(h.games<3||a.games<3)return null;
 const hAttack=(h.gf+PRIOR*leagueHome)/(h.weight+PRIOR)/leagueHome;
 const aDef=(a.ga+PRIOR*leagueHome)/(a.weight+PRIOR)/leagueHome;
 const aAttack=(a.gf+PRIOR*leagueAway)/(a.weight+PRIOR)/leagueAway;
 const hDef=(h.ga+PRIOR*leagueAway)/(h.weight+PRIOR)/leagueAway;
 return {home:round(clamp(leagueHome*hAttack*aDef,.35,4.2)),
 away:round(clamp(leagueAway*aAttack*hDef,.35,4.2)),
 trainGames:hist.length,homeSamples:h.games,awaySamples:a.games,
 lastResultDate:hist.reduce((s,m)=>m.date>s?m.date:s,'')};
}
export function poissonPMF(lambda){
 if(!Number.isFinite(lambda)||lambda<0)throw Error('Lambda inválida');
 const out=[Math.exp(-lambda)];
 for(let i=1;i<=MAX_GOALS;i++)out.push(out[i-1]*lambda/i);
 const norm=out.reduce((a,b)=>a+b,0);
 return out.map(x=>x/norm);
}
export function predictMarkets(homeLambda,awayLambda){
 const h=poissonPMF(homeLambda),a=poissonPMF(awayLambda);let home=0,draw=0,away=0;
 for(let x=0;x<h.length;x++)for(let y=0;y<a.length;y++){
  const p=h[x]*a[y];
  if(x>y)home+=p;else if(x===y)draw+=p;else away+=p;
 }
 const total=poissonPMF(homeLambda+awayLambda),goals={};
 for(const n of [1.5,2.5,3.5]){
  const under=total.slice(0,Math.floor(n)+1).reduce((s,p)=>s+p,0);
  goals[String(n)]={under,over:1-under};
 }
 return {oneXTwo:{home,draw,away},goals};
}
export function evaluateMatch(data,fixture,asOf){
 if(!fixture||!dayOk(fixture.date)||fixture.date<=asOf)return null;
 const lambdas=estimateLambdas(data,fixture.home,fixture.away,asOf);
 return lambdas?{fixture,lambdas,...predictMarkets(lambdas.home,lambdas.away)}:null;
}
export function oddsAnalysis(p,odds){
 const n=Number(odds);
 if(!Number.isFinite(n)||n<=1||!(p>0&&p<1))return null;
 return {decimal:n,implicit:1/n,fair:1/p,edge:p-1/n,ev:p*n-1};
}
export function noVigThreeWay(odds){
 const nums=odds.map(Number);
 if(nums.length!==3||nums.some(x=>!Number.isFinite(x)||x<=1))return null;
 const vig=nums.reduce((s,x)=>s+1/x,0);
 return nums.map(x=>1/x/vig);
}
export function backtest(data,asOf,max=65){
 const played=data.filter(m=>m.hg!==null&&m.ag!==null&&m.date<asOf).sort((a,b)=>a.date.localeCompare(b.date));
 let n=0,brier=0,logLoss=0,base=0;
 for(const m of played.slice(-Math.max(max*2,100))){
  const strength=estimateLambdas(data,m.home,m.away,m.date);
  if(!strength)continue;
  const {home,draw,away}=predictMarkets(strength.home,strength.away).oneXTwo;
  const p=[home,draw,away],actual=[+(m.hg>m.ag),+(m.hg===m.ag),+(m.hg<m.ag)];
  brier+=p.reduce((s,x,i)=>s+(x-actual[i])**2,0);
  logLoss-=Math.log(Math.max(1e-10,p[actual.indexOf(1)]));
  base+=actual.reduce((s,x,i)=>s+([.44,.26,.30][i]-x)**2,0);
  n++;if(n>=max)break;
 }
 return {games:n,brier:n?round(brier/n):null,logLoss:n?round(logLoss/n):null,baselineBrier:n?round(base/n):null};
}