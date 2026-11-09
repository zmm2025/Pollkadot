// Controls: icons, the chip row and its menus, header, popular-vote bar and details sheet.
import { D, NC, stateSum, weightsFor } from './data.js';
import { fmt, OFF, pct } from './format.js';
import {
  app,
  metricAvailable,
  metricInfo,
  normalizeSettings,
  NU,
  st,
  UNIT,
  unitSkip,
  unitVotes,
  wkeyFor,
} from './state.js';
import { requestDraw } from './render.js';
import { refreshBand } from './legend.js';
import { updateTip } from './interaction.js';
import { transitionTo } from './transition.js';

// ================= icons =================
const ICP = {
  land: '<path d="M1.5 13.5l4-7 3 4.5 2-3 4 5.5z"/>',
  pop: '<circle cx="6" cy="5" r="2.2"/><path d="M2 13.5c0-2.6 1.8-4.2 4-4.2s4 1.6 4 4.2"/><circle cx="11.5" cy="5.5" r="1.8"/><path d="M11 9.3c1.8.2 3 1.6 3 4.2"/>',
  votes: '<rect x="2.5" y="8" width="11" height="6" rx="1"/><path d="M5 8V2.5h6V8M6.5 5.2h3"/>',
  ev: '<path d="M8 1.8l1.9 3.9 4.3.6-3.1 3 .7 4.3L8 11.6l-3.8 2 .7-4.3-3.1-3 4.3-.6z"/>',
  senate: '<path d="M2 6h12L8 2.5zM3.8 6v6M6.6 6v6M9.4 6v6M12.2 6v6M2 13.5h12"/>',
  edu: '<path d="M1.5 6.2L8 3.2l6.5 3L8 9.2z"/><path d="M4.5 7.7v3c0 1 1.6 2 3.5 2s3.5-1 3.5-2v-3M14.5 6.2v4"/>',
  gdp: '<path d="M2 13.5h12M3.5 11l3-3.5 2.5 2 4-5"/><path d="M10.5 4.5H13V7"/>',
  none: '<circle cx="8" cy="8" r="5.5"/><path d="M4.2 11.8l7.6-7.6"/>',
  circ: '<circle cx="5.5" cy="6" r="3.2"/><circle cx="11.6" cy="5.4" r="2.1"/><circle cx="10.4" cy="11.6" r="2.6"/><circle cx="4.4" cy="12.4" r="1.6"/>',
  place: '<circle cx="6" cy="8" r="4.2"/><circle cx="10.6" cy="8" r="3.6"/>',
  contig: '<path d="M2 3.5l4-1.5 4 1.5 4-1.5v10.5l-4 1.5-4-1.5-4 1.5zM6 2v10.5M10 3.5V14"/>',
  borders: '<path d="M2.5 3h11v10h-11z"/><path d="M8 3v10M2.5 8H8"/>',
  noborders: '<path d="M2.5 3h11v10h-11z" stroke-dasharray="2 1.8" opacity=".6"/>',
  ring: '<circle cx="8" cy="8" r="5.8"/><circle cx="8" cy="8" r="2.4"/>',
  share: '<circle cx="8" cy="8" r="5.8"/><path d="M8 2.2a5.8 5.8 0 0 1 0 11.6z" fill="currentColor" stroke="none"/>',
  winner:
    '<path d="M5 2.5h6v3.3a3 3 0 0 1-6 0z"/><path d="M5 3.6H3.2c0 1.7.8 2.7 2 2.9M11 3.6h1.8c0 1.7-.8 2.7-2 2.9M8 8.8v2.7M5.5 13.5h5"/>',
  county:
    '<rect x="2.5" y="2.5" width="11" height="11" rx="1.5"/><path d="M2.5 6.2h11M2.5 9.8h11M6.2 2.5v11M9.8 2.5v11"/>',
  state: '<rect x="2.5" y="2.5" width="11" height="11" rx="1.5"/><path d="M8 2.5v11M2.5 8h11"/>',
};
const icon = k =>
  `<svg class="ic" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">${ICP[k] || ''}</svg>`;
