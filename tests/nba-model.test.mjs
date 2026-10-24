import test from 'node:test';
import assert from 'node:assert/strict';
import {attachDunkapiModels,explanatoryLabel,candidateIsExploratory}
 from '../assets/js/nba-model.mjs';
const clock=new Date('2026-10-24T16:00:00Z');
const game={sport:'basket',competition_id:'nba',fixture_id:'espn-1'};
const rows=[
 {kind:'prop',label:'Jalen Brunson (Puntos)',line:25.5,side:'over',price:1.95,book:'DraftKings',analysis:{type:'sin_modelo',p:null}},
 {kind:'prop',label:'Jalen Brunson (Puntos)',line:25.5,side:'under',price:1.85,book:'DraftKings',analysis:{type:'sin_modelo',p:null}},
 {kind:'prop',label:'Jalen Brunson (Puntos)',line:26.5,side:'over',price:1.90,book:'DraftKings',analysis:{type:'sin_modelo',p:null}},
 {kind:'prop',label:'Jane Smith (Puntos)',line:25.5,side:'over',price:2.10,book:'DraftKings',analysis:{type:'sin_modelo',p:null}}
];
const snapshot={
 schema:1,generated_at:'2026-10-24T15:50:00Z',
 forecasts:[{
  fixture_id:'espn-1',market_label:'Jalen Brunson (Puntos)',market_line:25.5,
  book:'DraftKings',quote:1.95,p:.6,projected_mean:27,minutes_reference:34,
  sample_size:10,calibrated:false,quote_updated_at:'2026-10-24T15:48:00Z',
  stats_checked_at:'2026-10-24T15:37:00Z',injuries_fresh:true,
  injury_status:null,model:'recent10-normal-heuristic-v1',
  warnings:['Sin minutos confirmados']
 }]
};
test('solo vincula mercado, casa, jugador, line y cuota idénticos',()=>{
 const newRows=attachDunkapiModels(game,rows,snapshot,clock);
 assert.equal(newRows[0].analysis.type,'dunkapi_exploratorio');
 assert.equal(newRows[0].analysis.p,.6);
 assert.equal(newRows[1].analysis.p,null);
 assert.equal(newRows[2].analysis.p,null);
 assert.equal(newRows[3].analysis.p,null);
 assert.ok(explanatoryLabel(newRows[0]).includes('minutos ref. 34'));
 assert.equal(candidateIsExploratory(newRows[0]),true);
});
test('mercado cambiando cuota, evento o datos viejos no se mezcla',()=>{
 let copy=structuredClone(snapshot);copy.forecasts[0].quote=1.99;
 assert.equal(attachDunkapiModels(game,rows,copy,clock)[0].analysis.p,null);
 copy=structuredClone(snapshot);copy.generated_at='2026-10-23T01:00:00Z';
 assert.equal(attachDunkapiModels(game,rows,copy,clock)[0].analysis.p,null);
 copy=structuredClone(snapshot);copy.forecasts[0].stats_checked_at='2026-10-22T01:00:00Z';
 assert.equal(attachDunkapiModels(game,rows,copy,clock)[0].analysis.p,null);
 assert.equal(attachDunkapiModels({...game,fixture_id:'other'},rows,snapshot,clock)[0].analysis.p,null);
});
test('lesiones dudosas y pequeña muestra no se consideran candidato',()=>{
 const copy=structuredClone(snapshot);copy.forecasts[0].injury_status='Questionable';
 const result=attachDunkapiModels(game,rows,copy,clock);
 assert.equal(result[0].analysis.p,.6);
 assert.equal(candidateIsExploratory(result[0]),false);
 copy.forecasts[0].sample_size=5;copy.forecasts[0].injury_status=null;
 assert.equal(candidateIsExploratory(attachDunkapiModels(game,rows,copy,clock)[0]),false);
});
