(() => {
  'use strict';

  const DATA_URL = 'data/status.json';
  const REFRESH_INTERVAL_MS = 10 * 60 * 1000;
  const CACHE_KEY = 'tsurugamine-infection-status-v2';

  const byId = (id) => document.getElementById(id);
  const isFiniteNumber = (value) => typeof value === 'number' && Number.isFinite(value);
  const formatNumber = (value) => isFiniteNumber(value)
    ? value.toFixed(2).replace(/\.00$/, '')
    : '--';

  function classify(value) {
    if (!isFiniteNumber(value)) return { key: 'unknown', label: '確認中' };
    if (value >= 30) return { key: 'warning', label: '警報レベル' };
    if (value >= 10) return { key: 'advisory', label: '注意報レベル' };
    if (value >= 1) return { key: 'epidemic', label: '流行中' };
    return { key: 'normal', label: '非流行' };
  }

  function normalizeItem(item) {
    if (!item || typeof item !== 'object') return null;
    return {
      week: Number(item.week),
      value: Number(item.value),
      previousValue: item.previousValue == null ? null : Number(item.previousValue),
      change: item.change == null ? null : Number(item.change)
    };
  }

  function validateStatus(data) {
    if (!data || typeof data !== 'object') throw new Error('status.json is not an object');
    const influenza = normalizeItem(data.influenza);
    const covid19 = normalizeItem(data.covid19);
    if (!influenza || !covid19) throw new Error('required disease data is missing');
    if (!isFiniteNumber(influenza.value) || !isFiniteNumber(covid19.value)) {
      throw new Error('disease values are invalid');
    }
    return { ...data, influenza, covid19 };
  }

  function trendMarkup(item) {
    if (!isFiniteNumber(item.previousValue) || !isFiniteNumber(item.change)) {
      return '前週比較 --';
    }

    let arrow = '→';
    let arrowClass = 'steady';
    if (item.change > 0) {
      arrow = '↑';
      arrowClass = 'increase';
    } else if (item.change < 0) {
      arrow = '↓';
      arrowClass = 'decrease';
    }

    const sign = item.change > 0 ? '+' : '';
    return `前週 ${formatNumber(item.previousValue)} <span class="trend-arrow ${arrowClass}" aria-label="${arrowClass === 'increase' ? '増加' : arrowClass === 'decrease' ? '減少' : '維持'}">${arrow}</span> ${sign}${formatNumber(item.change)}`;
  }

  function renderDisease(prefix, item) {
    const card = byId(`${prefix}Card`);
    const level = classify(item.value);

    byId(`${prefix}Value`).textContent = formatNumber(item.value);
    byId(`${prefix}Level`).textContent = level.label;
    byId(`${prefix}Trend`).innerHTML = trendMarkup(item);
    byId(`${prefix}Week`).textContent = Number.isInteger(item.week) ? `第${item.week}週` : '--';

    card.classList.remove(
      'level-warning', 'level-advisory', 'level-epidemic', 'level-normal', 'level-unknown'
    );
    card.classList.add(`level-${level.key}`);
  }

  function render(data, sourceLabel) {
    renderDisease('influenza', data.influenza);
    renderDisease('covid19', data.covid19);
    if (typeof data.area === 'string' && data.area.trim()) {
      byId('area').textContent = data.area;
    }
    if (typeof data.unit === 'string' && data.unit.trim()) {
      byId('unit').textContent = data.unit;
    }
    byId('dataStatus').textContent = sourceLabel;
  }

  function saveCache(data) {
    try {
      localStorage.setItem(CACHE_KEY, JSON.stringify({ savedAt: Date.now(), data }));
    } catch (error) {
      console.warn('cache save failed', error);
    }
  }

  function loadCache() {
    try {
      const raw = localStorage.getItem(CACHE_KEY);
      if (!raw) return null;
      const cached = JSON.parse(raw);
      return validateStatus(cached.data);
    } catch (error) {
      console.warn('cache load failed', error);
      return null;
    }
  }

  async function update() {
    try {
      const response = await fetch(`${DATA_URL}?t=${Date.now()}`, { cache: 'no-store' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = validateStatus(await response.json());
      render(data, 'データ更新済み');
      saveCache(data);
    } catch (error) {
      console.error('status update failed', error);
      const cached = loadCache();
      if (cached) {
        render(cached, '通信失敗：直近データを表示中');
      } else {
        byId('dataStatus').textContent = 'データ取得失敗';
      }
    }
  }

  update();
  window.setInterval(update, REFRESH_INTERVAL_MS);
})();
