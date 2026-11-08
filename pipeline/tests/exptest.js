const { chromium } = require('playwright'); const fs = require('fs');
(async () => {
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1280, height: 900 } }); const errs = []; p.on('pageerror', e => errs.push(e.message));
  // stub the platform downloads capability to exercise the button path
  await p.addInitScript(() => { window.__saved = null; window.claude = { use: async n => n === 'downloads' ? { save: async ({ filename, data }) => { window.__saved = { filename, size: data.size, type: data.constructor.name }; return { status: 'saved' } } } : null } });
  await p.goto('http://localhost:8000/#2024-pres'); await p.waitForFunction(() => typeof disp !== 'undefined' && disp && !animating);
  const shot = async (name) => { const d = await p.evaluate(() => renderExport().toDataURL('image/png')); fs.writeFileSync(`build/sweep/X_${name}.png`, Buffer.from(d.split(',')[1], 'base64')) };
  // messy live state: zoomed, county selected, band highlight, hovering
  await p.evaluate(() => { view = { k: 4, x: -900, y: -400 }; sel = 5; selBand = [0.6, 0.9]; refreshBand(); draw() });
  await shot('packed'); const after = await p.evaluate(() => ({ k: view.k, sel, band: !!selBand }));
  for (const [m, c, g, sh] of [['place', 'land', 'county', 'share'], ['contig', 'none', 'county', 'winner'], ['circ', 'pop', 'state', 'share'], ['contig', 'land', 'state', 'share']]) {
    await p.evaluate(async s => { st.method = s[0]; st.cmp = s[1]; st.gran = s[2]; st.shade = s[3]; if (s[1] === 'pop') st.metric = 'ev'; await go() }, [m, c, g, sh]); await p.waitForFunction(() => !animating); await shot(`${m}_${c}_${g}_${sh}`) }
  await p.evaluate(() => { st.borders = true; st.method = 'circ'; st.metric = 'pop'; st.cmp = 'none'; st.gran = 'county'; st.shade = 'share'; go() }); await p.waitForFunction(() => !animating);
  const vis = await p.isVisible('#exportBtn'); await p.click('#exportBtn'); await p.waitForTimeout(800);
  console.log('button visible:', vis, '| saved:', JSON.stringify(await p.evaluate(() => __saved)), '| live view kept after export:', JSON.stringify(after), '| errors', JSON.stringify(errs));
  await p.locator('#stage').screenshot({ path: 'build/sweep/X_button.png' });
  await b.close();
})();
