import test from 'node:test';
import assert from 'node:assert/strict';
import {sameLine,modelProbability,fairMarketProbability,assessQuote,reportForEvent} from '../assets/js/value-engine.mjs';
import {predictMarkets} from '../assets/js/football-model.mjs';
import {readFileSync} from 'node:fs';

test('no compara líneas distintas ni jugadores distintos',()=>{
 const a={kind:'prop',line:24.5,label:'Jane Smith (Points)'};
 assert.equal(sameLine(a,{...a,line:25.5}),false);
 assert.equal(sameLine(a,{...a,label:'Other (Points)'}),false);
 assert.equal(sameLine(a,{...a}),true);
});
test('comparación sin margen requiere ambos lados o 1X2 completo',()=>{
 const market={kind:'result',selections:{home:2.1,draw:3.2,away:3.5}};
 const p=fairMarketProbability(market,'home');
 assert.ok(p>0&&p<1);
 assert.equal(fairMarketProbability({kind:'result',selections:{home:2.1}},'home'),null);
});
test('Poisson para fútbol y EV a cuota decimal',()=>{
 const rates={home:1.6,away:0.9};
 const predictions=predictMarkets(rates.home,rates.away);
 const market={kind:'result',line:null,selections:{home:2.1,draw:3.2,away:3.5}};
 const p=modelProbability(market,'home',rates,predictions);
 assert.ok(p>.45&&p<.75);
 const x=assessQuote(market,'home',2.2,null,rates,predictions);
 assert.equal(x.type,'modelo');
 assert.ok(Math.abs(x.ev-(p*2.2-1))<1e-12);
 assert.equal(modelProbability({kind:'result',selections:{home:2,away:2}},'home',rates,predictions),null);
 assert.equal(modelProbability({kind:'goals',line:2},'over',rates,predictions),null);
});
test('la comparación entre dos casas es distinta del modelo',()=>{
 const first={kind:'prop',line:25.5,label:'Jane Smith (Points)',selections:{over:2.1,under:1.78}};
 const second={...first,selections:{over:1.8,under:2.05}};
 const x=assessQuote(first,'over',2.1,second,null,null);
 assert.equal(x.type,'comparación entre casas');
 assert.ok(x.p>0&&x.p<1);
 assert.equal(assessQuote(first,'over',2.1,{...second,line:24.5},null,null).type,'sin_modelo');
});
test('los equipos con pronóstico insuficiente se quedan sin probabilidad independiente',()=>{
 const event={sport:'basket',books:{Betano:[{kind:'prop',label:'P. Roe (Assists)',line:5.5,selections:{over:2.03}}]}};
 const x=reportForEvent(event,{home:'X',away:'Y',date:'2026-10-29'},[],{});
 assert.equal(x.rows[0].analysis.type,'sin_modelo');
});
test('frontend lee instantánea sin insertar secretos en HTML',()=>{
 const code=readFileSync(new URL('../assets/js/odds-dashboard.mjs',import.meta.url),'utf8');
 assert.match(code,/odds\.json/);
 assert.doesNotMatch(code,/apiKey=/);
});
