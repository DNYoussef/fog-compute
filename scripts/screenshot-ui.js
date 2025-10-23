const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

async function captureScreenshots() {
  console.log('🚀 Launching Chromium browser...');

  // Launch browser with visible window (headless: false)
  const browser = await chromium.launch({
    headless: false,  // Show the browser window
    slowMo: 1000      // Slow down by 1 second to see what's happening
  });

  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: 1
  });

  const page = await context.newPage();

  // Create screenshots directory if it doesn't exist
  const screenshotsDir = path.join(__dirname, '..', 'screenshots');
  if (!fs.existsSync(screenshotsDir)) {
    fs.mkdirSync(screenshotsDir, { recursive: true });
  }

  // Pages to capture
  const pages = [
    { url: 'http://localhost:3000', name: 'dashboard', title: 'Dashboard' },
    { url: 'http://localhost:3000/betanet', name: 'betanet', title: 'BetaNet' },
    { url: 'http://localhost:3000/bitchat', name: 'bitchat', title: 'BitChat' },
    { url: 'http://localhost:3000/benchmarks', name: 'benchmarks', title: 'Benchmarks' },
    { url: 'http://localhost:3000/quality', name: 'quality', title: 'Quality Dashboard' }
  ];

  console.log(`\n📸 Capturing ${pages.length} screenshots...\n`);

  for (const pageInfo of pages) {
    try {
      console.log(`   → Opening ${pageInfo.title} (${pageInfo.url})...`);

      // Navigate to page
      await page.goto(pageInfo.url, { waitUntil: 'networkidle' });

      // Wait a bit for any animations/data loading
      await page.waitForTimeout(2000);

      // Take screenshot
      const screenshotPath = path.join(screenshotsDir, `${pageInfo.name}.png`);
      await page.screenshot({ path: screenshotPath, fullPage: false });

      console.log(`   ✓ Saved ${pageInfo.name}.png`);

    } catch (error) {
      console.error(`   ✗ Error capturing ${pageInfo.title}:`, error.message);
    }
  }

  console.log('\n✅ All screenshots captured!');
  console.log(`📁 Screenshots saved to: ${screenshotsDir}\n`);

  // Keep browser open for 3 seconds so user can see final page
  console.log('Keeping browser open for 3 seconds...');
  await page.waitForTimeout(3000);

  await browser.close();
  console.log('🎉 Done!');
}

// Run the script
captureScreenshots().catch(console.error);
