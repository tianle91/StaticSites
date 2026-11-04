'use strict';
const DATA = JSON.parse(document.getElementById('dataset').textContent);
const T = MortgageTimeline;
const $ = id => document.getElementById(id);
const state = { bank:true, prices:true, bankType:'monthly', priceType:'monthly',
  from:2021, to:2026, mode:'raw', forecast:true, inspect:'2026-06' };
let selected = [];
let width = 900;
let layout = {};

function text(tag, value, className) {
  const el = document.createElement(tag);
  el.textContent = value;
  if (className) el.className = className;
  return el;
}
function svgNode(tag, attrs = {}, value) {
  const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [key, val] of Object.entries(attrs)) el.setAttribute(key, String(val));
  if (value !== undefined) el.textContent = value;
  return el;
}
function format(value, unit) {
  return unit === 'CAD' ? '$' + Math.round(value).toLocaleString('en-CA') : value.toFixed(2) + '%';
}
function useSharedHistory() {
  [state.coverageStart,state.coverageEnd] = T.sharedBounds(DATA,state);
  const years = T.overlapYears(DATA,state);
  if (!years.length) throw new Error('The series have no years in common.');
  state.from = years[0];
  state.to = years.at(-1);
}
for (const source of DATA.sources) {
  const li = document.createElement('li');
  const link = text('a', source.name);
  link.href = source.url;
  link.target = '_blank';
  link.rel = 'noopener';
  li.append(link);
  $('source-list').append(li);
}
$('snapshot').textContent = 'Snapshot retrieved ' + DATA.retrieved_at.slice(0,10) +
  '. Rebuilds use committed data; refresh only with make data.';

function xAt(date) {
  const [start, end] = T.domain(state);
  return layout.left + (date - start) / (end - start) * layout.plotWidth;
}
function ticks() {
  const [start,end] = T.domain(state);
  const withStart = ticks => {
    if (!ticks.length || ticks[0].date > start) ticks.unshift({date:start,label:String(state.from)});
    return ticks;
  };
  const span = state.to - state.from + 1;
  if (span === 1) return withStart([0,3,6,9,12].map(month => ({date:Date.UTC(state.from,month,1),
    label:month === 12 ? String(state.to+1) : ['Jan','Apr','Jul','Oct'][month/3]}))
    .filter(tick => tick.date >= start && tick.date <= end));
  const target = Math.max(2, Math.floor(layout.plotWidth/70));
  const step = [1,2,5,10,20].find(step => step >= span/target) || 20;
  const result = [];
  for (let year = Math.ceil(state.from/step)*step; year <= state.to+1; year += step) {
    result.push({date:Date.UTC(year,0,1),label:String(year)});
  }
  return withStart(result.filter(tick => tick.date >= start && tick.date <= end));
}

function inspectMonth(period) {
  const [start,end] = T.domain(state);
  const min = new Date(start).toISOString().slice(0,7);
  const max = new Date(end).toISOString().slice(0,7);
  state.inspect = period < min ? min : period > max ? max : period;
  const cursor = document.querySelector('.shared-cursor');
  if (cursor) {
    const x = xAt(T.stamp(state.inspect));
    cursor.setAttribute('x1', x);
    cursor.setAttribute('x2', x);
  }
  $('inspect-period').textContent = 'Inspecting ' + state.inspect + ' · nearest published observations';
  $('readout').replaceChildren();
  for (const metric of selected) {
    const row = text('div', '', 'readout-row');
    row.dataset.color = metric.id === 'bank' ? 'var(--bank)' : 'var(--price)';
    row.append(text('span', metric.id === 'bank' ? 'Ontario bank arrears' : 'Toronto-area price'));
    const match = metric.series.map(series => T.nearestObservation(series,state.inspect,metric.frequency,state)).find(Boolean);
    const detail = text('span','','readout-value');
    if (match) {
      row.dataset.plotX = xAt(T.stamp(match.period));
      const index = metric.toIndex(match.value);
      row.dataset.plotY = layout.yAt(index);
      detail.append(text('strong', index.toFixed(1) + ' index · ' + format(match.value,metric.unit)),
        text('span',match.period.replace('-Q',' Q') + (match.status === 'forecast' ? ' · forecast' : ' · observed'),'readout-period'));
    } else detail.append(text('span','No nearby observation','readout-period'));
    row.append(detail);
    $('readout').append(row);
  }
}

