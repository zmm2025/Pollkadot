// Automated interaction sweep of the county map page.
const { chromium } = require('playwright');
const fs = require('fs');
const OUT = 'build/sweep'; fs.mkdirSync(OUT, { recursive: true });
const issues = []; const log = (...a) => console.log(...a);
const issue = (where, what) => { issues.push({ where, what }); log('  ISSUE', where, '->', what); };

async function settle(p) { // wait for load + animation to finish
  await p.waitForFunction(() => typeof disp !== 'undefined' && disp && !animating && document.getElementById('busy').style.display !== 'block', null, { timeout: 15000 });
  await p.waitForTimeout(60);
}
// state checks run inside the page
const CHECK = () => {
  const out = [];
  const fin = a => { if (!a) return true; for (let i = 0; i < a.length; i++) if (!isFinite(a[i])) return false; return true };
  if (disp.type === 'circ' && !fin(disp.c)) out.push('NaN in circle layout');
  if (disp.type === 'shape' && !fin(disp.pos)) out.push('NaN in shape layout');
  if (ringC && !fin(ringC)) out.push('NaN in ring radii');
  if (outl && outl.E && !fin(outl.E)) out.push('NaN in outline geometry');
  if (!fin(colT) || !fin(colV)) out.push('NaN in colours');
  if (dens && !fin(dens)) out.push('NaN in curve');
  const c = st.contest;
  if (dens && dens.reduce((a, b) => a + b, 0) <= 0) out.push('empty curve');
  if (st.cmp !== 'none' && !ringC && !outl && !ringE) out.push('rings selected but none drawn');
  // canvas not blank: count non-background pixels on a sample grid
  const g = cv.getContext('2d').getImageData(0, 0, cv.width, cv.height).data; let n = 0, tot = 0;
  for (let y = 0; y < cv.height; y += 7) for (let x = 0; x < cv.width; x += 7) { const o = 4 * (y * cv.width + x); tot++; if (g[o + 3] > 0) n++ }
  if (n / tot < 0.01) out.push('canvas nearly blank (' + (100 * n / tot).toFixed(2) + '%)');
  // tooltip text for a few units
  const nU = NU(); for (const u of [0, Math.floor(nU / 3), Math.floor(2 * nU / 3), nU - 1]) {
    sel = u; tipPos = [50, 50]; updateTip(); const h = document.getElementById('tip').innerHTML;
    if (/NaN|undefined|Infinity/.test(h)) out.push('tooltip text bad for unit ' + u + ': ' + h.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').slice(0, 160));
  }
  sel = -1; updateTip();
  // labels
  for (const el of [...document.querySelectorAll('#chips .chip'), document.getElementById('pvcap'), document.getElementById('pvnames')]) { const t = el.textContent; if (/NaN|undefined/.test(t)) out.push(el.id + ' text: ' + t) }
  // chip / header button overflow
  for (const el of document.querySelectorAll('#chips .chip, #infobtn')) { if (el.scrollWidth > el.clientWidth + 2) out.push('text clipped in ' + (el.id || el.className) + ': ' + el.textContent.trim().slice(0, 40)) }
  return { problems: out, coverage: (100 * n / tot).toFixed(1) };
};
async function setState(p, s) {
  await p.evaluate(async s => {
    if (s.contest) { const c = D.contests.find(x => x.key === s.contest); st.contest = c; }
    for (const k of ['metric', 'method', 'cmp', 'gran', 'shade']) if (s[k] !== undefined) st[k] = s[k];
    if (s.borders !== undefined) st.borders = s.borders;
    selBand = null; preview = null; hl = null; xr = [0, 1]; sel = -1;
    await go();
  }, s);
  await settle(p);
}
(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: 1280, height: 900 } });
  const p = await ctx.newPage(); const errs = [];
  p.on('pageerror', e => errs.push(e.message)); p.on('console', m => { if (m.type() === 'error') errs.push(m.text()) });
  const flushErr = where => { while (errs.length) issue(where, 'JS error: ' + errs.shift()) };
  const t0 = Date.now();
  await p.goto('http://localhost:8000/'); await settle(p); flushErr('load');
  const meta = await p.evaluate(() => ({ contests: D.contests.map(c => ({ key: c.key, office: c.office, year: c.year })), metrics: D.metrics.map(m => m.key), methods: D.methods.map(m => m.key) }));
  log('contests', meta.contests.length, 'metrics', meta.metrics.join(','), 'methods', meta.methods.join(','));
  let checked = 0; const shots = [];

  // ---- Pass A: every race, default view, counties + states, both colour modes ----
  log('\nPASS A: every race × counties/states × share/winner (packed circles, population)');
  for (const c of meta.contests) for (const gran of ['county', 'state']) for (const shade of ['share', 'winner']) {
    const where = `${c.key} ${gran} ${shade}`;
    try { await setState(p, { contest: c.key, metric: 'pop', method: 'circ', cmp: 'none', gran, shade }); const r = await p.evaluate(CHECK); r.problems.forEach(x => issue(where, x)); checked++;
      if (shade === 'share' && gran === 'county') { const f = `${OUT}/A_${c.key}.png`; await p.locator('#stage').screenshot({ path: f }); shots.push([f, c.key]) } }
    catch (e) { issue(where, 'exception: ' + e.message.split('\n')[0]) }
    flushErr(where);
  }
  // ---- Pass B: every size × shape × granularity, rings none + each ring, on four representative races ----
  log('\nPASS B: size × rings × shape × counties/states on 2024 pres, 2022 sen, 2018 gov, 2024 house');
  const races = ['2024-pres', '2022-sen', '2018-gov', '2024-house'];
  for (const race of races) {
    const avail = await p.evaluate(k => { const c = D.contests.find(x => x.key === k); return D.metrics.filter(m => metricAvailable(c, m.key)).map(m => m.key) }, race);
    for (const metric of avail) for (const method of meta.methods) for (const gran of ['county', 'state']) {
      const rings = ['none', ...avail.filter(m => m !== metric)];
      for (const cmp of rings) {
        if (cmp !== 'none' && !(race === '2024-pres' || cmp === 'pop' || cmp === 'land')) continue; // all ring pairs on 2024 pres, pop/land rings elsewhere
        const where = `${race} size=${metric} rings=${cmp} ${method} ${gran}`;
        try { await setState(p, { contest: race, metric, method, cmp, gran, shade: 'share' }); const r = await p.evaluate(CHECK); r.problems.forEach(x => issue(where, x)); checked++;
          if (race === '2024-pres' && gran === 'county' && (cmp === 'none' || (metric === 'pop' && cmp === 'land') || (metric === 'ev' && cmp === 'pop'))) { const f = `${OUT}/B_${metric}_${method}_${cmp}.png`; await p.locator('#stage').screenshot({ path: f }); shots.push([f, `${metric}/${method}/${cmp}`]) } }
        catch (e) { issue(where, 'exception: ' + e.message.split('\n')[0]) }
        flushErr(where);
      }
    }
  }
  // ---- Pass C: real UI interactions ----
  log('\nPASS C: UI interactions');
  await setState(p, { contest: '2024-pres', metric: 'pop', method: 'circ', cmp: 'none', gran: 'county', shade: 'share' });
  const ui = async (name, fn) => { try { await fn(); await p.waitForTimeout(150); flushErr(name); log('  ok', name) } catch (e) { issue(name, 'exception: ' + e.message.split('\n')[0]); flushErr(name) } };
  await ui('year menu open/pick', async () => { await p.click('#ddYear'); await p.locator('#menu button', { hasText: '2016' }).click(); await settle(p); if (await p.evaluate(() => st.contest.key) !== '2016-pres') throw new Error('year not switched') });
  await ui('race menu open/pick', async () => { await p.click('#ddRace'); await p.locator('#menu button', { hasText: 'Senate' }).click(); await settle(p); if (await p.evaluate(() => st.contest.office) !== 'SEN') throw new Error('race not switched') });
  await ui('menu closes on outside click', async () => { await p.click('#ddMetric'); await p.mouse.click(5, 5); if (await p.evaluate(() => menu.classList.contains('show'))) throw new Error('menu stayed open') });
  await ui('menu closes on Escape', async () => { await p.click('#ddMetric'); await p.keyboard.press('Escape'); if (await p.evaluate(() => menu.classList.contains('show'))) throw new Error('menu stayed open') });
  await ui('disabled metric not selectable', async () => { await p.click('#ddMetric'); const dis = await p.locator('#menu button[disabled]').count(); if (!dis) throw new Error('expected disabled options for Senate'); await p.keyboard.press('Escape') });
  await ui('map style menu picks all 3', async () => { const seen = []; for (const k of ['place', 'contig', 'circ']) { await p.click('#cMethod'); await p.click(`#menu button[data-v="${k}"]`); await settle(p); seen.push(await p.evaluate(() => st.method)) } if (seen.join() !== 'place,contig,circ') throw new Error('picked ' + seen) });
  await ui('borders menu', async () => { await p.evaluate(() => { st.method = 'circ'; go() }); await settle(p); await p.click('#cBorders'); await p.click('#menu button[data-v="on"]'); if (!await p.evaluate(() => st.borders)) throw new Error('not on'); await p.click('#cBorders'); await p.click('#menu button[data-v="off"]'); if (await p.evaluate(() => st.borders)) throw new Error('not off') });
  await ui('color menu share/winner', async () => { await p.click('#cColor'); await p.click('#menu button[data-v="winner"]'); await settle(p); if (await p.evaluate(() => st.shade) !== 'winner') throw new Error('not winner'); await p.click('#cColor'); await p.click('#menu button[data-v="share"]'); await settle(p) });
  await ui('curve: click selects band, Esc clears', async () => { const bb = await p.locator('#curvebox').boundingBox(); await p.mouse.click(bb.x + bb.width * 0.6, bb.y + 20); await p.waitForTimeout(100); if (!await p.evaluate(() => !!selBand)) throw new Error('no band'); await p.keyboard.press('Escape'); if (await p.evaluate(() => !!selBand)) throw new Error('band not cleared') });
  await ui('curve: drag range then clear button', async () => { const bb = await p.locator('#curvebox').boundingBox(); await p.mouse.move(bb.x + bb.width * 0.2, bb.y + 20); await p.mouse.down(); await p.mouse.move(bb.x + bb.width * 0.45, bb.y + 25, { steps: 6 }); await p.mouse.up();
    const r = await p.evaluate(() => [selBand[0], selBand[1], document.getElementById('chiptxt').textContent]); if (!(r[1] > r[0])) throw new Error('bad band ' + r); await p.mouse.move(640, 300); await p.locator('#stage').screenshot({ path: `${OUT}/C_band.png` }); await p.locator('#legcard').screenshot({ path: `${OUT}/C_legend_band.png` }); await p.click('#clearSel'); if (await p.evaluate(() => !!selBand)) throw new Error('not cleared') });
  await ui('curve: tiny centred band labels do not overlap', async () => { const bb = await p.locator('#curvebox').boundingBox(); await p.mouse.move(bb.x + bb.width * 0.499, bb.y + 20); await p.mouse.down(); await p.mouse.move(bb.x + bb.width * 0.501, bb.y + 20, { steps: 2 }); await p.mouse.up();
    const ov = await p.evaluate(() => { const a = elLo.getBoundingClientRect(), b = elHi.getBoundingClientRect(); return a.right > b.left + 0.5 }); await p.locator('#legcard').screenshot({ path: `${OUT}/C_legend_tiny.png` }); if (ov) throw new Error('edge labels overlap'); await p.click('#clearSel') });
  await ui('curve: band near right edge keeps chip inside panel', async () => { const bb = await p.locator('#curvebox').boundingBox(); await p.mouse.move(bb.x + bb.width * 0.97, bb.y + 20); await p.mouse.down(); await p.mouse.move(bb.x + bb.width * 0.999, bb.y + 20, { steps: 3 }); await p.mouse.up();
    const r = await p.evaluate(() => { const c = document.querySelector('#chip .in').getBoundingClientRect(), l = document.getElementById('legend').getBoundingClientRect(), h = elHi.getBoundingClientRect(); return [c.left >= l.left - 1 && c.right <= l.right + 1, h.right <= l.right + 1] }); if (!r[0]) throw new Error('chip outside'); if (!r[1]) throw new Error('right label outside'); await p.click('#clearSel') });
  await ui('curve: wheel zoom + right-drag pan + zoom-out button', async () => { const bb = await p.locator('#curvebox').boundingBox(); await p.mouse.move(bb.x + bb.width * 0.5, bb.y + 20); for (let i = 0; i < 5; i++) await p.mouse.wheel(0, -200);
    const z = await p.evaluate(() => xr.slice()); if (!(z[1] - z[0] < 0.9)) throw new Error('no zoom ' + z); await p.mouse.down({ button: 'right' }); await p.mouse.move(bb.x + bb.width * 0.3, bb.y + 20, { steps: 5 }); await p.mouse.up({ button: 'right' });
    const z2 = await p.evaluate(() => xr.slice()); if (Math.abs(z2[0] - z[0]) < 1e-6) throw new Error('pan did nothing'); await p.locator('#legcard').screenshot({ path: `${OUT}/C_legend_zoomed.png` }); for (let i = 0; i < 8; i++) await p.click('#lzout').catch(() => { }); });
  await ui('map: click county zooms in, zoom-out returns', async () => { await p.mouse.click(860, 330); await p.waitForTimeout(700); const k = await p.evaluate(() => view.k); if (!(k > 1.5)) throw new Error('no zoom, k=' + k); await p.locator('#stage').screenshot({ path: `${OUT}/C_clickzoom.png` }); for (let i = 0; i < 12; i++) { if (await p.locator('#zout').isDisabled()) break; await p.click('#zout'); await p.waitForTimeout(380) } if (await p.evaluate(() => view.k) !== 1) throw new Error('not back to 1') });
  await ui('map: drag pans, wheel zooms', async () => { await p.mouse.move(700, 400); await p.mouse.down(); await p.mouse.move(600, 380, { steps: 5 }); await p.mouse.up(); await p.mouse.wheel(0, -300); await p.waitForTimeout(300); await p.evaluate(() => { view = { k: 1, x: 0, y: 0 }; draw() }) });
  await ui('popular vote bar hover tooltip', async () => { const bb = await p.locator('#pvbar').boundingBox(); await p.mouse.move(bb.x + 20, bb.y + 4); await p.waitForTimeout(100); const h = await p.evaluate(() => document.getElementById('pvtip').textContent); if (!/Votes/.test(h) || /NaN|undefined/.test(h)) throw new Error(h.slice(0, 80)); await p.mouse.move(bb.x + bb.width - 10, bb.y + 4); await p.waitForTimeout(100) });
  await ui('details sheet opens and closes', async () => { await p.click('#infobtn'); await p.waitForTimeout(100); const t = await p.evaluate(() => sheetbox.textContent); if (/NaN|undefined/.test(t)) throw new Error('bad text'); await p.keyboard.press('Escape'); if (await p.evaluate(() => sheet.classList.contains('show'))) throw new Error('sheet still open') });
  await ui('only built-in results: every contest has votes, no file loading', async () => { const r = await p.evaluate(() => ({ empty: D.contests.filter(c => { let t = 0; for (let i = 0; i < c.dem.length; i++) t += c.dem[i] + c.rep[i] + c.oth[i]; return !(t > 0) }).map(c => c.key), file: !!document.querySelector('input[type=file]') }));
    if (r.empty.length) throw new Error('contests without results: ' + r.empty.join(', ')); if (r.file) throw new Error('file input present');
    for (const o of ['Senate', 'House', 'Governor']) { await p.click('#ddRace'); await p.locator('#menu button', { hasText: o }).click(); await settle(p); await p.click('#ddYear'); const ys = await p.locator('#menu button').allTextContents(); await p.keyboard.press('Escape'); if (ys.some(y => /2026/.test(y))) throw new Error(o + ' year menu lists 2026') }
    await p.click('#infobtn'); const t = await p.evaluate(() => sheetbox.textContent); await p.keyboard.press('Escape'); if (/load results|\bcsv\b/i.test(t)) throw new Error('details sheet offers loading') });
  // ---- Pass D: rapid switching while animating (race conditions) ----
  log('\nPASS D: rapid switching mid-animation');
  await ui('rapid changes', async () => { for (let i = 0; i < 25; i++) { await p.evaluate(i => { const ms = ['circ', 'place', 'contig'], gs = ['county', 'state'], cs = ['none', 'land', 'gdp']; st.method = ms[i % 3]; st.gran = gs[(i >> 1) % 2]; st.cmp = cs[i % 3]; st.contest = D.contests[(i * 7) % 20]; go() }, i); await p.waitForTimeout(90 + (i % 4) * 60) }
    await settle(p); const r = await p.evaluate(CHECK); r.problems.forEach(x => issue('after rapid changes', x)) });
  // ---- Pass E: phone width + dark mode ----
  log('\nPASS E: phone width, dark mode');
  for (const [w, h, scheme] of [[390, 844, 'light'], [390, 844, 'dark'], [1280, 900, 'dark']]) {
    const c2 = await b.newContext({ viewport: { width: w, height: h }, colorScheme: scheme, deviceScaleFactor: w < 500 ? 2 : 1 }); const q = await c2.newPage(); q.on('pageerror', e => issue(`${w}px ${scheme}`, 'JS error: ' + e.message));
    await q.goto('http://localhost:8000/#2024-pres'); await settle(q);
    const lay = await q.evaluate(() => { const r = []; const vw = innerWidth; for (const el of document.querySelectorAll('button,#pvnames span')) { if (el.closest('#chips')) continue; const b = el.getBoundingClientRect(); if (b.width && (b.right > vw + 1 || b.left < -1)) r.push((el.id || el.textContent.trim()).slice(0, 30)) } const st_ = document.getElementById('stage').getBoundingClientRect(); return { off: r, stageH: Math.round(st_.height), docH: document.documentElement.scrollHeight, vh: innerHeight } });
    if (lay.off.length) issue(`${w}px ${scheme}`, 'elements off-screen: ' + lay.off.join(', '));
    if (lay.stageH < 200) issue(`${w}px ${scheme}`, 'map area only ' + lay.stageH + 'px tall');
    if (lay.docH > lay.vh + 2) issue(`${w}px ${scheme}`, `page scrolls (content ${lay.docH}px > viewport ${lay.vh}px)`);
    const r = await q.evaluate(CHECK); r.problems.forEach(x => issue(`${w}px ${scheme}`, x));
    const f = `${OUT}/E_${w}_${scheme}.png`; await q.screenshot({ path: f, fullPage: true }); shots.push([f, `${w}px ${scheme}`]);
    await q.click('#ddMetric'); await q.screenshot({ path: `${OUT}/E_${w}_${scheme}_menu.png` }); await c2.close();
  }
  fs.writeFileSync(`${OUT}/shots.json`, JSON.stringify(shots));
  fs.writeFileSync(`${OUT}/issues.json`, JSON.stringify(issues, null, 1));
  log(`\nchecked ${checked} states + UI in ${((Date.now() - t0) / 1000).toFixed(0)}s; issues: ${issues.length}`);
  await b.close();
})();
