// 平衡測試：讓自動玩家（tools/bot.js）快轉跑 N 局，看過關率、收攤時間、等級。升級用遊戲內建的「自動挑」。
// 用法：npm i playwright && npx playwright install chromium && node tools/sim.js [局數] [關卡 1-5，不填就五關都跑]
// 圖片放在 assets/，要用 http 開才讀得到，所以這裡先開一個小伺服器。
const path = require('path'), http = require('http'), fs = require('fs');
const { chromium } = require('playwright');
const N = +process.argv[2] || 12, ONLY = +process.argv[3] || 0;
const ROOT = path.join(__dirname, '..');
const TYPES = { '.html':'text/html', '.png':'image/png', '.jpg':'image/jpeg', '.webp':'image/webp', '.js':'text/javascript' };

(async () => {
  const server = http.createServer((req, res) => {
    const url = decodeURIComponent(req.url.split('?')[0]), f = path.join(ROOT, url === '/' ? 'index.html' : url);
    if (!f.startsWith(ROOT) || !fs.existsSync(f)) { res.writeHead(404); return res.end(); }
    res.writeHead(200, { 'Content-Type': TYPES[path.extname(f)] || 'application/octet-stream' }); fs.createReadStream(f).pipe(res);
  }).listen(0);
  const browser = await chromium.launch();
  const page = await (await browser.newContext({ viewport: { width: 390, height: 780 } })).newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto('http://127.0.0.1:' + server.address().port + '/');
  await page.waitForFunction(() => window.__nm && Object.keys(window.__nm.art).length > 0, null, { timeout: 15000 }).catch(() => {});
  await page.addScriptTag({ path: path.join(__dirname, 'bot.js') });
  const count = await page.evaluate(() => window.__nm.stages.length);
  for (const si of ONLY ? [ONLY - 1] : [...Array(count).keys()]) {
    const rows = await page.evaluate(([si, n]) => window.runStage(si, n), [si, N]);
    console.table(rows);
    console.log(await page.evaluate(rows => window.summary(rows), rows));
  }
  if (errors.length) console.log('頁面錯誤：', errors);
  await browser.close(); server.close();
})();
