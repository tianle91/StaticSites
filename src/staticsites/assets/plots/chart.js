/* Shared native SVG chart components embedded at build time. */
(function (root) {
  'use strict';
  const model = {
    panels(spec, choices) {
      return spec.panels.map(panel => panel.choices ? {...panel, ...panel.choices.find(choice =>
        choice.key === (choices[panel.id] || panel.defaultChoice))} : panel);
    },
    dates(spec) {
      return [...new Set(spec.panels.flatMap(panel => (panel.choices || [panel]).flatMap(choice =>
        choice.series.flatMap(series => series.points.map(point => point.date)))))].sort();
    },
    nearest(dates, value) {
      const target = new Date(value).getTime();
      return dates.reduce((best, date) => Math.abs(Date.parse(date)-target) < Math.abs(Date.parse(best)-target) ? date : best);
    },
    segments(points) {
      const result = [];
      let segment = null;
      for (const point of points) {
        if (point.value === null) { segment = null; continue; }
        const status = point.status || 'observed';
        if (!segment || segment.status !== status) {
          const previous = segment?.points.at(-1);
          segment = {status, points: previous ? [previous, point] : [point]};
          result.push(segment);
        } else segment.points.push(point);
      }
      return result;
    },
  };
  if (typeof module !== 'undefined' && module.exports) { module.exports = model; return; }
  root.ChartModel = model;
  const spec = JSON.parse(document.getElementById('chart-data').textContent);
  const $ = id => document.getElementById(id);
  const hidden = new Set();
  const choices = {};
  const dates = model.dates(spec);
  const start = Date.parse(spec.domain[0]), end = Date.parse(spec.domain[1]);
  let current = dates.at(-1);
  let panels = [];
  const panelScales = [];
  let width = 900, left = 76, right = 24;
  function text(tag, value, className) {
    const el = document.createElement(tag);
    el.textContent = value;
    if (className) el.className = className;
    return el;
  }
  function svg(tag, attributes = {}, value) {
    const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (const [key, val] of Object.entries(attributes)) el.setAttribute(key, String(val));
    if (value !== undefined) el.textContent = value;
    return el;
  }
  function x(value) { return left + (Date.parse(value)-start)/(end-start)*(width-left-right); }
  function format(value, unit) { return unit === '%' ? value.toFixed(2)+'%' : value.toFixed(1); }
  function ticks() {
    const first = new Date(start).getUTCFullYear(), last = new Date(end).getUTCFullYear();
    const step = [1,2,5,10,20].find(step => step >= (last-first)/Math.max(2,Math.floor((width-left-right)/80))) || 20;
    const result = [{date:spec.domain[0],label:String(first)}];
    for (let year = Math.ceil(first/step)*step; year <= last; year += step) {
      const date = year+'-01-01';
      if (Date.parse(date)>start && Date.parse(date)<end && x(date)-left>45) result.push({date,label:String(year)});
    }
    return result;
  }
  function inspect(date) {
    current = model.nearest(dates,date);
    $('inspect-period').textContent = 'Inspecting '+current+' · aligned observations';
    $('readout').replaceChildren();
    for (const [index, panel] of panels.entries()) for (const series of panel.series) {
      if (hidden.has(series.id)) continue;
      const point = series.points.find(point => point.date === current);
      const row = text('div','','readout-row');
      row.dataset.panel = index;
      row.dataset.color = series.color;
      row.append(text('span',series.name));
      const value = text('span','','readout-value');
      if (point && point.value !== null) {
        row.dataset.plotX = x(current);
        row.dataset.plotY = panelScales[index](point.value);
        value.append(text('strong',format(point.value,panel.unit)),text('span',panel.unit === '%'?'yield':'index','readout-unit'));
        if (Number.isFinite(point.original)) {
          const original = point.original.toLocaleString('en-US', {maximumFractionDigits: series.originalDecimals});
          value.append(text('span', original + ' ' + series.originalUnit, 'readout-original'));
        }
      } else value.append(text('span','No observation','readout-unit'));
      row.append(value); $('readout').append(row);
    }
    document.querySelectorAll('.inspection-cursor').forEach(cursor => {
      cursor.setAttribute('x1',x(current));cursor.setAttribute('x2',x(current));
    });
  }
  function legend() {
    $('chart-legend').replaceChildren();
    for (const panel of panels) for (const series of panel.series) {
      const button = text('button','','legend-item');
      const swatch = text('i',''); swatch.style.background = series.color;
      button.type = 'button'; button.append(swatch,document.createTextNode(series.name));
      button.setAttribute('aria-pressed',String(!hidden.has(series.id)));
      button.disabled = !hidden.has(series.id) && panel.series.filter(series => !hidden.has(series.id)).length === 1;
      button.onclick = () => { hidden.has(series.id)?hidden.delete(series.id):hidden.add(series.id);render(); };
      $('chart-legend').append(button);
    }
  }
  function draw(panel, target, index) {
    const height = panels.length === 1 ? (width<480?330:390) : 210;
    const top = 28, bottom = height-12;
    const visible = panel.series.filter(series => !hidden.has(series.id));
    const values = visible.flatMap(series => series.points.filter(point => point.value !== null).map(point => point.value));
    const minimum = Math.min(...values), maximum = Math.max(...values);
    const padding = (maximum-minimum || Math.max(1,Math.abs(maximum)))*.09;
    const low = panel.zero ? Math.min(0,minimum) : minimum-padding;
    const high = maximum+padding;
    const y = value => bottom-(value-low)/(high-low)*(bottom-top);
    panelScales[index] = y;
    const graphic = svg('svg',{viewBox:`0 0 ${width} ${height}`,role:'img',
      'aria-label':panel.title+'. '+panel.axis+'. '+spec.domain.join(' through '),
      'data-domain-start':spec.domain[0],'data-domain-end':spec.domain[1]});
    const clip = 'plot-clip-'+index;
    const defs = svg('defs');const clipPath = svg('clipPath',{id:clip});
    clipPath.append(svg('rect',{x:left,y:top,width:width-left-right,height:bottom-top}));defs.append(clipPath);graphic.append(defs);
    graphic.append(svg('text',{x:left,y:15,class:'axis-title'},panel.axis));
    for (const tick of ticks()) graphic.append(svg('line',{x1:x(tick.date),x2:x(tick.date),y1:top,y2:bottom,class:'vertical-grid'}));
    for (let i=0;i<=4;i++) {
      const value=low+(high-low)*i/4;
      graphic.append(svg('line',{x1:left,x2:width-right,y1:y(value),y2:y(value),class:'gridline'}));
      const label=panel.unit === '%' ? value.toFixed(1)+'%' : value.toFixed(0);
      graphic.append(svg('text',{x:left-9,y:y(value)+4,'text-anchor':'end',class:'axis'},label));
    }
    const plot=svg('g',{'clip-path':`url(#${clip})`});graphic.append(plot);
    for (const band of spec.bands || []) {
      const rect=svg('rect',{x:x(band.from),y:top,width:x(band.to)-x(band.from),height:bottom-top,fill:band.color,opacity:.09});
      rect.append(svg('title',{},band.label));plot.append(rect);
    }
    for (const event of spec.events || []) {
      if (Date.parse(event.date)<start || Date.parse(event.date)>end) continue;
      const line=svg('line',{x1:x(event.date),x2:x(event.date),y1:top,y2:bottom,stroke:'var(--muted)','stroke-dasharray':'2 5',opacity:.45});
      line.append(svg('title',{},event.date+' · '+event.label));plot.append(line);
    }
    if (panel.reference !== undefined && panel.reference>=low && panel.reference<=high) {
      plot.append(svg('line',{x1:left,x2:width-right,y1:y(panel.reference),y2:y(panel.reference),stroke:'var(--muted)','stroke-dasharray':'4 4'}));
    }
    if (spec.anchor) plot.append(svg('line',{x1:x(spec.anchor),x2:x(spec.anchor),y1:top,y2:bottom,stroke:'var(--ink)','stroke-dasharray':'2 4'}));
    for (const series of visible) {
      for (const segment of model.segments(series.points)) {
        if (segment.points.length<2) continue;
        const d=segment.points.map((point,i)=>(i?'L':'M')+x(point.date).toFixed(2)+','+y(point.value).toFixed(2)).join(' ');
        plot.append(svg('path',{d,stroke:series.color,class:'series-line',...(segment.status==='forecast'?{'stroke-dasharray':'6 5'}:{})}));
      }
      if (spec.markers !== false) for (const point of series.points) {
        if (point.value === null) continue;
        const marker=svg('circle',{cx:x(point.date),cy:y(point.value),r:2.4,fill:series.color});
        marker.append(svg('title',{},series.name+' · '+point.date+' · '+format(point.value,panel.unit)));plot.append(marker);
      }
    }
    graphic.append(svg('line',{x1:x(current),x2:x(current),y1:top,y2:bottom,stroke:'var(--ink)','stroke-dasharray':'2 3',class:'inspection-cursor','data-panel':index}));
    const overlay=svg('rect',{x:left,y:top,width:width-left-right,height:bottom-top,fill:'transparent'});graphic.append(overlay);
    const inspectPointer = event=>{
      const bounds=graphic.getBoundingClientRect();
      const px=(event.clientX-bounds.left)/bounds.width*width;
      const date=new Date(start+Math.max(0,Math.min(1,(px-left)/(width-left-right)))*(end-start));
      inspect(date);
    };
    plotHover(overlay, inspectPointer, String(index));
    target.append(graphic);
  }
  function render() {
    panels=model.panels(spec,choices);legend();
    $('chart').replaceChildren();width=Math.max(240,$('chart').clientWidth);left=width<480?58:76;right=24;
    panels.forEach((panel,index)=>{
      const section=text('section','','plot-panel');
      if (panels.length>1) section.append(text('h2',panel.title));
      if (panel.description) section.append(text('p',panel.description,'panel-description'));
      $('chart').append(section);draw(panel,section,index);
    });
    const axis=svg('svg',{viewBox:`0 0 ${width} 47`,role:'img','aria-label':'Shared calendar time axis'});
    for (const tick of ticks()) axis.append(svg('text',{x:x(tick.date),y:15,'text-anchor':tick.date===spec.domain[0]?'start':'middle',class:'axis'},tick.label));
    axis.append(svg('text',{x:left+(width-left-right)/2,y:37,'text-anchor':'middle',class:'axis-title'},'Calendar time'));
    $('chart').append(axis);inspect(current);
  }
  const options=$('chart-choices');
  for (const panel of spec.panels.filter(panel=>panel.choices?.length>1)) {
    const field=text('label','Liquidity denominator');
    const select=document.createElement('select');
    for (const choice of panel.choices) {const option=text('option',choice.label);option.value=choice.key;select.append(option);}
    select.value=panel.defaultChoice;
    select.onchange=()=>{choices[panel.id]=select.value;render();};field.append(select);options.append(field);
  }
  $('chart').addEventListener('keydown',event=>{
    if (!['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return;
    event.preventDefault();const index=dates.indexOf(current);
    const next=event.key==='Home'?0:event.key==='End'?dates.length-1:Math.max(0,Math.min(dates.length-1,index+(event.key==='ArrowLeft'?-1:1)));
    inspect(dates[next]);
    plotHover.showAtCursor('.inspection-cursor');
  });
  let resizeTimer;window.addEventListener('resize',()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(render,100);});
  render();
})(typeof globalThis==='undefined'?this:globalThis);
