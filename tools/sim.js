// 平衡測試：讓自動玩家快轉跑 N 局，看過關率、收攤時間、等級。升級用遊戲內建的「自動挑」。
// 用法：npm i playwright && npx playwright install chromium && node tools/sim.js [局數] [關卡 1-3，不填就三關都跑]
// 圖片放在 assets/，要用 http 開才讀得到，所以這裡先開一個小伺服器。
const path = require('path'), http = require('http'), fs = require('fs');
const { chromium } = require('playwright');
const N = +process.argv[2] || 12, ONLY = +process.argv[3] || 0;
const ROOT = path.join(__dirname, '..');
const TYPES = { '.html':'text/html', '.png':'image/png', '.jpg':'image/jpeg', '.js':'text/javascript' };

// 躲開附近的客人和竹籤，順便往最近的錢靠；任務會在打怪、撿錢時自然完成
function runStage(si, n) {
  const nm = window.__nm, out = [];
  const bot = () => {
    const g = nm.g; let fx = 0, fy = 0;
    for (const e of g.enemies) { const dx = g.px - e.x, dy = g.py - e.y, d2 = dx * dx + dy * dy + 1; if (d2 < 180 * 180) { const w = e.r / d2; fx += dx * w; fy += dy * w; } }
    for (const s of g.shots) { const dx = g.px - s.x, dy = g.py - s.y, d2 = dx * dx + dy * dy + 1; if (d2 < 120 * 120) { const w = 14 / d2; fx += dx * w; fy += dy * w; } }
    let best = null, bd = 1e12;
    for (const c of g.coins) { const d = (c.x - g.px) ** 2 + (c.y - g.py) ** 2; if (d < bd) { bd = d; best = c; } }
    if (best) { const d = Math.sqrt(bd) || 1; fx += (best.x - g.px) / d * 0.01; fy += (best.y - g.py) / d * 0.01; }
    const m = Math.hypot(fx, fy); nm.input.on = true; nm.input.x = m ? fx / m : 0; nm.input.y = m ? fy / m : 0;
  };
  for (let r = 0; r < n; r++) {
    nm.start(si); let guard = 0;
    while (nm.state === 'play' && guard++ < 30 * 900) { bot(); nm.step(1 / 30); }
    const g = nm.g;
    out.push({ 關卡: si + 1, 結果: nm.state === 'win' ? '收攤' : '陣亡', 秒數: Math.round(g.t), 等級: g.lvl, 擊退: g.kills,
               任務: g.qdone.filter(Boolean).length + '/' + g.qdone.length, 營業額: g.money });
  }
  nm.input.on = false;
  return out;
}

(async () => {
  const server = http.createServer((req, res) => {
    const f = path.join(ROOT, decodeURIComponent(req.url.split('?')[0]) === '/' ? 'index.html' : decodeURIComponent(req.url.split('?')[0]));
    if (!f.startsWith(ROOT) || !fs.existsSync(f)) { res.writeHead(404); return res.end(); }
    res.writeHead(200, { 'Content-Type': TYPES[path.extname(f)] || 'application/octet-stream' }); fs.createReadStream(f).pipe(res);
  }).listen(0);
  const browser = await chromium.launch();
  const page = await (await browser.newContext({ viewport: { width: 390, height: 780 } })).newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto('http://127.0.0.1:' + server.address().port + '/');
  await page.waitForFunction(() => window.__nm && Object.keys(window.__nm.art).length > 0, null, { timeout: 15000 }).catch(() => {});
  for (const si of ONLY ? [ONLY - 1] : [0, 1, 2]) {
    const runs = await page.evaluate(runStage.toString().replace(/^function runStage/, '(function') + ')(' + si + ',' + N + ')');
    console.table(runs);
    const wins = runs.filter(r => r.結果 === '收攤'), ts = wins.map(r => r.秒數).sort((a, b) => a - b);
    console.log(`第 ${si + 1} 關：過關 ${wins.length}/${runs.length}` + (ts.length ? `，收攤時間中位數 ${ts[ts.length >> 1]} 秒` : ''));
  }
  if (errors.length) console.log('頁面錯誤：', errors);
  await browser.close(); server.close();
})();
