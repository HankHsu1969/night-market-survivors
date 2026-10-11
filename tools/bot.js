// 自動玩家：在遊戲頁面裡執行，透過 window.__nm 快轉。tools/sim.js 會載入這個檔案；
// 在瀏覽器裡測試時，也可以用 <script src="tools/bot.js"> 載入後呼叫 runStage(關卡索引, 局數)。
// 它只會躲開附近的客人和飛過來的東西，順便往最近的錢靠；任務會在打怪、撿錢時自然完成。
window.runStage = function (si, n, cap) {
  const nm = window.__nm, out = [];
  const steer = g => {
    let fx = 0, fy = 0;
    for (const e of g.enemies) { const dx = g.px - e.x, dy = g.py - e.y, d2 = dx * dx + dy * dy + 1; if (d2 < 180 * 180) { const w = e.r / d2; fx += dx * w; fy += dy * w; } }
    for (const s of g.shots) { const dx = g.px - s.x, dy = g.py - s.y, d2 = dx * dx + dy * dy + 1; if (d2 < 120 * 120) { const w = 14 / d2; fx += dx * w; fy += dy * w; } }
    let best = null, bd = 1e12;
    for (const c of g.coins) { const d = (c.x - g.px) ** 2 + (c.y - g.py) ** 2; if (d < bd) { bd = d; best = c; } }
    if (best) { const d = Math.sqrt(bd) || 1; fx += (best.x - g.px) / d * 0.01; fy += (best.y - g.py) / d * 0.01; }
    const m = Math.hypot(fx, fy); nm.input.on = true; nm.input.x = m ? fx / m : 0; nm.input.y = m ? fy / m : 0;
  };
  for (let r = 0; r < n; r++) {
    nm.start(si); let guard = 0, bossAt = 0;
    while (nm.state === 'play' && guard++ < 30 * (cap || 900)) {
      steer(nm.g); nm.step(1 / 30);
      if (nm.g.bossOn && !bossAt) bossAt = nm.g.t;
    }
    const g = nm.g;
    out.push({ 關卡: si + 1, 結果: nm.state === 'win' ? '收攤' : nm.state === 'over' ? '陣亡' : '超時', 秒數: Math.round(g.t), 等級: g.lvl, 擊退: g.kills,
               任務: g.qdone.filter(Boolean).length + '/' + g.qdone.length, 魔王戰: bossAt ? Math.round(g.t - bossAt) : '',
               武器: Object.keys(g.it).filter(k => g.it[k] && ['pearl', 'sausage', 'cutlet', 'qq', 'ice', 'tofu'].includes(k)).map(k => k + g.it[k]).join(' ') });
  }
  nm.input.on = false;
  try { localStorage.removeItem('nm.save'); } catch (e) {}   // tests must not unlock stages for the real player
  return out;
};
window.summary = function (rows) {
  const w = rows.filter(r => r.結果 === '收攤'), ts = w.map(r => r.秒數).sort((a, b) => a - b);
  return `第 ${rows[0].關卡} 關：過關 ${w.length}/${rows.length}` + (ts.length ? `，收攤時間中位數 ${ts[ts.length >> 1]} 秒` : '');
};
