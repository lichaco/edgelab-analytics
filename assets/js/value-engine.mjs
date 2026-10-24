import {poissonPMF} from './football-model.mjs';

// Cada selección se compara exclusivamente con el MISMO mercado y línea.
export function sameLine(a,b){
 return a?.kind===b?.kind && a?.line===b?.line &&
        (a?.kind!=='prop'||a?.label===b?.label);
}

export function modelProbability(market, side, rates, predictions){
 if(!rates||!predictions) return null;
 if(market.kind==='result'){
  // Sin empate publicado, podría ser Draw No Bet: no aplicar el 1X2.
  if(!market.selections?.draw)return null;
  if(!['home','draw','away'].includes(side))return null;
  return predictions.oneXTwo?.[side]??null;
 }
 if(market.kind==='goals' && ['over','under'].includes(side)){
  const line=Number(market.line);
  if(!(line>=.5&&line<=8.5) || Math.abs(line-Math.floor(line)-.5)>1e-7)return null;
  const dist=poissonPMF(rates.home+rates.away);
  const under=dist.slice(0,Math.floor(line)+1).reduce((s,x)=>s+x,0);
  return side==='under'?under:1-under;
 }
 return null; // Tarjetas/córners requieren modelos estadísticos independientes.
}

export function fairMarketProbability(market,side){
 const required=market?.kind==='result'&&market?.selections?.draw
   ? ['home','draw','away'] : market?.kind==='result'||market?.kind==='spread'
   ? ['home','away'] : ['over','under'];
 if(!required.includes(side))return null;
 if(!required.every(k=>Number.isFinite(market?.selections?.[k])&&market.selections[k]>1))return null;
 const hold=required.reduce((s,k)=>s+1/market.selections[k],0);
 return (1/market.selections[side])/hold;
}

export function assessQuote(market,side,price,otherMarket,rates,predictions){
 if(!Number.isFinite(price)||price<=1)return null;
 let p=modelProbability(market,side,rates,predictions),method='modelo';
 if(!(p>0&&p<1)){
  p=null;
  if(otherMarket&&sameLine(market,otherMarket)){
   p=fairMarketProbability(otherMarket,side);
   method='comparación entre casas';
  }
 }
 if(!(p>0&&p<1))return {type:'sin_modelo',p:null,ev:null,fair:null};
 return {type:method,p,ev:p*price-1,fair:1/p,edge:p-1/price};
}

export function reportForEvent(event,fixture,history,modelFunctions){
 let rates=null,predictions=null;
 if(event.sport==='football' && Array.isArray(history)&&history.length>=55){
  try {
   rates=modelFunctions.estimateLambdas(history,fixture.home,fixture.away,fixture.date||fixture.utc.slice(0,10));
   if(rates)predictions=modelFunctions.predictMarkets(rates.home,rates.away);
  } catch(_error){/* no falsificar probabilidad */ }
 }
 const all=[];
 for(const [book,markets] of Object.entries(event.books||{})){
  const others=Object.entries(event.books||{}).filter(([other])=>other!==book);
  for(const m of markets){
   if(!m||!m.selections)continue;
   const alt=others.flatMap(([,ms])=>ms).find(x=>sameLine(x,m));
   for(const [side,quote] of Object.entries(m.selections)){
    if(!(quote>1))continue;
    const analysis=assessQuote(m,side,quote,alt,rates,predictions);
    all.push({book,kind:m.kind,line:m.line,label:m.label||'',side,price:quote,
       updated_at:m.updated_at||null,source:m.source||event.source||null,analysis});
   }
  }
 }
 return {rows:all,rates};
}
