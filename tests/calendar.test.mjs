import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {LEAGUES,scoreboardURL,parseScoreboard,futureOnly,historyOnly,localDateTime} from '../assets/js/fixtures.mjs';

const sample=(id,date,state='pre',homeScore=null,awayScore=null)=>({
 id,date,status:{type:{state,completed:state==='post'}},
 competitions:[{competitors:[
  {homeAway:'away',team:{displayName:'Visita FC'},score:awayScore},
  {homeAway:'home',team:{displayName:'Local FC'},score:homeScore}
 ]}]
});
const league=LEAGUES.football[0];
test('calendario incluye 6 ligas, NBA/WNBA, NHL y NFL',()=>{
 assert.equal(LEAGUES.football.length,6);
 assert.equal(LEAGUES.basket.length,2);
 assert.equal(LEAGUES.nhl[0].id,'nhl');
 assert.equal(LEAGUES.nfl[0].id,'nfl');
});
test('URLs usan competiciones permitidas y fechas en UTC',()=>{
 const u=scoreboardURL(league,new Date('2026-10-24T12:00:00Z'),new Date('2026-10-31T12:00:00Z'));
 assert.match(u,/soccer\/eng\.1\/scoreboard\?dates=20261024-20261031/);
 assert.throws(()=>scoreboardURL({id:'fake',path:'soccer'},new Date(),new Date()));
});
test('normaliza equipo local, visita y hora',()=>{
 const [m]=parseScoreboard({events:[sample('1','2026-10-25T20:00:00Z')]},league);
 assert.equal(m.home,'Local FC');assert.equal(m.away,'Visita FC');assert.equal(m.status,'pre');
});
test('excluye partidos iniciados o finalizados y repetidos',()=>{
 const data=parseScoreboard({events:[
  sample('1','2026-10-24T14:00:00Z'),
  sample('2','2026-10-26T20:00:00Z'),
  sample('2','2026-10-26T20:00:00Z'),
  sample('3','2026-10-27T20:00:00Z','post',1,0)
 ]},league);
 assert.deepEqual(futureOnly(data,new Date('2026-10-25T00:00:00Z')).map(x=>x.id),['2']);
});
test('sólo resultados terminados anteriores al día consultado alimentan el modelo',()=>{
 const data=parseScoreboard({events:[
  sample('1','2026-09-10T20:00:00Z','post',3,1),
  sample('2','2026-10-28T20:00:00Z')
 ]},league);
 const history=historyOnly(data,new Date('2026-10-24T20:00:00Z'));
 assert.equal(history.length,1);assert.equal(history[0].hg,3);assert.equal(history[0].ag,1);
});
test('usa hora de Chile, incluido cambio de fecha',()=>{
 assert.equal(localDateTime(new Date('2026-10-26T01:00:00Z')),'2026-10-25T22:00');
});
test('interfaz conecta calendario con formulario y motor sin secretos',()=>{
 const h=readFileSync(new URL('../index.html',import.meta.url),'utf8');
 const app=readFileSync(new URL('../assets/js/app.js',import.meta.url),'utf8');
 const calendar=readFileSync(new URL('../assets/js/calendar.mjs',import.meta.url),'utf8');
 assert.match(h,/id="calendarList"/);assert.match(h,/src="assets\/js\/calendar.mjs"/);
 assert.match(app,/EdgeLabUI=\{chooseFixture/);assert.match(calendar,/estimateLambdas/);
 assert.doesNotMatch(calendar,/DUNKAPI_API_KEY\s*=/);
});
