"use strict";
(() => {
  const $ = id => document.getElementById(id);
  const level = $("level"), value = $("value"), trend = $("trend"), updated = $("updated");
  if (!level || !value || !trend || !updated || !level.querySelector(".level-label")) return;
  const label = level.querySelector(".level-label");
  let busy = false;
  function reset(message) {
    level.className = "level level-unknown"; label.textContent = "確認中";
    value.textContent = "--"; trend.textContent = message; updated.textContent = "対象週：確認中";
  }
  function classify(n) {
    // 京王笹塚版の表示区分を踏襲。公式の注意報・警報発令を示すものではない。
    if (n >= 30) return ["警報レベル", "level-alert"];
    if (n >= 10) return ["注意報レベル", "level-warning"];
    if (n >= 1) return ["流行中", "level-spread"];
    return ["非流行", "level-normal"];
  }
  async function load() {
    if (busy) return; busy = true;
    try {
      const res = await fetch("data/status.json?t=" + Date.now(), {cache:"no-store"});
      if (!res.ok) throw Error("HTTP " + res.status);
      const d = await res.json();
      if (d.region !== "横浜市" || d.metric !== "定点当たり報告数" || d.year !== 2026 ||
          !Number.isInteger(d.week) || d.week < 1 || d.week > 53 ||
          typeof d.perSentinel !== "number" || !Number.isFinite(d.perSentinel) || d.perSentinel < 0 || d.perSentinel > 10000)
        throw Error("データ不正");
      const now = new Date(new Date().toLocaleString("en-US", {timeZone:"Asia/Tokyo"}));
      const end = new Date(Date.UTC(d.year, 0, 4));
      end.setUTCDate(end.getUTCDate() - (end.getUTCDay() || 7) + 7 + (d.week - 1) * 7);
      const age = (Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()) - end.getTime()) / 86400000;
      if (age < 0 || age > 21) throw Error("対象週が未終了または古い");
      const [text, css] = classify(d.perSentinel);
      level.className = "level " + css; label.textContent = text;
      value.textContent = d.perSentinel.toFixed(2);
      // 旧JSONには前週差がない。再実行後に同じCSVの前週値を検証して表示。
      const p = d.previousPerSentinel;
      if (typeof p === "number" && Number.isFinite(p) && p >= 0 && d.week > 1) {
        const diff = Math.round((d.perSentinel - p) * 100) / 100;
        const verified = typeof d.difference === "number" && Number.isFinite(d.difference) && Math.abs(d.difference - diff) < 0.011;
        trend.textContent = verified ? `先週比 ${diff > 0 ? "+" : diff < 0 ? "" : "±"}${diff.toFixed(2)}人（前週 ${p.toFixed(2)}人）` : "先週比：確認中";
      } else trend.textContent = "先週比：データなし";
      updated.textContent = `対象週：${d.year}年第${d.week}週`;
    } catch (error) { console.error(error); reset("最新の公表値を確認できません"); }
    finally { busy = false; }
  }
  load(); const timer = setInterval(load, 600000);
  window.addEventListener("pagehide", () => clearInterval(timer), {once:true});
})();
