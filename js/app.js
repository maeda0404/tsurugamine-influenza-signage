(() => {
  "use strict";
  const config = window.SIGNAGE_CONFIG || {};
  let timerId = null;
  const $ = (id) => document.getElementById(id);
  const els = {level:$("level"), value:$("value"), unit:$("unit"), label:$("metricLabel"), trend:$("trend"), updated:$("updated"), state:$("dataState")};
  const allowedLevels = {alert:["level-alert","警報"],warning:["level-warning","注意報"],watch:["level-watch","注意"],normal:["level-normal","平常"],unknown:["level-unknown","確認中"]};
  function safeText(v,fallback){return (typeof v === "string" || typeof v === "number") && String(v).trim() ? String(v) : fallback;}
  function setLevel(key,label){const k=allowedLevels[key]?key:"unknown";els.level.className="level "+allowedLevels[k][0];els.level.querySelector(".level-label").textContent=safeText(label,allowedLevels[k][1]);}
  function validData(d){return d && typeof d==="object" && !Array.isArray(d);}
  function render(d){
    if(!validData(d)) throw new Error("Invalid data");
    setLevel(d.levelKey,d.levelLabel);
    els.value.textContent=safeText(d.value,"--");
    els.unit.textContent=safeText(d.unit,"人");
    els.label.textContent=safeText(d.metricLabel,"定点当たり報告数");
    els.trend.textContent=safeText(d.trend,"傾向：確認中");
    els.updated.textContent="最終更新："+safeText(d.updatedAt,"確認中");
    els.state.textContent=safeText(d.note,"");
  }
  function showError(){setLevel("unknown",config.fallbackTitle||"データ確認中");els.trend.textContent="最新情報を取得できません";els.state.textContent="画面の感染対策情報は引き続き利用できます";}
  async function load(){try{const res=await fetch((config.dataUrl||"data/content.json")+"?t="+Date.now(),{cache:"no-store"});if(!res.ok)throw new Error("HTTP "+res.status);render(await res.json());}catch(e){console.error(e);showError();}}
  function start(){load();const min=Number(config.refreshMinutes);if(Number.isFinite(min)&&min>0){timerId=setInterval(load,min*60000);}}
  window.addEventListener("beforeunload",()=>{if(timerId)clearInterval(timerId);},{once:true});
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",start,{once:true});else start();
})();
