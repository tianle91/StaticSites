/* Show the observations announced by the chart's live region. */
const plotHover = (() => {
  const chart = document.getElementById('chart');
  const period = document.getElementById('inspect-period');
  const readout = document.getElementById('readout');
  const tooltip = document.createElement('div');
  tooltip.className = 'plot-hover';
  tooltip.setAttribute('aria-hidden', 'true');
  tooltip.hidden = true;
  const marker = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
  marker.classList.add('plot-hover-marker');
  marker.setAttribute('r', '5');
  marker.setAttribute('aria-hidden', 'true');
  const hide = () => {
    tooltip.hidden = true;
    marker.remove();
  };
  document.addEventListener('pointerdown', event => {
    if (!chart.contains(event.target)) hide();
  });
  chart.addEventListener('keydown', event => {
    if (event.key === 'Escape') hide();
  });
  chart.addEventListener('focusout', event => {
    if (!chart.contains(event.relatedTarget)) hide();
  });
  window.addEventListener('resize', hide);

  function show(clientX, clientY, panel, pointerY, graphic) {
    const title = document.createElement('div');
    title.className = 'plot-hover-period';
    title.textContent = period.textContent;
    const rows = Array.from(readout.children).filter(row => row.dataset.panel === panel);
    let closest;
    let minDistance = Infinity;
    for (const row of rows) {
      const distance = Math.abs(Number(row.dataset.plotY) - pointerY);
      if (distance < minDistance) {
        closest = row;
        minDistance = distance;
      }
    }
    if (closest && graphic) {
      marker.setAttribute('cx', closest.dataset.plotX);
      marker.setAttribute('cy', closest.dataset.plotY);
      marker.setAttribute('fill', closest.dataset.color);
      if (marker.parentNode !== graphic) graphic.append(marker);
    } else {
      marker.remove();
    }
    const copies = rows.map(row => {
      const copy = row.cloneNode(true);
      const dot = document.createElement('span');
      dot.className = 'plot-hover-dot';
      dot.style.backgroundColor = row.dataset.color;
      copy.firstElementChild.prepend(dot);
      if (row === closest) copy.firstElementChild.classList.add('plot-hover-closest');
      return copy;
    });
    tooltip.replaceChildren(title, ...copies);
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

  function bind(overlay, inspect, panel) {
    function inspectPointer(event) {
      inspect(event);
      const transform = overlay.getScreenCTM();
      const pointer = new DOMPoint(event.clientX, event.clientY);
      const pointerY = transform ? pointer.matrixTransform(transform.inverse()).y : undefined;
      show(event.clientX, event.clientY, panel, pointerY, overlay.ownerSVGElement);
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
    for (const guide of chart.querySelectorAll(selector)) {
      const bounds = guide.getBoundingClientRect();
      if (bounds.bottom > 0 && bounds.top < window.innerHeight) {
        show(bounds.left, Math.max(0, bounds.top) + 12, guide.dataset.panel);
        break;
      }
    }
  };
  return bind;
})();
