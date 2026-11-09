// Right/middle-button drags pan the map and the curve. Browsers open the context menu when the right button is
// released, even if that happens outside the element that started the drag, so suppress it for a moment afterwards.

let auxDrag = false,
  suppressCtxUntil = 0;
document.addEventListener(
  'contextmenu',
  e => {
    if (auxDrag || performance.now() < suppressCtxUntil) e.preventDefault();
  },
  true,
);
export function beginAuxDrag() {
  auxDrag = true;
}
function endAuxDrag() {
  if (auxDrag) {
    auxDrag = false;
    suppressCtxUntil = performance.now() + 400;
  }
}
window.addEventListener('pointerup', endAuxDrag, true);
window.addEventListener('pointercancel', endAuxDrag, true);