const item = (v, label, { on = false, ic = null, dis = false, desc = '' } = {}) =>
  `<button data-v="${v}" class="${on ? 'on' : ''}" ${dis ? 'disabled' : ''}>${ic ? icon(ic) : ''}<span class="lab">${label}${desc ? `<span class="d">${desc}</span>` : ''}</span><span class="ck">✓</span></button>`;
// ================= UI =================
// ---- dropdown menu: grows out of its anchor; chips are scrolled to the centre of the row first ----
const menu = document.getElementById('menu'),
  menuin = document.getElementById('menuin'),
  scrim = document.getElementById('scrim'),
  chipsEl = document.getElementById('chips');
let menuAnchor = null,
  menuSeq = 0,
  menuTimer = 0,
  menuClosedAt = -1e9;
const reducedMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches,
  phoneLayout = () => matchMedia('(max-width:640px)').matches;
const menuOpen = () => menu.classList.contains('show');
function openMenu(anchor, html, onclick, head = '') {
  if (menuAnchor === anchor) {
    closeMenu();
    return;
  }
  closeMenu();
  const seq = ++menuSeq;
  menuAnchor = anchor;
  anchor.classList.add('open');
  const inRow = chipsEl.contains(anchor);
  (inRow ? centerChip(anchor) : Promise.resolve()).then(() => {
    if (seq !== menuSeq) return;
    const wait = reducedMotion() ? 0 : Math.max(0, menuClosedAt + 95 - performance.now());
    setTimeout(() => {
      if (seq === menuSeq) showMenu(anchor, html, onclick, head, inRow);
    }, wait);
  });
}
function showMenu(anchor, html, onclick, head, inRow) {
  clearTimeout(menuTimer);
  menuin.innerHTML = (head ? `<div class="mh">${head}</div>` : '') + html;
  menuin.scrollTop = 0;
  menuin.style.maxHeight = '';
  const phone = phoneLayout(),
    wide = phone && inRow;
  menu.classList.remove('show', 'up');
  menu.classList.toggle('wide', wide);
  menu.style.width = wide ? innerWidth - 20 + 'px' : '';
  menu.style.display = 'block';
  const r = anchor.getBoundingClientRect(),
    mw = menu.offsetWidth;
  let mh = menuin.offsetHeight;
  const cx = r.left + r.width / 2,
    gap = 9;
  let limit = innerHeight - 10;
  if (phone) {
    const lc = document.getElementById('legcard').getBoundingClientRect();
    if (lc.top > r.bottom + 120) limit = Math.min(limit, lc.top - 8);
  }
  const below = limit - (r.bottom + gap),
    above = r.top - gap - 10,
    up = mh > below && below < 200 && above > below;
  const room = up ? above : below;
  if (mh > room) {
    menuin.style.maxHeight = room + 'px';
    mh = room;
  }
  const x = Math.min(Math.max(10, cx - mw / 2), innerWidth - mw - 10),
    y = up ? r.top - gap - mh : r.bottom + gap,
    ax = Math.max(18, Math.min(mw - 18, cx - x));
  menu.style.left = x + 'px';
  menu.style.top = y + 'px';
  menu.style.setProperty('--ax', ax + 'px');
  menu.style.transformOrigin = `${ax}px ${up ? '100%' : '0'}`;
  menu.classList.toggle('up', up);
  if (phone) {
    scrim.classList.add('show');
    document.body.classList.add('mopen');
  }
  void menu.offsetWidth;
  menu.classList.add('show');
  menu.onclick = e => {
    const b = e.target.closest('button');
    if (!b || b.disabled) return;
    closeMenu();
    onclick(b.dataset.v);
  };
}
function closeMenu() {
  menuSeq++;
  if (menuAnchor) menuAnchor.classList.remove('open');
  menuAnchor = null;
  scrim.classList.remove('show');
  document.body.classList.remove('mopen');
  if (!menuOpen()) return;
  menu.classList.remove('show');
  menuClosedAt = performance.now();
  clearTimeout(menuTimer);
  menuTimer = setTimeout(
    () => {
      if (!menuOpen()) menu.style.display = 'none';
    },
    reducedMotion() ? 80 : 100,
  );
}
document.addEventListener(
  'pointerdown',
  e => {
    if (menuAnchor && !menu.contains(e.target) && !menuAnchor.contains(e.target)) closeMenu();
  },
  true,
);
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    if (menuAnchor) closeMenu();
    else if (sheet.classList.contains('show')) sheet.classList.remove('show');
    else if (app.selBand) {
      app.selBand = null;
      refreshBand();
    }
  }
});
window.addEventListener('resize', () => {
  if (menuAnchor) closeMenu();
});
// ---- chip row: wheel scrolls it sideways, mouse drag scrolls it, edges fade when there's more ----
let chipAutoUntil = 0; // scroll events arrive a frame late, so programmatic scrolls are recognised by time, not a flag
export function chipFades() {
  const m = chipsEl.scrollWidth - chipsEl.clientWidth;
  chipsEl.classList.toggle('scr', m > 1);
  chipsEl.classList.toggle('fl', chipsEl.scrollLeft > 1);
  chipsEl.classList.toggle('fr', chipsEl.scrollLeft < m - 1);
}
function scrollChips(to, dur) {
  return new Promise(res => {
    const s = chipsEl.scrollLeft;
    if (reducedMotion() || Math.abs(to - s) < 1) {
      chipAutoUntil = performance.now() + 150;
      chipsEl.scrollLeft = to;
      return res();
    }
    const t0 = performance.now();
    chipAutoUntil = t0 + dur + 150;
    const f = n => {
      const p = Math.min(1, (n - t0) / dur);
      chipsEl.scrollLeft = s + (to - s) * (1 - Math.pow(1 - p, 3));
      if (p < 1) requestAnimationFrame(f);
      else {
        chipAutoUntil = performance.now() + 150;
        res();
      }
    };
    requestAnimationFrame(f);
  });
}
function centerChip(c) {
  const m = chipsEl.scrollWidth - chipsEl.clientWidth;
  if (m <= 1) return Promise.resolve();
  return scrollChips(Math.max(0, Math.min(m, c.offsetLeft + c.offsetWidth / 2 - chipsEl.clientWidth / 2)), 260);
}
chipsEl.addEventListener('scroll', () => {
  chipFades();
  if (performance.now() > chipAutoUntil && menuAnchor && chipsEl.contains(menuAnchor)) closeMenu();
});
chipsEl.addEventListener(
  'wheel',
  e => {
    const m = chipsEl.scrollWidth - chipsEl.clientWidth;
    if (m <= 1) return;
    e.preventDefault();
    const d = Math.abs(e.deltaY) > Math.abs(e.deltaX) ? e.deltaY : e.deltaX;
    chipsEl.scrollLeft += e.deltaMode === 1 ? d * 16 : d;
  },
  { passive: false },
);
let chipDrag = null,
  chipDragged = false;
