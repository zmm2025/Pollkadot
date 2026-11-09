const { chromium } = require('playwright'); const BASE = process.env.BASE_URL || 'http://localhost:8000';
(async () => {
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1280, height: 900 } }); const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.goto(BASE + '/#2024-pres'); await p.waitForFunction(() => window.pollkadot?.disp && !pollkadot.animating);
  await p.evaluate(() => { window.__ctx = []; window.addEventListener('contextmenu', e => setTimeout(() => __ctx.push(e.defaultPrevented)), false) });
  const modes = [['circ', 'none', 'county'], ['circ', 'land', 'county'], ['place', 'none', 'county'], ['place', 'land', 'county'], ['contig', 'none', 'county'], ['contig', 'land', 'county'], ['contig', 'land', 'state'], ['circ', 'pop', 'state']];
  for (const [m, c, g] of modes) {
    await p.evaluate(async s => { pollkadot.st.method = s[0]; pollkadot.st.cmp = s[1]; pollkadot.st.gran = s[2]; pollkadot.st.metric = s[1] === 'pop' ? 'gdp' : 'pop'; pollkadot.view = { k: 1, x: 0, y: 0 }; await pollkadot.go() }, [m, c, g]); await p.waitForFunction(() => !pollkadot.animating); await p.waitForTimeout(250);
    // simulate a pan/zoom gesture: time 30 consecutive frames rendered while view changes
    const t = await p.evaluate(() => new Promise(res => { let n = 0, t0 = performance.now(); pollkadot.markInteracting(); const f = () => { pollkadot.view.k = 1 + n * 0.05; pollkadot.view.x = -n * 6; pollkadot.view.y = -n * 3; pollkadot.markInteracting(); pollkadot.draw(); if (++n < 30) requestAnimationFrame(f); else res((performance.now() - t0) / 30) }; requestAnimationFrame(f) }));
    // blank-edge check mid-gesture: pixels coverage on left/right thirds should be non-zero after panning
    const cov = await p.evaluate(() => { const g = pollkadot.cv.getContext('2d').getImageData(0, 0, pollkadot.cv.width, pollkadot.cv.height).data; let n = 0, t = 0; for (let y = 0; y < pollkadot.cv.height; y += 9) for (let x = 0; x < pollkadot.cv.width; x += 9) { t++; if (g[4 * (y * pollkadot.cv.width + x) + 3] > 0) n++ } return (100 * n / t).toFixed(0) });
    console.log(`${m}/${c}/${g}: ${t.toFixed(1)} ms per frame during pan+zoom, coverage ${cov}%`);
    await p.evaluate(() => { pollkadot.view = { k: 1, x: 0, y: 0 }; pollkadot.draw() });
  }
  // real mouse: left drag, right drag ending outside the map, middle drag
  await p.evaluate(async () => { pollkadot.st.method = 'circ'; pollkadot.st.cmp = 'none'; pollkadot.st.gran = 'county'; pollkadot.st.metric = 'pop'; await pollkadot.go() }); await p.waitForFunction(() => !pollkadot.animating);
  await p.mouse.move(640, 350); await p.mouse.down(); await p.mouse.move(560, 320, { steps: 6 });
  const cur = await p.evaluate(() => pollkadot.cv.style.cursor); await p.locator('#stage').screenshot({ path: 'build/sweep/pan_mid.png' }); await p.mouse.up();
  const v1 = await p.evaluate(() => ({ ...pollkadot.view }));
  await p.mouse.move(640, 350); await p.mouse.down({ button: 'right' }); await p.mouse.move(640, 880, { steps: 8 }); await p.mouse.up({ button: 'right' });
  await p.waitForTimeout(100); const v2 = await p.evaluate(() => ({ ...pollkadot.view }));
  const lg = await p.locator('#curvebox').boundingBox(); await p.mouse.move(lg.x + lg.width / 2, lg.y + 20); for (let i = 0; i < 4; i++) await p.mouse.wheel(0, -200);
  await p.mouse.down({ button: 'right' }); await p.mouse.move(lg.x + lg.width / 2, lg.y - 300, { steps: 6 }); await p.mouse.up({ button: 'right' }); await p.waitForTimeout(100);
  const ctx = await p.evaluate(() => __ctx);
  console.log('cursor while dragging:', cur, '| left-drag moved view:', v1.x !== 0, '| right-drag moved view:', v2.y !== v1.y, '| contextmenu events (preventDefault?):', JSON.stringify(ctx), '| errors', JSON.stringify(errs));
  await b.close();
})();
