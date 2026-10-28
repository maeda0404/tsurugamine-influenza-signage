(() => {
  'use strict';
  const DATA_URL='./data/status.json';
  const REFRESH_MS=10*60*1000;
  const $=id=>document.getElementById(id);
  const setText=(id,v)=>{const e=$(id); if(e)e.textContent=v;};
  const n=v=>typeof v==='number'&&Number.isFinite(v);
  const fmt=v=>n(v)?v.toFixed(2).replace(/\.00$/,''):'--';

  // Approved legacy influenza thresholds: >=30 warning, >=10 advisory, >=1 epidemic, <1 non-epidemic.
  function influenzaLevel(v){
    if(!n(v)) return {key:'unknown',label:'確認中'};
    if(v>=30) return {key:'warning',label:'警報レベル'};
    if(v>=10) return {key:'advisory',label:'注意報レベル'};
    if(v>=1) return {key:'epidemic',label:'流行中'};
    return {key:'normal',label:'非流行'};
  }

  // User-selected display rule: apply the same 4-step thresholds to COVID-19.
  function covidLevel(v){
    if(!n(v)) return {key:'unknown',label:'確認中'};
    if(v>=30) return {key:'warning',label:'警報レベル'};
    if(v>=10) return {key:'advisory',label:'注意報レベル'};
    if(v>=1) return {key:'epidemic',label:'流行中'};
    return {key:'normal',label:'非流行'};
  }

  function normalize(item,label){
    if(!item||typeof item!=='object')return null;
    return {label:item.label||label,week:Number(item.week),value:Number(item.value),previousValue:item.previousValue==null?null:Number(item.previousValue),change:item.change==null?null:Number(item.change),sourceUrl:item.sourceUrl||'',publishedDate:item.publishedDate||''};
  }
  function trend(item){
    if(!n(item.previousValue)||!n(item.change))return '前週比較 --';
    const a=item.change>0?'↑':item.change<0?'↓':'→';
    const s=item.change>0?'+':'';
    return `前週 ${fmt(item.previousValue)} ${a} ${s}${fmt(item.change)}`;
  }
  function renderCard(prefix,item,state){
    setText(prefix+'Value',fmt(item.value)); setText(prefix+'Week',Number.isInteger(item.week)?`第${item.week}週`:'--'); setText(prefix+'Trend',trend(item)); setText(prefix+'Published',item.publishedDate||'--'); setText(prefix+'Level',state.label);
    const card=$(prefix+'Card'); if(card){card.dataset.level=state.key; card.classList.remove('level-warning','level-advisory','level-epidemic','level-normal','level-increase','level-decrease','level-same','level-neutral','level-unknown'); card.classList.add('level-'+state.key);}
    const link=$(prefix+'Source'); if(link&&item.sourceUrl){link.href=item.sourceUrl;link.hidden=false;}
  }
  async function load(){
    try{
      const r=await fetch(`${DATA_URL}?t=${Date.now()}`,{cache:'no-store'}); if(!r.ok)throw new Error(`HTTP ${r.status}`); const d=await r.json();
      const flu=normalize(d.influenza,'インフルエンザ'); const covid=normalize(d.covid19,'新型コロナ'); if(!flu||!covid||!n(flu.value)||!n(covid.value))throw new Error('invalid status.json');
      renderCard('influenza',flu,influenzaLevel(flu.value)); renderCard('covid19',covid,covidLevel(covid.value)); setText('area',d.area||'横浜市'); setText('unit',d.unit||'定点当たり報告数'); setText('dataStatus','データ更新済み');
    }catch(e){console.error(e);setText('dataStatus','最新データを取得できません');}
  }
  load(); setInterval(load,REFRESH_MS);
})();
