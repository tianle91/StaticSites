/* Show the same observations beside the pointer and in the persistent readout. */
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
  chart.addEventListener('keydown', hide);
  window.addEventListener('resize', hide);

  return (overlay, inspect) => {
    function show(event) {
      inspect(event);
      const title = document.createElement('div');
      title.className = 'plot-hover-period';
      title.textContent = period.textContent;
      tooltip.replaceChildren(title, ...Array.from(readout.children, row => row.cloneNode(true)));
      if (!tooltip.isConnected) chart.append(tooltip);
      tooltip.hidden = false;

      const bounds = chart.getBoundingClientRect();
      const gap = 14;
      const x = event.clientX - bounds.left;
      const w = tooltip.offsetWidth;
      const h = tooltip.offsetHeight;
      const left = x + gap + w <= bounds.width ? x + gap : x - gap - w;
      const below = event.clientY + gap;
      const above = event.clientY - gap - h;
      const y = below + h <= window.innerHeight ? below : above;
      tooltip.style.left = Math.max(0, Math.min(left, bounds.width - w)) + 'px';
      tooltip.style.top = Math.max(4, Math.min(y, window.innerHeight - h - 4)) - bounds.top + 'px';
    }
    overlay.addEventListener('pointermove', event => {
      if (event.pointerType !== 'touch') show(event);
    });
    overlay.addEventListener('pointerdown', show);
    overlay.addEventListener('pointerleave', event => {
      if (event.pointerType !== 'touch') hide();
    });
    overlay.addEventListener('pointercancel', hide);
  };
})();
