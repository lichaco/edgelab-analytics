import test from 'node:test';
import assert from 'node:assert/strict';
import {attachDunkapiModels,attachOfficialNbaModels,candidateIsExploratory,explanatoryLabel}
 from '../assets/js/nba-model.mjs';

const time=new Date('2026-10-24T17:00:00Z');
const event={sport:'basket',competition_id:'nba',fixture_id:'espn-nba-1'};
const rows=[
 {kind:'prop',label:'Jalen Brunson (Puntos)',line:25.5,side:'over',price:1.93,
  book:'DraftKings',source:'The Odds API',analysis:{type:'sin_modelo',p:null}},
 {kind:'prop',label:'Jalen Brunson (Triples)',line:2.5,side:'over',price:2.10,
  book:'DraftKings',source:'The Odds API',analysis:{type:'sin_modelo',p:null}},
 {kind:'prop',label:'Jalen Brunson (Puntos)',line:25.5,side:'under',price:1.95,
  book:'DraftKings',source:'The Odds API',analysis:{type:'sin_modelo',p:null}}
];
function snap(provider,p){
 return {schema:1,generated_at:'2026-10-24T16:55:00Z',
  forecasts:[{
   fixture_id:'espn-nba-1',market_label:'Jalen Brunson (Puntos)',market_line:25.5,
   book:'DraftKings',quote:1.93,p,projected_mean:27.3,minutes_reference:34,
   sample_size:8,calibrated:false,quote_updated_at:'2026-10-24T16:55:00Z',
   stats_checked_at:'2026-10-24T16:57:00Z',injuries_fresh:false,
   injury_status:null,model:provider,
   warnings:['No hay informe de lesiones validado']
  }]
 };
}
test('NBA oficial tiene precedencia sobre DunkAPI para exactamente la misma línea',()=>{
 const official=attachOfficialNbaModels(event,rows,snap('nba-cdn',.61),time);
 const both=attachDunkapiModels(event,official,snap('dunkapi',.44),time);
 assert.equal(both[0].analysis.type,'nba_oficial_exploratorio');
 assert.equal(both[0].analysis.p,.61);
 assert.equal(both[1].analysis.p,null);
 assert.equal(both[2].analysis.p,null);
 assert.ok(explanatoryLabel(both[0]).includes('NBA oficial'));
 assert.equal(candidateIsExploratory(both[0]),false);
});
test('DunkAPI se usa si NBA oficial no tiene datos suficientes',()=>{
 const official=attachOfficialNbaModels(event,rows,{schema:1,generated_at:'2026-10-24T16:55:00Z',forecasts:[]},time);
 const fallback=attachDunkapiModels(event,official,snap('dunkapi',.55),time);
 assert.equal(fallback[0].analysis.type,'dunkapi_exploratorio');
 assert.equal(fallback[0].analysis.p,.55);
});
test('Cuota o snapshot desactualizado no produce análisis NBA',()=>{
 const outdated=snap('nba-cdn',.61);
 outdated.forecasts[0].quote=2.2;
 assert.equal(attachOfficialNbaModels(event,rows,outdated,time)[0].analysis.p,null);
 outdated.forecasts[0].quote=1.93;
 outdated.generated_at='2026-10-23T12:00:00Z';
 assert.equal(attachOfficialNbaModels(event,rows,outdated,time)[0].analysis.p,null);
});
