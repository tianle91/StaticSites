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
function syncYearRange() {
  [state.coverageStart,state.coverageEnd] = T.sharedBounds(DATA,state);
  const years = T.overlapYears(DATA,state);
  if (!years.length) throw new Error('The selected series have no years in common.');
  for (const key of ['from','to']) {
    // Preserve the chosen window where possible, clamping it when a series
    // switch makes an endpoint unavailable (e.g. annual prices stop in 2025).
    state[key] = years.reduce((best,year) => Math.abs(year-state[key]) < Math.abs(best-state[key]) ? year : best);
    $(key).replaceChildren();
    for (const year of years) {
      const option = text('option',String(year));
      option.value = year;
      $(key).append(option);
    }
    $(key).value = state[key];
  }
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
    row.append(text('span', metric.id === 'bank' ? 'Ontario bank arrears' : 'Toronto-area price'));
    const match = metric.series.map(series => T.nearestObservation(series,state.inspect,metric.frequency,state)).find(Boolean);
    const detail = text('span','','readout-value');
    if (match) detail.append(text('strong',format(match.value,metric.unit)),
      text('span',match.period.replace('-Q',' Q') + (match.status === 'forecast' ? ' · forecast' : ' · observed'),'readout-period'));
    else detail.append(text('span','No nearby observation','readout-period'));
    row.append(detail);
    $('readout').append(row);
  }
}