chipsEl.addEventListener('pointerdown', e => {
  if (e.pointerType === 'mouse' && e.button === 0)
    chipDrag = { x: e.clientX, s: chipsEl.scrollLeft, id: e.pointerId, moved: false };
});
chipsEl.addEventListener('pointermove', e => {
  if (!chipDrag) return;
  const dx = e.clientX - chipDrag.x;
  if (!chipDrag.moved && Math.abs(dx) > 4 && chipsEl.scrollWidth > chipsEl.clientWidth + 1) {
    chipDrag.moved = true;
    chipsEl.classList.add('drag');
    chipsEl.setPointerCapture(chipDrag.id);
  }
  if (chipDrag.moved) chipsEl.scrollLeft = chipDrag.s - dx;
});
const chipDragEnd = () => {
  if (chipDrag && chipDrag.moved) {
    chipDragged = true;
    setTimeout(() => (chipDragged = false), 0);
  }
  chipDrag = null;
  chipsEl.classList.remove('drag');
};
chipsEl.addEventListener('pointerup', chipDragEnd);
chipsEl.addEventListener('pointercancel', chipDragEnd);
chipsEl.addEventListener(
  'click',
  e => {
    if (chipDragged) {
      e.stopPropagation();
      e.preventDefault();
      chipDragged = false;
    }
  },
  true,
);
// chip label changes tween the chip's width so neighbours slide instead of jumping
function setChip(id, ic, label, title) {
  const b = document.getElementById(id);
  const h = `${icon(ic)}<span class="txt">${label}</span><span class="chev">▾</span>`;
  b.title = title || '';
  if (b.dataset.h === h) return;
  const first = !b.dataset.h,
    w0 = b.offsetWidth;
  b.innerHTML = h;
  b.dataset.h = h;
  if (first || reducedMotion()) return;
  const w1 = b.offsetWidth;
  if (Math.abs(w1 - w0) < 1) return;
  b.style.transition = 'none';
  b.style.width = w0 + 'px';
  void b.offsetWidth;
  b.style.transition = 'width 180ms cubic-bezier(.2,.8,.2,1),background .12s,border-color .12s';
  b.style.width = w1 + 'px';
  clearTimeout(b._tw);
  b._tw = setTimeout(() => {
    b.style.width = '';
    b.style.transition = '';
    chipFades();
  }, 200);
}
const ABBR = { Democrats: 'Dem.', Republicans: 'Rep.', Democratic: 'Dem.', Republican: 'Rep.' };
function candNames(c) {
  if (c.office === 'PRES') {
    const cd = c.cand['*'] || {};
    return [cd.d || 'Democratic', cd.r || 'Republican'];
  }
  return ['Democrats', 'Republicans'];
}
const SHORT = {
  land: 'land area',
  pop: y => `residents, ${y === '2026' ? 'July 2025' : 'July ' + y}`,
  votes: 'ballots cast',
  ev: 'share of state’s electors',
  senate: 'share of state’s 2 senators',
  edu: 'adults with a bachelor’s',
  gdp: y => `GDP, ${y} dollars`,
};
const short = (m, k) => (typeof SHORT[m] === 'function' ? SHORT[m](k) : SHORT[m]);
// Applies the current settings: fixes invalid combinations, refreshes the controls, then animates the map.
export function go() {
  normalizeSettings();
  renderUI();
  return transitionTo();
}
function renderUI() {
  const c = st.contest;
  document.getElementById('ddYear').textContent = c.label;
  document.getElementById('ddRace').textContent = OFF[c.office];
  const contig = st.method === 'contig',
    meth = D.methods.find(x => x.key === st.method);
  setChip('cMethod', st.method, meth.label, meth.short);
  setChip('ddMetric', st.metric, metricInfo(st.metric).label, 'Size: ' + short(st.metric, wkeyFor(c, st.metric)));
  setChip(
    'ddCmp',
    st.cmp === 'none' ? 'none' : 'ring',
    st.cmp === 'none' ? (contig ? 'No outlines' : 'No rings') : metricInfo(st.cmp).label,
    st.cmp === 'none' ? '' : `${contig ? 'Outlines' : 'Rings'}: ${short(st.cmp, wkeyFor(c, st.cmp))}`,
  );
  setChip('cColor', st.shade === 'winner' ? 'winner' : 'share', st.shade === 'winner' ? 'Winner' : 'Vote share');
  setChip('cShow', st.gran === 'state' ? 'state' : 'county', st.gran === 'state' ? 'States' : 'Counties');
  document.getElementById('cBorders').setAttribute('aria-disabled', String(contig));
  setChip(
    'cBorders',
    contig || st.borders ? 'borders' : 'noborders',
    contig || st.borders ? 'State borders' : 'No borders',
    contig ? 'State borders always show in the contiguous shape' : '',
  );
  let d = 0,
    r = 0,
    o = 0;
  for (let i = 0; i < NC; i++) {
    if (c.dedupe[i]) continue;
    d += c.dem[i];
    r += c.rep[i];
    o += c.oth[i];
  }
  const tot = d + r + o || 1;
  const [dn, rn] = candNames(c);
  const nm = n => {
    const a = ABBR[n];
    return a ? `<span class="fn">${n}</span><span class="ab">${a}</span>` : n;
  };
  document.getElementById('pvnames').innerHTML =
    `<span><span class="dot" style="background:var(--dem)"></span>${nm(dn)} <b>${pct(d / tot)}</b></span><span class="sub oth">${o / tot >= 0.005 ? 'Other ' + pct(o / tot) : ''}</span><span>${nm(rn)} <b>${pct(r / tot)}</b><span class="dot" style="background:var(--rep);margin:0 0 0 5px"></span></span>`;
  document.getElementById('pvbar').innerHTML =
    `<div data-p="d" style="width:${(100 * d) / tot}%;background:var(--dem)"></div><div data-p="o" style="width:${(100 * o) / tot}%;background:var(--oth)"></div><div data-p="r" style="width:${(100 * r) / tot}%;background:var(--rep)"></div>`;
  const pc = document.getElementById('pvcap');
  pc.textContent = `${fmt(d + r + o)} ballots`;
  pc.title = `${c.office === 'PRES' ? 'National popular vote' : 'All ' + OFF[c.office] + ' races combined'} · ${fmt(d + r + o)} ballots`;
  document.getElementById('infobtn').classList.toggle('warn', !!(c.gaps && c.gaps.length));
  chipFades();
}
document.getElementById('ddYear').onclick = e => {
  const c = st.contest;
  const list = D.contests.filter(x => x.office === c.office);
  openMenu(
    e.currentTarget,
    `<div class="grid">${list.map(x => `<button data-v="${x.key}" class="${x === c ? 'on' : ''}">${x.label}</button>`).join('')}</div>`,
    k => pick(D.contests.find(x => x.key === k)),
  );
};
document.getElementById('ddRace').onclick = e => {
  const c = st.contest;
  openMenu(
    e.currentTarget,
    Object.entries(OFF)
      .map(([k, l]) => item(k, l, { on: k === c.office }))
      .join(''),
    o => {
      if (o === c.office) return;
      const list = D.contests.filter(x => x.office === o);
      let best = list[0];
      for (const x of list)
        if (
          Math.abs(x.year - c.year) < Math.abs(best.year - c.year) ||
          (x.year === best.year && !x.special && best.special)
        )
          best = x;
      pick(best);
    },
  );
};
const metricItem = (c, m, on) => {
  const ok = metricAvailable(c, m.key);
  return item(m.key, m.label, { on, ic: m.key, dis: !ok, desc: ok ? m.short : m.only });
};
document.getElementById('cMethod').onclick = e =>
  openMenu(
    e.currentTarget,
    D.methods.map(m => item(m.key, m.label, { on: m.key === st.method, ic: m.key, desc: m.short })).join(''),
    k => {
      if (k === st.method) return;
      st.method = k;
      go();
    },
    'Map style',
  );
