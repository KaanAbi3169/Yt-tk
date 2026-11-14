// Rendert SVG-Dateien mit Chromium (Playwright) zu PNG.
// Aufruf: node tools/svg2png.js <jobs.json>
// jobs.json: [{"svg": "/pfad/in.svg", "png": "/pfad/out.png", "width": 1080, "height": 1920, "transparent": false}]
const fs = require('fs');
let chromium;
try { ({ chromium } = require('playwright')); }
catch (e) { ({ chromium } = require('/opt/node-tools/node_modules/playwright')); }

(async () => {
  const jobs = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const browser = await chromium.launch();
  const page = await browser.newPage();
  for (const j of jobs) {
    await page.setViewportSize({ width: j.width, height: j.height });
    const svg = fs.readFileSync(j.svg, 'utf8');
    const bg = j.transparent ? 'transparent' : '#000';
    await page.setContent(`<!doctype html><html><head><meta charset="utf-8"><style>
      html,body{margin:0;padding:0;background:${bg};overflow:hidden}
      svg{display:block;width:${j.width}px;height:${j.height}px}
    </style></head><body>${svg}</body></html>`, { waitUntil: 'load' });
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({ path: j.png, omitBackground: !!j.transparent,
      clip: { x: 0, y: 0, width: j.width, height: j.height } });
  }
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
