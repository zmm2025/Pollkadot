const { chromium } = require('playwright'); const BASE = process.env.BASE_URL || 'http://localhost:8000'; const fs = require('fs'); fs.mkdirSync('build/sweep', { recursive: true });
(async () => {
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1280, height: 900 } }); const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.goto(BASE + '/#2024-pres'); await p.waitForFunction(() => window.pollkadot?.disp && !pollkadot.animating);
  const shot = async (name) => { const d = await p.evaluate(() => pollkadot.renderExport().toDataURL('image/png')); fs.writeFileSync(`build/sweep/X_${name}.png`, Buffer.from(d.split(',')[1], 'base64')) };
  // messy live state: zoomed, county selected, band highlight, hovering
  await p.evaluate(() => { pollkadot.view = { k: 4, x: -900, y: -400 }; pollkadot.sel = 5; pollkadot.selBand = [0.6, 0.9]; pollkadot.refreshBand(); pollkadot.draw() });
  await shot('packed'); const after = await p.evaluate(() => ({ k: pollkadot.view.k, sel: pollkadot.sel, band: !!pollkadot.selBand }));
  for (const [m, c, g, sh] of [['place', 'land', 'county', 'share'], ['contig', 'none', 'county', 'winner'], ['circ', 'pop', 'state', 'share'], ['contig', 'land', 'state', 'share']]) {
    await p.evaluate(async s => { pollkadot.st.method = s[0]; pollkadot.st.cmp = s[1]; pollkadot.st.gran = s[2]; pollkadot.st.shade = s[3]; if (s[1] === 'pop') pollkadot.st.metric = 'ev'; await pollkadot.go() }, [m, c, g, sh]); await p.waitForFunction(() => !pollkadot.animating); await shot(`${m}_${c}_${g}_${sh}`) }
  await p.evaluate(() => { pollkadot.st.borders = true; pollkadot.st.method = 'circ'; pollkadot.st.metric = 'pop'; pollkadot.st.cmp = 'none'; pollkadot.st.gran = 'county'; pollkadot.st.shade = 'share'; pollkadot.go() }); await p.waitForFunction(() => !pollkadot.animating);
  const vis = await p.isVisible('#exportBtn'); const [dl] = await Promise.all([p.waitForEvent('download'), p.click('#exportBtn')]); const saved = { filename: dl.suggestedFilename(), size: fs.statSync(await dl.path()).size };
  console.log('button visible:', vis, '| saved:', JSON.stringify(saved), '| live view kept after export:', JSON.stringify(after), '| errors', JSON.stringify(errs));
  await p.locator('#stage').screenshot({ path: 'build/sweep/X_button.png' });
  await b.close();
})();
