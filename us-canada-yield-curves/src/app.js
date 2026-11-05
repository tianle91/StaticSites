'use strict';
const DATA = JSON.parse(document.getElementById('dataset').textContent);
const $ = id => document.getElementById(id);
let current = DATA.tenors.findIndex(tenor => tenor.label === '10Y');
let layout;
let plotted = [];
const history = DATA.history || Object.fromEntries(DATA.series.map(series => [series.id, {[DATA.date]: series.yields}]));
const countryDates = Object.fromEntries(DATA.series.map(series => [series.id, Object.keys(history[series.id]).sort()]));
const latestDate = DATA.series.map(series => countryDates[series.id].at(-1)).sort().at(-1);
const offsets = [
  {key:'latest', label:'Latest', months:0, strength:1},
  {key:'1m', label:'−1m', months:1, strength:.84},
  {key:'3m', label:'−3m', months:3, strength:.72},
  {key:'6m', label:'−6m', months:6, strength:.62},
  {key:'1y', label:'−1y', months:12, strength:.52},
  {key:'2y', label:'−2y', months:24, strength:.42},
  {key:'5y', label:'−5y', months:60, strength:.32},
  {key:'10y', label:'−10y', months:120, strength:.22},
];
const selectedOffsets = new Set(['latest', '1y', '5y']);

function offsetDate(day, months) {
  const source = new Date(day + 'T00:00:00Z');
  const target = new Date(Date.UTC(source.getUTCFullYear(), source.getUTCMonth() - months, 1));
  const lastDay = new Date(Date.UTC(target.getUTCFullYear(), target.getUTCMonth() + 1, 0)).getUTCDate();
  target.setUTCDate(Math.min(source.getUTCDate(), lastDay));
  return target.toISOString().slice(0, 10);
}
function curveColor(color, strength) {
  const channels = color.slice(1).match(/../g).map(channel => parseInt(channel, 16));
  return '#' + channels.map(channel => Math.round(255 + (channel - 255) * strength)
    .toString(16).padStart(2, '0')).join('');
}
function seriesAt(offset) {
  const target = offsetDate(latestDate, offset.months);
  return DATA.series.map(series => {
    const day = countryDates[series.id].findLast(day => day <= target);
    const overnightRows = DATA.overnight_history?.[series.id] || {};
    const overnightDate = Object.keys(overnightRows).sort().at(-1);
    return {
      ...series, country:series.id, date:day, label:offset.label, offset:offset.key,
      comparison:offset.months > 0, color:curveColor(series.color, offset.strength),
      yields:history[series.id][day] || DATA.tenors.map(() => null),
      overnight:offset.months === 0 ? overnightRows[overnightDate] : null,
      overnightDate,
    };
  });
}
function renderOffsets() {
  $('offset-controls').replaceChildren();
  for (const offset of offsets) {
    const button = text('button', '', 'offset-button');
    button.type = 'button';
    button.dataset.offset = offset.key;
    button.setAttribute('aria-pressed', String(selectedOffsets.has(offset.key)));
    button.disabled = offset.key === 'latest';
    for (const series of DATA.series) {
      const swatch = text('i', '');
      swatch.style.background = curveColor(series.color, offset.strength);
      button.append(swatch);
    }
    button.append(document.createTextNode(offset.label));
    button.onclick = () => {
      if (selectedOffsets.has(offset.key)) selectedOffsets.delete(offset.key);
      else selectedOffsets.add(offset.key);
      render();
      $('offset-controls').querySelector('[data-offset="' + offset.key + '"]').focus();
    };
    $('offset-controls').append(button);
  }
}

