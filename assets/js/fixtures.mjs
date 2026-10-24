/** EdgeLab calendar: daily ESPN API queries, no unsupported date-range requests. */
export const LEAGUES={
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
export const dateOfFixture=f=>f.utc?dayChile(new Date(f.utc)):f.date;
export function scoreboardURL(league,day){
 if(!Object.values(LEAGUES).flat().some(l=>l.id===league?.id&&l.path===league?.path))throw Error('Competencia desconocida');
 if(!(day instanceof Date)||Number.isNaN(day.getTime()))throw Error('Fecha de consulta inválida');
 // ESPN broke YYYYMMDD-YYYYMMDD date-range queries in September 2026.
 return `https://site.api.espn.com/apis/site/v2/sports/${league.path}/${league.id}/scoreboard?dates=${ymd(day)}&limit=300`;
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
   home:h.team.displayName,away:a.team.displayName,utc:new Date(ts).toISOString(),date:new Date(ts).toISOString().slice(0,10),
   status,finished,hg:finished?score(h):null,ag:finished?score(a):null,source:'ESPN'}];
 });
}
export function futureOnly(matches,now=new Date()){
 const seen=new Set(),today=dayChile(now);
 return matches.filter(e=>{
  if(!e||e.finished||e.status!=='pre')return false;
  // Unknown kick-off: show date only if it is strictly a future calendar day.
  if(!e.utc){if(!e.timeTBD||!e.date||e.date<=today)return false}
  else if(!Number.isFinite(Date.parse(e.utc))||Date.parse(e.utc)<=now.getTime())return false;
  const key=e.competitionId+'/'+e.id;
  if(seen.has(key))return false;
  seen.add(key);return true;
 }).sort((a,b)=>(a.utc||a.date+'T23:59:59').localeCompare(b.utc||b.date+'T23:59:59'));
}
export function historyOnly(matches,now=new Date()){
 const today=dayChile(now);
 return matches.filter(e=>e.finished&&e.hg!==null&&e.ag!==null&&e.utc&&dayChile(new Date(e.utc))<today)
  .map(e=>({date:dayChile(new Date(e.utc)),home:e.home,away:e.away,hg:e.hg,ag:e.ag}));
}
export function daysInclusive(start,end,max=34){
 const a=Date.UTC(start.getUTCFullYear(),start.getUTCMonth(),start.getUTCDate());
 const b=Date.UTC(end.getUTCFullYear(),end.getUTCMonth(),end.getUTCDate());
 const count=Math.floor((b-a)/86400000)+1;
 if(!Number.isInteger(count)||count<1||count>max)throw Error('Intervalo de fechas inválido o demasiado amplio');
 return Array.from({length:count},(_,i)=>new Date(a+i*86400000));
}
export async function fetchLeague(league,start,end,fetcher=fetch){
 const days=daysInclusive(start,end),results=[],errors=[];let ok=0;
 // Rate-controlled batches: unlike the former broken single range query.
 for(let k=0;k<days.length;k+=5){
  const chunk=days.slice(k,k+5);
  const responses=await Promise.allSettled(chunk.map(async d=>{
   const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),10000);
   try{
    const r=await fetcher(scoreboardURL(league,d),{signal:controller.signal});
    if(!r.ok)throw Error('HTTP '+r.status);
    return parseScoreboard(await r.json(),league);
   }finally{clearTimeout(timer)}
  }));
  for(let i=0;i<responses.length;i++){
   const result=responses[i];
   if(result.status==='fulfilled'){ok++;results.push(...result.value)}
   else errors.push(ymd(chunk[i])+': '+String(result.reason?.message||result.reason).slice(0,100));
  }
  if(ok===0&&errors.length>=10)break; // Provider rejected all requests: stop retrying.
 }
 if(!ok)throw Error('ESPN sin respuesta ('+errors.slice(0,2).join('; ')+')');
 const dedup=[...new Map(results.map(x=>[x.competitionId+'/'+x.id,x])).values()];
 dedup.errors=errors;dedup.daysOk=ok;
 return dedup;
}
