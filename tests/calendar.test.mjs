import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {LEAGUES,scoreboardURL,parseScoreboard,futureOnly,historyOnly,localDateTime,daysInclusive,fetchLeague} from '../assets/js/fixtures.mjs';
const sample=(id,date,state='pre',homeScore=null,awayScore=null)=>({
 id,date,status:{type:{state,completed:state==='post'}},
 competitions:[{competitors:[
  {homeAway:'away',team:{displayName:'Visita FC'},score:awayScore},
  {homeAway:'home',team:{displayName:'Local FC'},score:homeScore}
 ]}]
});
const league=LEAGUES.football[0];
test('seis ligas, NBA/WNBA, NHL y NFL',()=>{
 assert.equal(LEAGUES.football.length,6);assert.equal(LEAGUES.basket.length,2);
 assert.equal(LEAGUES.nhl[0].id,'nhl');assert.equal(LEAGUES.nfl[0].id,'nfl');
});
test('la URL de ESPN usa una única fecha, nunca el rango que devuelve HTTP 400',()=>{
 const url=scoreboardURL(league,new Date('2026-10-24T12:00:00Z'));
 assert.match(url,/soccer\/eng\.1\/scoreboard\?dates=20261024&/);
 assert.doesNotMatch(url,/20261024-20261031/);
 assert.throws(()=>scoreboardURL({id:'fake',path:'soccer'},new Date()));
});
test('normaliza equipos y excluye iniciados, finalizados y repetidos',()=>{
 const data=parseScoreboard({events:[
  sample('1','2026-10-24T14:00:00Z'),
  sample('2','2026-10-26T20:00:00Z'),
  sample('2','2026-10-26T20:00:00Z'),
  sample('3','2026-10-27T20:00:00Z','post',1,0)
 ]},league);
 assert.equal(data[0].home,'Local FC');
 assert.deepEqual(futureOnly(data,new Date('2026-10-25T00:00:00Z')).map(x=>x.id),['2']);
});
test('una fecha sin hora confirmada no es elegible para analizar y solo se muestra en días futuros',()=>{
 const future={id:'one',competitionId:'eng.1',status:'pre',date:'2026-10-27',utc:null,timeTBD:true};
 const today={...future,id:'two',date:'2026-10-24'};
 assert.deepEqual(futureOnly([future,today],new Date('2026-10-24T14:00:00Z')).map(x=>x.id),['one']);
});
test('histórico solo contiene resultados anteriores al día y finalizados',()=>{
 const data=parseScoreboard({events:[sample('1','2026-09-10T20:00:00Z','post',3,1),sample('2','2026-10-28T20:00:00Z')]},league);
 const h=historyOnly(data,new Date('2026-10-24T20:00:00Z'));
 assert.equal(h.length,1);assert.equal(h[0].hg,3);
});
test('hora chilena con desplazamiento UTC',()=>{
 assert.equal(localDateTime(new Date('2026-10-26T01:00:00Z')),'2026-10-25T22:00');
});
test('genera una lista inclusiva limitada para evitar llamadas masivas',()=>{
 assert.equal(daysInclusive(new Date('2026-10-24T12:00Z'),new Date('2026-10-26T12:00Z')).length,3);
 assert.throws(()=>daysInclusive(new Date('2026-01-01'),new Date('2026-12-01')));
});
test('obtiene varios días mediante llamadas individuales y deduplica partidos',async()=>{
 const seen=[];
 const mock=async url=>{seen.push(url);return {ok:true,json:async()=>({events:[sample('1','2026-10-26T20:00:00Z')]})}};
 const got=await fetchLeague(league,new Date('2026-10-24T12:00Z'),new Date('2026-10-27T12:00Z'),mock);
 assert.equal(seen.length,4);assert.ok(seen.every(x=>/dates=\d{8}&/.test(x)));
 assert.equal(got.length,1);assert.equal(got.daysOk,4);
});
test('errores parciales no eliminan los días exitosos',async()=>{
 const got=await fetchLeague(league,new Date('2026-10-24T12:00Z'),new Date('2026-10-25T12:00Z'),async url=>{
  if(url.includes('20261025'))throw Error('NetworkError');
  return {ok:true,json:async()=>({events:[sample('1','2026-10-26T20:00:00Z')]})};
 });
 assert.equal(got.length,1);assert.equal(got.errors.length,1);
});
test('si no responde ninguna petición la interfaz recibe un error explícito',async()=>{
 await assert.rejects(()=>fetchLeague(league,new Date('2026-10-24T12:00Z'),new Date('2026-10-25T12:00Z'),async()=>{throw Error('NetworkError')}),/sin respuesta/);
});
test('interfaz integra el calendario y mantiene el modelo y controles de claves',()=>{
 const html=readFileSync(new URL('../index.html',import.meta.url),'utf8');
 const app=readFileSync(new URL('../assets/js/app.js',import.meta.url),'utf8');
 const calendar=readFileSync(new URL('../assets/js/calendar.mjs',import.meta.url),'utf8');
 assert.match(html,/id="calendarList"/);assert.match(html,/src="assets\/js\/calendar.mjs"/);
 assert.match(app,/EdgeLabUI=\{chooseFixture/);assert.match(calendar,/estimateLambdas/);
 assert.match(calendar,/data\/calendar\.json/);
 assert.doesNotMatch(calendar,/DUNKAPI_API_KEY\s*=/);
});
