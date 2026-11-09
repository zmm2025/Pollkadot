// Number and label formatting shared by the tooltips, header and details sheet.

export const fmt = n => Math.round(n).toLocaleString('en-US');
export const pct = x => (100 * x).toFixed(1) + '%';
export const OFF = { PRES: 'President', SEN: 'Senate', HOUSE: 'House', GOV: 'Governor' };
