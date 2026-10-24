import test from 'node:test';
import assert from 'node:assert/strict';
import {normalizeOpenFootball,estimateLambdas,predictMarkets,poissonPMF,noVigThreeWay,oddsAnalysis,evaluateMatch,backtest} from '../assets/js/football-model.mjs';
const day=n=>new Date(Date.UTC(2026,0,1+n)).toISOString().slice(0,10);
const teams=['A','B','C','D','E','F','G','H'],matches=[];
for(let i=0;i<160;i++){
 const home=teams[i%8];
 let away=teams[(i+1+Math.floor(i/8)%7)%8];if(home===away)away=teams[(i+2)%8];
 matches.push({date:day(i),home,away,hg:i%4,ag:(i+1)%3});
}
test('OpenFootball descarta resultados-placeholder y conserva cero a cero explícito',()=>{
 const m=normalizeOpenFootball({matches:[
  {date:'2026-02-01',team1:'A',team2:'B',score:[0,0]},
  {date:'2026-02-02',team1:'C',team2:'D',score:{ft:[0,0]}},
  {date:'2026-02-03',team1:'E',team2:'F'}
 ]},'2025-26');
 assert.equal(m[0].hg,null);assert.equal(m[1].hg,0);assert.equal(m[2].hg,null);
});
test('Poisson 1X2 suma uno y Over disminuye al subir la línea',()=>{
 const p=predictMarkets(1.65,1.09);
 assert.ok(Math.abs(p.oneXTwo.home+p.oneXTwo.draw+p.oneXTwo.away-1)<1e-8);
 assert.ok(p.goals['1.5'].over>p.goals['2.5'].over);
 assert.ok(p.goals['2.5'].over>p.goals['3.5'].over);
 assert.ok(Math.abs(poissonPMF(4.2).reduce((x,y)=>x+y,0)-1)<1e-12);
});
test('No predice con pocos datos ni equipo no observado',()=>{
 assert.equal(estimateLambdas(matches.slice(0,40),'A','B',day(41)),null);
 assert.equal(estimateLambdas(matches,'A','Z',day(170)),null);
});
test('No hay filtración temporal de partidos en el futuro',()=>{
 const prev=estimateLambdas(matches,'A','B',day(140));
 assert.deepEqual(estimateLambdas([...matches,{date:day(140),home:'A',away:'B',hg:25,ag:0}],'A','B',day(140)),prev);
 assert.equal(evaluateMatch(matches,{date:day(140),home:'A',away:'B'},day(140)),null);
});
test('Cuotas decimales, probabilidad sin margen y EV',()=>{
 const p=noVigThreeWay([2.1,3.3,3.5]);assert.ok(Math.abs(p.reduce((x,y)=>x+y,0)-1)<1e-12);
 assert.equal(noVigThreeWay([0,3,4]),null);
 assert.ok(Math.abs(oddsAnalysis(.6,2).ev-.2)<1e-12);
});
test('Backtest temporal entrega Brier calculable',()=>{
 const b=backtest(matches,day(165),32);
 assert.ok(b.games>0);assert.ok(Number.isFinite(b.brier));assert.ok(b.brier>=0&&b.brier<=2);
});