document.getElementById('ddMetric').onclick = e => {
  const c = st.contest;
  openMenu(
    e.currentTarget,
    D.metrics.map(m => metricItem(c, m, m.key === st.metric)).join(''),
    k => {
      if (k === st.metric) return;
      if (k === st.cmp) st.cmp = 'none';
      st.metric = k;
      go();
    },
    'Size by',
  );
};
document.getElementById('ddCmp').onclick = e => {
  const c = st.contest,
    contig = st.method === 'contig';
  openMenu(
    e.currentTarget,
    item('none', 'None', {
      on: st.cmp === 'none',
      ic: 'none',
      desc: contig ? 'No comparison outlines' : 'No comparison rings',
    }) +
      D.metrics
        .filter(m => m.key !== st.metric)
        .map(m => metricItem(c, m, m.key === st.cmp))
        .join(''),
    k => {
      if (k === st.cmp) return;
      st.cmp = k;
      go();
    },
    contig ? 'Compare with outlines' : 'Compare with rings',
  );
};
document.getElementById('cColor').onclick = e =>
  openMenu(
    e.currentTarget,
    item('share', 'Vote share', {
      on: st.shade === 'share',
      ic: 'share',
      desc: 'Blue-to-red blend by two-party share',
    }) + item('winner', 'Winner', { on: st.shade === 'winner', ic: 'winner', desc: 'Solid blue or red by who won' }),
    k => {
      if (k === st.shade) return;
      st.shade = k;
      go();
    },
    'Color by',
  );