function render() {
  syncYearRange();
  selected = T.panels(DATA,state);
  $('chart').replaceChildren();
  width = Math.max(300,$('chart').clientWidth);
  layout = {left:width < 480 ? 58 : 76, right:width < 480 ? 65 : 76,
    top:32, bottom:45, height:width < 480 ? 330 : 390};
  layout.plotWidth = width-layout.left-layout.right;
  const {left,right,top,bottom,height} = layout;
  const plotBottom = height-bottom;
  const [start,end] = T.domain(state);
  const svg = svgNode('svg', {viewBox:`0 0 ${width} ${height}`,role:'img',tabindex:'0',
    'aria-label':`Ontario bank arrears on the left percentage axis and Toronto-area prices on the right Canadian-dollar axis, ${state.from}–${state.to}. Use left and right arrow keys to inspect months.`,
    'data-domain-start':start,'data-domain-end':end});
  $('chart').append(svg);
  for (let i=0;i<=4;i++) {
    const y=top+(plotBottom-top)*i/4;
    svg.append(svgNode('line',{x1:left,x2:width-right,y1:y,y2:y,class:'gridline'}));
  }
  for (const tick of ticks()) {
    const x=xAt(tick.date);
    svg.append(svgNode('line',{x1:x,x2:x,y1:top,y2:plotBottom,class:'vertical-grid'}));
    const anchor=x < left+10 ? 'start' : x > width-right-10 ? 'end' : 'middle';
    svg.append(svgNode('text',{x,y:height-24,'text-anchor':anchor,class:'axis'},tick.label));
  }
  svg.append(svgNode('text',{x:left+layout.plotWidth/2,y:height-5,'text-anchor':'middle',class:'axis-title'},'Calendar time'));
  const hasBank = selected[0].series.some(series => T.pointsFor(series,state).length);
  const hasPrices = selected[1].series.some(series => T.pointsFor(series,state).length);
  if (!hasBank || !hasPrices) {
    const missing = !hasBank && !hasPrices ? 'Neither series has observations' : !hasBank ? 'No bank arrears observations' : 'No house-price observations';
    svg.append(svgNode('text',{x:left+8,y:top+17,class:'axis'},missing+' in this range'));
  }
  selected.forEach(metric => {
    const isBank=metric.id === 'bank';
    const color=isBank ? 'var(--bank)' : 'var(--price)';
    const series=metric.series.map(series=>({...series,points:T.pointsFor(series,state)}));
    const values=series.flatMap(series=>series.points.map(point=>point.value));
    const high=values.length ? Math.max(...values)*1.1 || 1 : 1;
    // Both axes start at zero; their independent units are labelled and colored.
    // Keeping separate scales avoids treating a mortgage percentage as a price.
    const yAt=value=>plotBottom-value/high*(plotBottom-top);
    for (let i=0;i<=4 && values.length;i++) {
      const value=high*i/4;
      const label=isBank ? value.toFixed(high < 1 ? 2 : 1)+'%' : '$'+(value/1e6).toFixed(2)+'m';
      svg.append(svgNode('text',{x:isBank?left-9:width-right+9,y:yAt(value)+4,
        'text-anchor':isBank?'end':'start',class:isBank?'axis bank-axis':'axis price-axis'},label));
    }
    svg.append(svgNode('text',{x:isBank?left:width-right,y:15,'text-anchor':isBank?'start':'end',
      class:isBank?'axis-title bank-axis':'axis-title price-axis'},isBank?'Arrears (%)':'Price (CAD)'));
    series.forEach(series => {
      const observed=series.points.filter(point=>point.status === 'observed');
      const forecast=series.points.filter(point=>point.status === 'forecast');
      function path(points,dashed=false) {
        if (points.length<2) return;
        const d=points.map((point,i)=>(i?'L':'M')+xAt(T.stamp(point.period)).toFixed(2)+','+yAt(point.value).toFixed(2)).join(' ');
        svg.append(svgNode('path',{d,stroke:color,class:'series-line','data-metric':metric.id,
          ...(dashed?{'stroke-dasharray':'6 5','data-forecast':'true'}:{})}));
      }
      path(observed);
      if (forecast.length) path(observed.length?[observed.at(-1),...forecast]:forecast,true);
      series.points.forEach(point=>{
        const dot=svgNode('circle',{cx:xAt(T.stamp(point.period)),cy:yAt(point.value),r:2.5,fill:color,
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
  overlay.addEventListener('pointermove',event=>{
    const bounds=svg.getBoundingClientRect();
    const x=(event.clientX-bounds.left)/bounds.width*width;
    const date=start+Math.max(0,Math.min(1,(x-left)/layout.plotWidth))*(end-start);
    inspectMonth(new Date(date).toISOString().slice(0,7));
  });
  svg.addEventListener('keydown',event=>{
    if (!['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return;
    event.preventDefault();
    const [year,month]=state.inspect.split('-').map(Number);
    const date=new Date(Date.UTC(year,month-1+(event.key==='ArrowLeft'?-1:1),1));
    const period=event.key==='Home'?state.from+'-01':event.key==='End'?state.to+'-12':date.toISOString().slice(0,7);
    inspectMonth(period);
  });
  $('series-label').textContent=new Date(start).toISOString().slice(0,7)+'–'+new Date(end).toISOString().slice(0,7)+
    ' · Monthly data · Dashed bank line = CMHC forecast · Price coverage changes at 2024';
  $('definitions').replaceChildren();
  for (const metric of selected) $('definitions').append(text('h2',metric.title),text('p',metric.note));
  inspectMonth(state.inspect);
  document.querySelectorAll('[data-start]').forEach(button=>button.classList.toggle('active',
    button.dataset.start==='all'?state.from===T.overlapYears(DATA,state)[0]:state.from===Number(button.dataset.start)));
}
for (const key of ['from','to']) {
  $(key).onchange=()=>{
    state[key]=Number($(key).value);
    if (state.from>state.to) state[key==='from'?'to':'from']=state[key];
    $('from').value=state.from;
    $('to').value=state.to;
    render();
  };
}
document.querySelectorAll('[data-start]').forEach(button=>{
  button.onclick=()=>{
    const years=T.overlapYears(DATA,state);
    state.from=button.dataset.start==='all'?years[0]:Number(button.dataset.start);
    state.to=years.at(-1);
    render();
  };
});
$('download').onclick=()=>{
  const csv=T.selectionRows(DATA,state).map(row=>row.map(value=>'"'+String(value).replaceAll('"','""')+'"').join(',')).join('\r\n');
  const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));
  const link=document.createElement('a');
  link.href=url;
  link.download='ontario-arrears-prices.csv';
  link.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
};
let resizeTimer;
window.addEventListener('resize',()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(render,100);});
render();
