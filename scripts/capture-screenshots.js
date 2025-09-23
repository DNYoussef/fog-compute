const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

async function captureScreenshots() {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });

  const screenshotsDir = path.join(__dirname, '../screenshots');
  if (!fs.existsSync(screenshotsDir)) {
    fs.mkdirSync(screenshotsDir, { recursive: true });
  }

  try {
    await page.goto('http://localhost:3001', { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);

    await page.screenshot({
      path: path.join(screenshotsDir, 'control-panel-overview.png'),
      fullPage: false
    });
    console.log('Captured: control-panel-overview.png');

    const topologyExists = await page.locator('[data-testid="betanet-topology"]').count() > 0;
    if (topologyExists) {
      await page.locator('[data-testid="betanet-topology"]').screenshot({
        path: path.join(screenshotsDir, 'network-topology.png')
      });
      console.log('Captured: network-topology.png');
    }

    const bitcohatExists = await page.locator('[data-testid="bitchat-interface"]').count() > 0;
    if (bitcohatExists) {
      await page.locator('[data-testid="bitchat-interface"]').screenshot({
        path: path.join(screenshotsDir, 'bitchat-messaging.png')
      });
      console.log('Captured: bitchat-messaging.png');
    }

    const benchmarksExists = await page.locator('[data-testid="benchmark-charts"]').count() > 0;
    if (benchmarksExists) {
      await page.locator('[data-testid="benchmark-charts"]').screenshot({
        path: path.join(screenshotsDir, 'performance-benchmarks.png')
      });
      console.log('Captured: performance-benchmarks.png');
    }

    await page.screenshot({
      path: path.join(screenshotsDir, 'control-panel-fullpage.png'),
      fullPage: true
    });
    console.log('Captured: control-panel-fullpage.png');

    console.log('All Fog-Compute screenshots captured successfully!');
  } catch (error) {
    console.error('Error capturing screenshots:', error.message);
    process.exit(1);
  } finally {
    await browser.close();
  }
}

captureScreenshots();