document.getElementById('cShow').onclick = e =>
  openMenu(
    e.currentTarget,
    item('county', 'Counties', { on: st.gran === 'county', ic: 'county', desc: 'One shape per county' }) +
      item('state', 'States', { on: st.gran === 'state', ic: 'state', desc: 'Counties summed to each state' }),
    k => {
      if (k === st.gran) return;
      st.gran = k;
      app.sel = -1;
      app.selBand = null;
      app.preview = null;
      app.hl = null;
      app.xr = [0, 1];
      updateTip();
      go();
    },
    'Show',
  );
document.getElementById('cBorders').onclick = e => {
  if (st.method === 'contig') return;
  openMenu(
    e.currentTarget,
    item('off', 'No borders', { on: !st.borders, ic: 'noborders', desc: 'Hide state outlines' }) +
      item('on', 'State borders', { on: st.borders, ic: 'borders', desc: 'Outline each state' }),
    k => {
      const v = k === 'on';
      if (v === st.borders) return;
      st.borders = v;
      renderUI();
      requestDraw();
    },
    'State borders',
  );
};
export function pick(c) {
  st.contest = c;
  app.sel = -1;
  updateTip();
  go();
  try {
    history.replaceState(null, '', '#' + c.key);
  } catch (e) {}
}
// popular-vote bar hover
const pvtip = document.getElementById('pvtip');
function pvInfo(p, ev) {
  const c = st.contest;
  const [dn, rn] = candNames(c);
  const pop = weightsFor('pop', wkeyFor(c, 'pop'));
  const U = unitVotes(c),
    n = NU(),
    pu = st.gran === 'state' ? stateSum(pop) : pop;
  let d = 0,
    r = 0,
    o = 0,
    wonD = 0,
    wonR = 0,
    popD = 0,
    popR = 0;
  for (let i = 0; i < NC; i++) {
    if (c.dedupe[i]) continue;
    d += c.dem[i];
    r += c.rep[i];
    o += c.oth[i];
  }
  for (let u = 0; u < n; u++) {
    if (unitSkip(c, u)) continue;
    if (U.d[u] > U.r[u]) {
      wonD++;
      popD += pu[u];
    } else if (U.r[u] > U.d[u]) {
      wonR++;
      popR += pu[u];
    }
  }
  const tot = d + r + o,
    un = UNIT();
  let h;
  if (p === 'o')
    h = `<b>Other candidates</b><div class="sub">Third-party, independent and write-in</div><table><tr><td>Votes</td><td>${fmt(o)}</td></tr><tr><td>Share of all votes</td><td>${pct(o / tot)}</td></tr></table>`;
  else {
    const isD = p === 'd';
    const v = isD ? d : r,
      won = isD ? wonD : wonR,
      pp = isD ? popD : popR;
    const lead = isD ? d - r : r - d;
    h = `<b>${isD ? dn : rn}</b><div class="sub">${isD ? 'Democratic' : 'Republican'}${c.office === 'PRES' ? '' : ' candidates, all races'}</div><table><tr><td>Votes</td><td>${fmt(v)}</td></tr><tr><td>Share of all votes</td><td>${pct(v / tot)}</td></tr><tr><td>Two-party share</td><td>${pct(v / (d + r))}</td></tr><tr><td>${lead >= 0 ? 'Lead' : 'Trails'} by</td><td>${fmt(Math.abs(lead))}</td></tr><tr><td>${un.many[0].toUpperCase() + un.many.slice(1)} carried</td><td>${fmt(won)}</td></tr><tr><td>People in those ${un.many}</td><td>${pct(pp / (popD + popR || 1))}</td></tr></table>`;
  }
  pvtip.innerHTML = h;
  pvtip.style.display = 'block';
  const tw = pvtip.offsetWidth;
  pvtip.style.left = Math.min(innerWidth - tw - 8, Math.max(8, ev.clientX - tw / 2)) + 'px';
  pvtip.style.top = document.getElementById('pvbar').getBoundingClientRect().bottom + 22 + 'px';
}
const pvbar = document.getElementById('pvbar');
pvbar.addEventListener('pointermove', e => {
  const s = e.target.closest('[data-p]');
  if (s) pvInfo(s.dataset.p, e);
  else pvtip.style.display = 'none';
});
pvbar.addEventListener('pointerleave', () => (pvtip.style.display = 'none'));
pvbar.addEventListener('pointerdown', e => {
  const s = e.target.closest('[data-p]');
  if (s) pvInfo(s.dataset.p, e);
});
document.addEventListener(
  'pointerdown',
  e => {
    if (!pvbar.contains(e.target)) pvtip.style.display = 'none';
  },
  true,
);
// ================= details sheet =================
const sheet = document.getElementById('sheet'),
  box = document.getElementById('sheetbox');
