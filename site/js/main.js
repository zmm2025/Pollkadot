// Entry point: wires up every module, loads the data and shows the first contest.
import * as state from './state.js';
import * as color from './color.js';
import * as format from './format.js';
import './aux-drag.js';
import * as data from './data.js';
import * as transition from './transition.js';
import * as render from './render.js';
import * as legend from './legend.js';
import * as exporter from './export.js';
import * as interaction from './interaction.js';
import * as ui from './ui.js';
import { app, scene, st } from './state.js';
import { D, loadCoreData } from './data.js';
import { resizeMap } from './render.js';
import { drawLegend } from './legend.js';
import { chipFades, pick } from './ui.js';

// Debug handle for the browser console and the Playwright tests. Reading `pollkadot.<name>` returns live state
// (`app`, then `scene`) or any exported value, e.g. `pollkadot.disp` or `pollkadot.go()`. Only `app` and `scene`
// fields can be assigned, e.g. `pollkadot.view = { k: 1, x: 0, y: 0 }`.
const stores = [app, scene];
const modules = [state, color, format, data, transition, render, legend, exporter, interaction, ui];
window.pollkadot = new Proxy(
  {},
  {
    get: (_, key) => {
      const store = stores.find(s => key in s);
      return store ? store[key] : modules.find(m => key in m)?.[key];
    },
    set: (_, key, value) => {
      const store = stores.find(s => key in s);
      if (!store) throw new TypeError(`pollkadot.${String(key)} is read-only`);
      store[key] = value;
      return true;
    },
  },
);

// The map, the chip row's edge fades and the curve all depend on the page size.
function resize() {
  resizeMap();
  chipFades();
  drawLegend();
}
window.addEventListener('resize', () => D && resize());
try {
  const ro = new ResizeObserver(() => {
    if (D) resize();
  });
  for (const id of ['stage', 'chips', 'legcard']) ro.observe(document.getElementById(id));
} catch (e) {}
(async () => {
  try {
    await loadCoreData();
    const only = { votes: 'Presidential races only', ev: 'Presidential races only', senate: 'Senate races only' };
    D.metrics.forEach(m => (m.only = only[m.key] || 'Not available for this race'));
    st.method = D.defaultMethod;
    const h = location.hash.slice(1);
    const c = D.contests.find(x => x.key === h) || D.contests.find(x => x.key === D.defaultKey);
    resize();
    pick(c);
  } catch (err) {
    document.getElementById('pvcap').textContent = 'Could not load map data: ' + err;
    console.error(err);
  }
})();
