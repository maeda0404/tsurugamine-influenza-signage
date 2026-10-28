(() => {
  'use strict';

  const DATA_URL = './data/status.json';
  const REFRESH_MS = 10 * 60 * 1000;
  const CACHE_KEY = 'tsurugamine_infection_last';

  const $ = (id) => document.getElementById(id);
  const setText = (id, value) => {
    const el = $(id);
    if (el) el.textContent = value;
  };

  const isNumber = (v) => typeof v === 'number' && Number.isFinite(v);
  const fmt = (v) => isNumber(v) ? v.toFixed(2).replace(/\.00$/, '') : '--';

  function saveCache(data) {
    try { localStorage.setItem(CACHE_KEY, JSON.stringify(data)); } catch (_) {}
  }

  function loadCache() {
    try {
      const raw = localStorage.getItem(CACHE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (_) { return null; }
  }

  function normalizeDisease(item, fallback) {
    if (!item || typeof item !== 'object') return null;
    return {
      label: item.label || fallback,
      week: Number.isInteger(item.week) ? item.week : null,
      value: Number(item.value),
      previousWeek: Number.isInteger(item.previousWeek) ? item.previousWeek : null,
      previousValue: item.previousValue == null ? null : Number(item.previousValue),
      change: item.change == null ? null : Number(item.change),
      sourceUrl: typeof item.sourceUrl === 'string' ? item.sourceUrl : '',
      publishedDate: typeof item.publishedDate === 'string' ? item.publishedDate : ''
    };
  }

  function validate(data) {
    if (!data || typeof data !== 'object') throw new Error('invalid JSON');
    const influenza = normalizeDisease(data.influenza || {
      label: 'インフルエンザ', week: data.week, value: data.value,
      previousValue: data.previousValue, change: data.change,
      sourceUrl: data.sourceUrl
    }, 'インフルエンザ');
    const covid19 = normalizeDisease(data.covid19, '新型コロナ');
    if (!influenza || !isNumber(influenza.value)) throw new Error('influenza missing');
    if (!covid19 || !isNumber(covid19.value)) throw new Error('covid19 missing');
    return { ...data, influenza, covid19 };
  }

  function trendText(item) {
    if (!isNumber(item.previousValue) || !isNumber(item.change)) return '前週比較 --';
    const sign = item.change > 0 ? '+' : '';
    const arrow = item.change > 0 ? '↑' : item.change < 0 ? '↓' : '→';
    return `前週 ${fmt(item.previousValue)} ${arrow} ${sign}${fmt(item.change)}`;
  }

  function renderDisease(prefix, item) {
    setText(`${prefix}Value`, fmt(item.value));
    setText(`${prefix}Week`, item.week ? `第${item.week}週` : '--');
    setText(`${prefix}Trend`, trendText(item));
    setText(`${prefix}Published`, item.publishedDate || '--');

    const link = $(`${prefix}Source`);
    if (link && item.sourceUrl) {
      link.href = item.sourceUrl;
      link.hidden = false;
    }
  }

  function render(data, cached = false) {
    renderDisease('influenza', data.influenza);
    renderDisease('covid19', data.covid19);

    // Compatibility with the current single-card HTML.
    setText('value', fmt(data.influenza.value));
    setText('week', data.influenza.week ? `第${data.influenza.week}週` : '--');
    setText('trend', trendText(data.influenza));
    setText('updated', data.updatedAt || data.influenza.publishedDate || '--');

    setText('area', data.area || '横浜市');
    setText('unit', data.unit || '定点当たり報告数');
    setText('dataStatus', cached ? '最新取得に失敗：直近データを表示中' : 'データ更新済み');

    document.documentElement.dataset.dataState = cached ? 'cached' : 'current';
  }

  function showError() {
    setText('dataStatus', '最新データを取得できません');
    document.documentElement.dataset.dataState = 'error';
  }

  async function load() {
    try {
      const response = await fetch(`${DATA_URL}?t=${Date.now()}`, { cache: 'no-store' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = validate(await response.json());
      saveCache(data);
      render(data, false);
    } catch (error) {
      console.error('感染症データ取得失敗', error);
      const cached = loadCache();
      if (cached) {
        try { render(validate(cached), true); return; } catch (_) {}
      }
      showError();
    }
  }

  load();
  setInterval(load, REFRESH_MS);
})();