sheet.onclick = e => {
  if (e.target === sheet || e.target.closest('[data-action="close"]')) sheet.classList.remove('show');
};
document.getElementById('infobtn').onclick = () => {
  const c = st.contest,
    m = metricInfo(st.metric),
    meth = D.methods.find(x => x.key === st.method);
  let h = `<button class="x" data-action="close" aria-label="Close">×</button><h3>What you're seeing</h3><p><b>Size: ${m.label}.</b> ${m.desc}</p><p><b>Shape: ${meth.label}.</b> ${meth.desc}</p>`;
  if (st.gran === 'state')
    h += `<p><b>States.</b> Results, sizes and colors are summed to each state. ${st.method === 'contig' ? 'Counties keep their cartogram shapes but take their state’s color.' : 'Each state is one circle with area proportional to its total.'}</p>`;
  if (st.method === 'contig' && st.metric !== 'land') {
    const v = D.variants['contig|' + st.metric + '|' + wkeyFor(c, st.metric)];
    if (v)
      h += `<p>Accuracy here: average area error ${pct(v.err.wm)} (weighted by ${m.unit}); ${pct(v.err.w10)} of ${m.unit} are in counties within 10% of their exact size.</p>`;
  }
  if (st.cmp !== 'none')
    h += `<p><b>${st.method === 'contig' ? 'Outlines' : 'Rings'}: ${metricInfo(st.cmp).label}.</b> ${st.method === 'contig' ? 'Each ' + UNIT().one + '’s real geographic shape, centered on its spot in the map and scaled' : 'A ring around each circle'} to the size it would have if sized by ${metricInfo(st.cmp).label.toLowerCase()} (its share of the national total, same overall scale). Bigger than the fill means a larger share of ${metricInfo(st.cmp).unit} than of ${m.unit}.</p>`;
  h += `<p><b>Color.</b> Vote share is R ÷ (D + R), blended between blue and red in OKLab. Winner is fully blue or red. Where circles overlap, colors blend by each one's votes per unit of area. Gray means no race, or no data in the source.</p>`;
  h += `<p><b>Curve in the corner.</b> How much of the current size measure sits at each vote share. Hover to preview; click or drag to select a range (edges snap to exact ${UNIT().one} values, whole points and tenths); drag the middle to move it, the edges to resize. Scroll over it, or use + and −, to zoom the scale.</p><h3>This race</h3>`;
  if (c.note) h += `<p>${c.note}</p>`;
  if (c.gaps && c.gaps.length)
    h += `<p><b>Gaps in the source data:</b></p><ul>${c.gaps.map(g => `<li>${g}</li>`).join('')}</ul>`;
  if (c.statewide && c.statewide['02'])
    h += `<p>Alaska reports by state-house district, so every borough shows the statewide result.</p>`;
  h += `<p class="sub">Results: ${c.src}.</p>`;
  h += `<h3>Sources</h3><ul>${D.sources.map(s => `<li>${s}</li>`).join('')}</ul>`;
  box.innerHTML = h;
  sheet.classList.add('show');
};
