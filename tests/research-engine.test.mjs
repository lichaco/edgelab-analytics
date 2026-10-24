import test from 'node:test';
import assert from 'node:assert/strict';
import {poissonOver,negativeBinomialOver,normalOver,oddsMetrics,bestOfThree,
 mapWinProbability,likelyVeto,analyzeRecord,validateSnapshot} from '../assets/js/research-engine.mjs';

test('colas estadísticas y cuotas justas',()=>{
 assert.ok(Math.abs(poissonOver(3,2.5)-(1-Math.exp(-3)*(1+3+4.5)))<1e-9);
 assert.equal(poissonOver(-1,2.5),null);
 assert.equal(poissonOver(3,2),null);
 assert.ok(negativeBinomialOver(4,3.5,2)>0&&negativeBinomialOver(4,3.5,2)<1);
 assert.ok(normalOver(25,6,24.5)>.45);
 assert.equal(oddsMetrics(.6,2).ev,.2);
});
test('BO3 exhaustivo y hándicap correctamente complementarios',()=>{
 const r=bestOfThree(.7,.3,.55);
 assert.ok(Math.abs(r.a20+r.a21+r.b21+r.b20-1)<1e-12);
 assert.ok(Math.abs(r.over25-(r.a21+r.b21))<1e-12);
 assert.ok(Math.abs(r.bPlus15-(1-r.a20))<1e-12);
});
const pool=['Dust2','Mirage','Inferno','Nuke','Ancient','Anubis','Overpass'];
function team(rank,seed){
 return {hltv_rank:rank,last10_bo3:Array.from({length:10},(_,i)=>({win:Number((i+seed)%3!==0),opponent_rank:5+i})),
  maps:Object.fromEntries(pool.map((map,i)=>[map,{wins:2+(i+seed)%5,played:9,ban_rate:(i+seed)%3/5}]))};
}
test('veto usa exactamente siete mapas y diez BO3 por equipo',()=>{
 const a=team(3,0),b=team(15,1),v=likelyVeto(a,b,pool);
 assert.equal(v.bans.length,4);assert.equal(v.picks.length,2);
 assert.equal(v.maps.length,3);assert.equal(new Set(v.maps).size,3);
 assert.ok(mapWinProbability(a,b,'Dust2')>0&&mapWinProbability(a,b,'Dust2')<1);
 assert.equal(likelyVeto({...a,last10_bo3:a.last10_bo3.slice(0,9)},b,pool),null);
});
const clock=new Date('2026-10-24T11:00:00Z');
const fixture={id:'f',sport:'nhl',utc:'2026-10-25T20:00:00Z'};
const source={name:'Dataset verificable',url:'https://example.com/data',captured_at:'2026-10-24T10:00:00Z',verified:true};
const sample={fixture_id:'f',sport:'nhl',player:'J. Doe',
 market:{kind:'shots',side:'over',line:2.5},last10:[3,2,4,3,1,4,3,2,2,4],
 expected_toi:18,baseline_toi:18,source,quote:{decimal:2.05,book:'Example',source}};
test('sin fuente/partido/tiempo sobre hielo no inventa modelo',()=>{
 assert.equal(analyzeRecord({...sample,source:null},fixture,clock).status,'sin_datos');
 assert.equal(analyzeRecord({...sample,expected_toi:null},fixture,clock).status,'sin_modelo');
 assert.equal(analyzeRecord(sample,{...fixture,utc:'2026-10-23T20:00:00Z'},clock).status,'sin_datos');
});
test('prop verificable calcula p y EV y exige cuota >1.80 para señal',()=>{
 const result=analyzeRecord(sample,fixture,clock);
 assert.ok(result.p>0&&result.p<1);
 assert.ok(result.metrics.fair>1);
 assert.ok(['candidato','exploratorio'].includes(result.status));
 assert.equal(analyzeRecord({...sample,quote:{...sample.quote,decimal:1.8}},fixture,clock).status,'exploratorio');
});
test('JSON normalizado rechaza estructuras falsas',()=>{
 assert.throws(()=>validateSnapshot({schema:1,records:{}}));
 assert.equal(validateSnapshot({schema:1,records:[sample]}).records.length,1);
});
