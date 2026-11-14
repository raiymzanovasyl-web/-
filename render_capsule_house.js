// Рендер чертежа в PDF (A2) и PNG: node render_capsule_house.js
const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const svg = path.join(__dirname, 'output', 'capsule_house.svg');
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 2245, height: 1587 }, deviceScaleFactor: 2 });
  await page.goto('file://' + svg);
  await page.pdf({ path: path.join(__dirname, 'output', 'capsule_house.pdf'), width: '594mm', height: '420mm',
                   printBackground: true, pageRanges: '1' });
  await page.screenshot({ path: path.join(__dirname, 'output', 'capsule_house.png'), clip: { x: 0, y: 0, width: 2245, height: 1587 } });
  await browser.close();
})();
