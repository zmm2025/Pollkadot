// OKLab color math and the blue-to-red color ramp.

// ================= OKLab =================
function s2l(c) {
  c /= 255;
  return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
}
function l2s(c) {
  c = c <= 0.0031308 ? 12.92 * c : 1.055 * Math.pow(c, 1 / 2.4) - 0.055;
  return Math.max(0, Math.min(255, Math.round(c * 255)));
}
function hexToLab(h) {
  const n = parseInt(h.slice(1), 16);
  const r = s2l((n >> 16) & 255),
    g = s2l((n >> 8) & 255),
    b = s2l(n & 255);
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b),
    m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b),
    s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
  return [
    0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s,
    1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s,
    0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s,
  ];
}
function labToRgb(L, a, b) {
  const l = Math.pow(L + 0.3963377774 * a + 0.2158037573 * b, 3),
    m = Math.pow(L - 0.1055613458 * a - 0.0638541728 * b, 3),
    s = Math.pow(L - 0.0894841775 * a - 1.291485548 * b, 3);
  return [
    l2s(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s),
    l2s(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s),
    l2s(-0.0041960695 * l - 0.7034186147 * m + 1.707614701 * s),
  ];
}
export const dark = matchMedia('(prefers-color-scheme: dark)').matches;
const DEM = hexToLab('#2f6fd8'),
  REP = hexToLab('#d63b3b'),
  NONE = hexToLab(dark ? '#3a3a40' : '#d9d7d2');
export const LUTN = 1024,
  LUT = new Uint8ClampedArray(3 * (LUTN + 1));
for (let i = 0; i <= LUTN; i++) {
  const t = i / LUTN;
  const c = labToRgb(DEM[0] + (REP[0] - DEM[0]) * t, DEM[1] + (REP[1] - DEM[1]) * t, DEM[2] + (REP[2] - DEM[2]) * t);
  LUT[3 * i] = c[0];
  LUT[3 * i + 1] = c[1];
  LUT[3 * i + 2] = c[2];
}
export const NONERGB = labToRgb(NONE[0], NONE[1], NONE[2]);
export const lutCss = t => {
  const i = 3 * Math.round(Math.min(1, Math.max(0, t)) * LUTN);
  return `rgb(${LUT[i]},${LUT[i + 1]},${LUT[i + 2]})`;
};
export function colorOf(t, none) {
  const L = [DEM[0] + (REP[0] - DEM[0]) * t, DEM[1] + (REP[1] - DEM[1]) * t, DEM[2] + (REP[2] - DEM[2]) * t];
  if (none > 0) for (let k = 0; k < 3; k++) L[k] += (NONE[k] - L[k]) * none;
  const c = labToRgb(L[0], L[1], L[2]);
  return 'rgb(' + c[0] + ',' + c[1] + ',' + c[2] + ')';
}
