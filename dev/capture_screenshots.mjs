#!/usr/bin/env node
/** Capture dashboard screenshots for README. Requires `poetry run frontend`. */
import { chromium } from 'playwright';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const OUT = path.join(ROOT, 'docs', 'screenshots');
const BASE = process.env.FRONTEND_URL || 'http://127.0.0.1:8787';

const SHOTS = [
  { file: 'overview.png', route: 'overview', wait: 2500 },
  { file: 'sybil-signals.png', route: 'sybil', wait: 1200 },
  { file: 'agent-dossier.png', route: 'dossier', params: { agent: 22721 }, wait: 2500 },
  { file: 'reviewer-lens.png', route: 'reviewer', wait: 2000 },
  { file: 'identity-graph.png', route: 'identity', wait: 2000 },
  { file: 'explorer.png', route: 'explorer', wait: 1200 },
  { file: 'corpus.png', route: 'corpus', wait: 1200 },
];

async function waitForApp(page) {
  await page.goto(BASE, { waitUntil: 'networkidle', timeout: 120_000 });
  await page.waitForSelector('.app', { timeout: 120_000 });
  await page.waitForFunction(() => window.AX && window.AX.agents && window.AX.agents.length > 0, {
    timeout: 120_000,
  });
}

async function navTo(page, route, params) {
  await page.evaluate(
    ({ route, params }) => {
      window.AXNAV(route, params || null);
    },
    { route, params: params || null },
  );
  await page.waitForTimeout(400);
}

async function main() {
  await mkdir(OUT, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
  });
  const page = await context.newPage();

  console.log(`Loading ${BASE}…`);
  await waitForApp(page);

  for (const shot of SHOTS) {
    console.log(`→ ${shot.file}`);
    await navTo(page, shot.route, shot.params);
    await page.waitForTimeout(shot.wait);
    await page.screenshot({
      path: path.join(OUT, shot.file),
      fullPage: false,
    });
  }

  await browser.close();
  console.log(`Saved ${SHOTS.length} screenshots to docs/screenshots/`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
