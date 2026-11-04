/* Show the observations announced by the chart's live region. */
const plotHover = (() => {
  const chart = document.getElementById('chart');
  const period = document.getElementById('inspect-period');
  const readout = document.getElementById('readout');
  const tooltip = document.createElement('div');
  tooltip.className = 'plot-hover';
  tooltip.setAttribute('aria-hidden', 'true');
  tooltip.hidden = true;
  const hide = () => { tooltip.hidden = true; };
  document.addEventListener('pointerdown', event => {
    if (!chart.contains(event.target)) hide();
  });
  chart.addEventListener('keydown', event => {
    if (event.key === 'Escape') hide();
  });
  chart.addEventListener('focusout', hide);
  window.addEventListener('resize', hide);

  function show(clientX, clientY) {
    const title = document.createElement('div');
    title.className = 'plot-hover-period';
    title.textContent = period.textContent;
    tooltip.replaceChildren(title, ...Array.from(readout.children, row => row.cloneNode(true)));
    if (!tooltip.isConnected) chart.append(tooltip);
    tooltip.hidden = false;

    const bounds = chart.getBoundingClientRect();
    const gap = 14;
    const x = clientX - bounds.left;
    const w = tooltip.offsetWidth;
    const h = tooltip.offsetHeight;
    const left = x + gap + w <= bounds.width ? x + gap : x - gap - w;
    const below = clientY + gap;
    const above = clientY - gap - h;
    const y = below + h <= window.innerHeight ? below : above;
    tooltip.style.left = Math.max(0, Math.min(left, bounds.width - w)) + 'px';
    tooltip.style.top = Math.max(4, Math.min(y, window.innerHeight - h - 4)) - bounds.top + 'px';
  }

  function bind(overlay, inspect) {
    function inspectPointer(event) {
      inspect(event);
      show(event.clientX, event.clientY);
    }
    overlay.addEventListener('pointermove', event => {
      if (event.pointerType !== 'touch') inspectPointer(event);
    });
    overlay.addEventListener('pointerdown', inspectPointer);
    overlay.addEventListener('pointerleave', event => {
      if (event.pointerType !== 'touch') hide();
    });
    overlay.addEventListener('pointercancel', hide);
  }

  bind.showAtCursor = selector => {
    const guides = Array.from(chart.querySelectorAll(selector), guide => guide.getBoundingClientRect());
    const visible = guides.find(guide => guide.bottom > 0 && guide.top < window.innerHeight);
    if (visible) show(visible.left, Math.max(0, visible.top) + 12);
  };
  return bind;
})();