function render() {
  useSharedHistory();
  const [start,end] = T.domain(state);
  const anchor = new Date(start).toISOString().slice(0,7);
  selected = T.panels(DATA,state).map(metric => {
    const series = metric.series.map(series => ({...series, points:T.pointsFor(series,state)}));
    // Both price vintages use the same base, so the coverage break does not reset the index.
    const base = series.flatMap(series => series.points).find(point => point.period === anchor)?.value;
    if (!Number.isFinite(base) || base <= 0) {
      throw new Error(metric.title + ' needs a positive observation in the base month ' + anchor);
    }
    return {...metric, series, toIndex: value => value / base * 100};
  });
  $('chart').replaceChildren();
  width = Math.max(300,$('chart').clientWidth);
  layout = {left:width < 480 ? 58 : 76, right:24,
    top:32, bottom:45, height:width < 480 ? 330 : 390};
  layout.plotWidth = width-layout.left-layout.right;
  const {left,right,top,bottom,height} = layout;
  const plotBottom = height-bottom;
  const values = selected.flatMap(metric => metric.series.flatMap(series =>
    series.points.map(point => metric.toIndex(point.value))));
  const minimum = Math.min(...values), maximum = Math.max(...values);
  const step = Math.max(5, Math.ceil((maximum - minimum) / 25) * 5);
  const low = 100 + Math.floor((minimum - 100) / step) * step - step;
  const high = 100 + Math.ceil((maximum - 100) / step) * step + step;
  const yAt = index => plotBottom - (index - low) / (high - low) * (plotBottom - top);
  layout.yAt = yAt;
  const axisTitle = 'Index (' + anchor + ' = 100)';
  const svg = svgNode('svg', {viewBox:`0 0 ${width} ${height}`,role:'img',tabindex:'0',
    'aria-label':`Ontario bank arrears and Toronto-area prices, both indexed to 100 in ${anchor}. Use left and right arrow keys to inspect months.`,
    'data-domain-start':start,'data-domain-end':end});
  $('chart').append(svg);
  svg.append(svgNode('text',{x:left,y:15,class:'axis-title'},axisTitle));
  for (let index = low; index <= high; index += step) {
    const y = yAt(index);
    svg.append(svgNode('line',{x1:left,x2:width-right,y1:y,y2:y,class:index === 100 ? 'index-base' : 'gridline'}));
    svg.append(svgNode('text',{x:left-9,y:y+4,'text-anchor':'end',class:'axis'},String(index)));
  }
  for (const tick of ticks()) {
    const x=xAt(tick.date);
    svg.append(svgNode('line',{x1:x,x2:x,y1:top,y2:plotBottom,class:'vertical-grid'}));
    const anchor=x < left+10 ? 'start' : x > width-right-10 ? 'end' : 'middle';
    svg.append(svgNode('text',{x,y:height-24,'text-anchor':anchor,class:'axis'},tick.label));
  }
  svg.append(svgNode('text',{x:left+layout.plotWidth/2,y:height-5,'text-anchor':'middle',class:'axis-title'},'Calendar time'));
  selected.forEach(metric => {
    const color=metric.id === 'bank' ? 'var(--bank)' : 'var(--price)';
    const yOf = point => yAt(metric.toIndex(point.value));
    metric.series.forEach(series => {
      const observed=series.points.filter(point=>point.status === 'observed');
      const forecast=series.points.filter(point=>point.status === 'forecast');
      function path(points,dashed=false) {
        if (points.length<2) return;
        const d=points.map((point,i)=>(i?'L':'M')+xAt(T.stamp(point.period)).toFixed(2)+','+yOf(point).toFixed(2)).join(' ');
        svg.append(svgNode('path',{d,stroke:color,class:'series-line','data-metric':metric.id,
          ...(dashed?{'stroke-dasharray':'6 5','data-forecast':'true'}:{})}));
      }
      path(observed);
      if (forecast.length) path(observed.length?[observed.at(-1),...forecast]:forecast,true);
      series.points.forEach(point=>{
        const dot=svgNode('circle',{cx:xAt(T.stamp(point.period)),cy:yOf(point),r:2.5,fill:color,
          'data-metric':metric.id,'data-period':point.period,'data-status':point.status});
        dot.append(svgNode('title',{},metric.title+' · '+point.period+' · '+format(point.value,metric.unit)+(point.status==='forecast'?' (forecast)':'')));
        svg.append(dot);
      });
    });
  });
  if (state.priceType==='monthly') {
    const boundary=Date.UTC(2024,0,1);
    if (boundary>start && boundary<end) {
      svg.append(svgNode('line',{x1:xAt(boundary),x2:xAt(boundary),y1:top,y2:plotBottom,
        stroke:'var(--muted)','stroke-dasharray':'3 5'}));
      // Keep the note outside the plotting area on narrow screens.
    }
  }
  svg.append(svgNode('line',{y1:top,y2:plotBottom,stroke:'var(--ink)','stroke-dasharray':'2 3',class:'shared-cursor'}));
  const overlay=svgNode('rect',{x:left,y:top,width:layout.plotWidth,height:plotBottom-top,fill:'transparent'});
  svg.append(overlay);
  plotHover(overlay, event=>{
    const bounds=svg.getBoundingClientRect();
    const x=(event.clientX-bounds.left)/bounds.width*width;
    const date = new Date(start + Math.max(0, Math.min(1, (x-left)/layout.plotWidth)) * (end-start));
    const year = date.getUTCFullYear();
    const month = date.getUTCMonth();
    const monthEnd = Date.UTC(year, month+1, 0);
    const before = date < monthEnd ? Date.UTC(year, month, 0) : monthEnd;
    const after = date < monthEnd ? monthEnd : Date.UTC(year, month+2, 0);
    const nearest = date - before <= after - date ? before : after;
    inspectMonth(new Date(nearest).toISOString().slice(0,7));
  });
  svg.addEventListener('keydown',event=>{
    if (!['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return;
    event.preventDefault();
    const [year,month]=state.inspect.split('-').map(Number);
    const date=new Date(Date.UTC(year,month-1+(event.key==='ArrowLeft'?-1:1),1));
    const period=event.key==='Home'?state.from+'-01':event.key==='End'?state.to+'-12':date.toISOString().slice(0,7);
    inspectMonth(period);
    plotHover.showAtCursor('.shared-cursor');
  });
  $('series-label').textContent=new Date(start).toISOString().slice(0,7)+'–'+new Date(end).toISOString().slice(0,7)+
    ' · Monthly data · Dashed bank line = CMHC forecast · Price coverage changes at 2024';
  $('definitions').replaceChildren();
  for (const metric of selected) $('definitions').append(text('h2',metric.title),text('p',metric.note));
  inspectMonth(state.inspect);
}
let resizeTimer;
window.addEventListener('resize',()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(render,100);});
render();
