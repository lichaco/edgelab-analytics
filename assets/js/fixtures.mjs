/** Normalización de calendarios de ESPN (API pública no oficial, sin credenciales). */
export const LEAGUES = {
 football:[
  {id:'eng.1',label:'Premier League',path:'soccer'},
  {id:'esp.1',label:'La Liga',path:'soccer'},
  {id:'ita.1',label:'Serie A',path:'soccer'},
  {id:'ger.1',label:'Bundesliga',path:'soccer'},
  {id:'fra.1',label:'Ligue 1',path:'soccer'},
  {id:'chi.1',label:'Primera División Chile',path:'soccer'}
 ],
 basket:[{id:'nba',label:'NBA',path:'basketball'},{id:'wnba',label:'WNBA',path:'basketball'}],
 nhl:[{id:'nhl',label:'NHL',path:'hockey'}],
 nfl:[{id:'nfl',label:'NFL',path:'football'}],
 cs2:[]
};
const pad=n=>String(n).padStart(2,'0');
export const ymd=d=>''+d.getUTCFullYear()+pad(d.getUTCMonth()+1)+pad(d.getUTCDate());
export function localDateTime(date){
 const parts=new Intl.DateTimeFormat('en-GB',{timeZone:'America/Santiago',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(date);
 const p=Object.fromEntries(parts.map(x=>[x.type,x.value]));
 return p.year+'-'+p.month+'-'+p.day+'T'+p.hour+':'+p.minute;
}
export const dayChile=date=>localDateTime(date).slice(0,10);
export function scoreboardURL(league,start,end){
 if(!Object.values(LEAGUES).flat().some(l=>l.id===league.id&&l.path===league.path))throw Error('Competencia desconocida');
 return 'https://site.api.espn.com/apis/site/v2/sports/'+league.path+'/'+league.id+'/scoreboard?dates='+ymd(start)+'-'+ymd(end)+'&limit=500';
}
export function parseScoreboard(payload,league){
 if(!Array.isArray(payload?.events))throw Error('Respuesta de calendario no válida');
 return payload.events.flatMap(e=>{
  const ts=Date.parse(e?.date),competitors=e?.competitions?.[0]?.competitors||[];
  const h=competitors.find(x=>x.homeAway==='home'),a=competitors.find(x=>x.homeAway==='away');
  if(!Number.isFinite(ts)||!h?.team?.displayName||!a?.team?.displayName)return [];
  const status=e?.status?.type?.state||'';
  const finished=status==='post'||e?.status?.type?.completed===true;
  const score=x=>{const v=x?.score;if(v===undefined||v===null||String(v).trim()==='')return null;const n=Number(v);return Number.isInteger(n)&&n>=0&&n<40?n:null};
  return [{id:String(e.id),competitionId:league.id,league:league.label,
   sport:league.path==='soccer'?'football':league.path==='basketball'?'basket':league.id,
   home:h.team.displayName,away:a.team.displayName,utc:new Date(ts).toISOString(),
   status,finished,hg:finished?score(h):null,ag:finished?score(a):null}];
 });
}
export function futureOnly(matches,now=new Date()){
 const seen=new Set();
 return matches.filter(e=>{
  if(e.finished||e.status!=='pre'||Date.parse(e.utc)<=now.getTime())return false;
  const key=e.competitionId+'/'+e.id;
  if(seen.has(key))return false;
  seen.add(key);return true;
 }).sort((a,b)=>a.utc.localeCompare(b.utc));
}
export function historyOnly(matches,now=new Date()){
 const today=dayChile(now);
 return matches.filter(e=>e.finished&&e.hg!==null&&e.ag!==null&&dayChile(new Date(e.utc))<today)
  .map(e=>({date:dayChile(new Date(e.utc)),home:e.home,away:e.away,hg:e.hg,ag:e.ag}));
}
export async function fetchLeague(league,start,end,fetcher=fetch){
 const ctl=new AbortController(),timer=setTimeout(()=>ctl.abort(),18000);
 try{
  const response=await fetcher(scoreboardURL(league,start,end),{signal:ctl.signal});
  if(!response.ok)throw Error('ESPN HTTP '+response.status);
  return parseScoreboard(await response.json(),league);
 }finally{clearTimeout(timer)}
}