function text(tag, value, className) {
  const element = document.createElement(tag);
  element.textContent = value;
  if (className) element.className = className;
  return element;
}
function svg(tag, attributes = {}, value) {
  const element = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [name, value] of Object.entries(attributes)) element.setAttribute(name, value);
  if (value !== undefined) element.textContent = value;
  return element;
}
function x(index) {
  const years = DATA.tenors[index].years;
  const first = DATA.tenors[0].years;
  const last = DATA.tenors.at(-1).years;
  return layout.left + Math.log(years / first) / Math.log(last / first) * layout.plotWidth;
}
function y(value) {
  return layout.bottom - (value - layout.low) / (layout.high - layout.low) * layout.plotHeight;
}
function readoutRow(series, name, value, index) {
  const row = text('div', '', 'readout-row');
  row.dataset.color = series.color;
  row.dataset.panel = series.country;
  row.dataset.country = series.country;
  row.dataset.date = series.date || '';
  row.dataset.offset = series.offset;
  row.dataset.kind = series.kind || 'curve';
  if (Number.isFinite(value)) {
    row.dataset.plotX = x(index);
    row.dataset.plotY = y(value);
  }
  const detail = text('span', '', 'readout-value');
  if (Number.isFinite(value)) detail.append(text('strong', value.toFixed(2) + '%'));
  else detail.append(text('span', 'No observation', 'readout-unit'));
  row.append(text('span', name), detail);
  return row;
}
function inspect(index) {
  current = index;
  const label = DATA.tenors[index].label;
  $('inspect-period').textContent = label + ' maturity';
  $('readout').replaceChildren();
  for (const series of plotted) {
    const name = series.name + ' · ' + series.label + (series.country === 'canada' && index === DATA.tenors.length - 1 ? ' · long-term' : '');
    $('readout').append(readoutRow(series, name, series.yields[index], index));
    if (!series.comparison && series.overnightName) {
      const reference = {...series, date:series.overnightDate, kind:'overnight'};
      $('readout').append(readoutRow(reference, series.overnightName + ' · Latest', series.overnight, index));
    }
  }
  document.querySelectorAll('.inspection-cursor').forEach(cursor => {
    cursor.setAttribute('x1', x(index));
    cursor.setAttribute('x2', x(index));
  });
}
function render() {
  plotted = offsets.filter(offset => selectedOffsets.has(offset.key)).flatMap(seriesAt);
  $('curve-date').textContent = 'Latest available data · ' + latestDate;
  renderOffsets();
  $('missing-curves').textContent = plotted.filter(series => series.yields.every(value => value === null))
    .map(series => series.name + ' · ' + series.label + ' is unavailable.').join(' ');
  $('chart').replaceChildren();
  const panels = DATA.series.map(country => {
    const panel = text('section', '', 'country-panel');
    panel.dataset.country = country.id;
    panel.tabIndex = 0;
    panel.setAttribute('role', 'group');
    panel.setAttribute('aria-label', country.name + ' yield curves. Use arrow keys to inspect maturities.');
    const heading = text('h2', '');
    const swatch = text('i', '');
    swatch.style.background = country.color;
    heading.append(swatch, document.createTextNode(country.name));
    panel.append(heading);
    $('chart').append(panel);
    return panel;
  });
  const width = Math.max(240, panels[0].clientWidth);
  const height = width < 480 ? 330 : 360;
  const values = plotted.flatMap(series => [...series.yields, series.overnight]).filter(Number.isFinite);
  const low = 0;
  const tickStep = Math.max(.5, Math.ceil((Math.max(0, ...values) + .15) / 6 * 2) / 2);
  const high = Math.ceil((Math.max(0, ...values) + .15) / tickStep) * tickStep;
  layout = {left:54, plotWidth:width-78, bottom:height-56, plotHeight:height-88, low, high};
  DATA.series.forEach((country, index) => draw(country, panels[index], width, height, tickStep));
  inspect(current);
  $('curve-observation-dates').replaceChildren();
  for (const series of plotted) {
    $('curve-observation-dates').append(text('li', series.name + ' · ' + series.label + ' · ' + (series.date || 'Unavailable')));
    if (!series.comparison && series.overnightName) {
      $('curve-observation-dates').append(text('li', series.overnightName + ' · Latest · ' + (series.overnightDate || 'Unavailable')));
    }
  }
  $('curve-summary').replaceChildren();
  const twoYear = DATA.tenors.findIndex(tenor => tenor.label === '2Y');
  const tenYear = DATA.tenors.findIndex(tenor => tenor.label === '10Y');
  for (const series of plotted) {
    if (series.comparison) continue;
    const spread = series.yields[tenYear] === null || series.yields[twoYear] === null
      ? null : Math.round((series.yields[tenYear] - series.yields[twoYear])*100);
    const card = text('p', series.name + ' · ' + series.label + ' · 10Y minus 2Y');
    card.append(text('strong', spread === null ? 'Unavailable' : (spread > 0 ? '+' : '') + spread + ' bp'));
    $('curve-summary').append(card);
  }
}
function draw(country, panel, width, height, tickStep) {
  const {low, high} = layout;
  const graphic = svg('svg', {viewBox:`0 0 ${width} ${height}`, role:'img',
    'aria-label':country.name + ' latest and historical yield curves' + '. Yield starts at zero percent. Maturity uses a logarithmic scale.'});
  panel.append(graphic);
  graphic.append(svg('text', {x:layout.left, y:16, class:'axis-title'}, 'Yield (%)'));
  for (let value = low; value <= high + .001; value += tickStep) {
    graphic.append(svg('line', {x1:layout.left, x2:width-24, y1:y(value), y2:y(value), class:'gridline'}));
    graphic.append(svg('text', {x:layout.left-9, y:y(value)+4, 'text-anchor':'end', class:'axis'}, value.toFixed(1)+'%'));
  }
  DATA.tenors.forEach((tenor, index) => {
    graphic.append(svg('line', {x1:x(index), x2:x(index), y1:32, y2:layout.bottom, class:'vertical-grid'}));
    // Alternate label rows on mobile to keep short maturity labels readable.
    const tickY = height - 34 + (width < 480 && index % 2 === 1 ? 14 : 0);
    graphic.append(svg('text', {x:x(index), y:tickY, class:'axis',
      'text-anchor':index === 0 ? 'start' : index === DATA.tenors.length - 1 ? 'end' : 'middle'}, tenor.label));
  });
  graphic.append(svg('text', {x:layout.left+layout.plotWidth/2, y:height-5,
    'text-anchor':'middle', class:'axis-title'}, 'Maturity (logarithmic scale)'));
  for (const series of [...plotted].reverse()) {
    if (series.country !== country.id) continue;
    if (Number.isFinite(series.overnight)) {
      graphic.append(svg('line', {x1:layout.left, x2:width-24,
        y1:y(series.overnight), y2:y(series.overnight), stroke:series.color,
        'stroke-dasharray':'6 4', class:'overnight-line'}));
      graphic.append(svg('text', {x:width-24, y:y(series.overnight)-6,
        'text-anchor':'end', fill:series.color, class:'overnight-label'},
        series.overnightName + ' ' + series.overnight.toFixed(2) + '%'));
    }
    const commands = [];
    let connected = false;
    series.yields.forEach((value, index) => {
      if (value === null) { connected = false; return; }
      commands.push((connected ? 'L' : 'M') + x(index) + ',' + y(value));
      connected = true;
    });
    const d = commands.join(' ');
    if (d) graphic.append(svg('path', {d, stroke:series.color, class:'series-line',
      'data-country':series.country, 'data-date':series.date, 'data-offset':series.offset}));
    series.yields.forEach((value, index) => {
      if (value === null) return;
      graphic.append(svg('circle', {cx:x(index), cy:y(value), r:2.5, fill:series.color}));
    });
  }
  graphic.append(svg('line', {y1:32, y2:layout.bottom, stroke:'var(--ink)',
    'stroke-dasharray':'2 3', class:'inspection-cursor', 'data-panel':country.id}));
  const overlay = svg('rect', {x:layout.left, y:32, width:layout.plotWidth,
    height:layout.plotHeight, fill:'transparent'});
  graphic.append(overlay);
  plotHover(overlay, event => {
    const pointer = new DOMPoint(event.clientX, event.clientY).matrixTransform(graphic.getScreenCTM().inverse());
    const nearest = DATA.tenors.reduce((best, tenor, index) =>
      Math.abs(x(index)-pointer.x) < Math.abs(x(best)-pointer.x) ? index : best, 0);
    inspect(nearest);
  }, country.id);
}

$('retrieved').textContent = 'Snapshot retrieved ' + DATA.retrieved_at.slice(0, 10) + '.';
$('coverage').textContent = 'Latest complete source dates · US ' + DATA.latest_available.us + ' · Canada ' + DATA.latest_available.canada + '.';
for (const source of DATA.sources) {
  const item = text('li', '');
  const link = text('a', source.name);
  link.href = source.url;
  item.append(link);
  $('sources').append(item);
}
$('chart').addEventListener('keydown', event => {
  if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
  event.preventDefault();
  if (event.key === 'Home') current = 0;
  else if (event.key === 'End') current = DATA.tenors.length-1;
  else current = Math.max(0, Math.min(DATA.tenors.length-1, current + (event.key === 'ArrowRight' ? 1 : -1)));
  inspect(current);
  const country = event.target.closest('.country-panel')?.dataset.country || DATA.series[0].id;
  plotHover.showAtCursor('.inspection-cursor[data-panel="' + country + '"]');
});
let resizeTimer;
window.addEventListener('resize', () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(render, 100);
});
render();
