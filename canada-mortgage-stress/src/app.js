'use strict';
const DATA = JSON.parse(document.getElementById('dataset').textContent);
const $ = id => document.getElementById(id);
const groups = Object.fromEntries(DATA.groups.map(g => [g.id, g]));
const colors = ['--teal','--orange','--blue','--purple','--gray','--red','--gold','--aqua'];
const state = {metric:'provinces', from:2020, to:2027, mode:'raw', forecast:true, compare:'prices', hidden:new Set()};
function text(tag, value, className) {const el=document.createElement(tag);el.textContent=value;if(className)el.className=className;return el;}
function stamp(period) {
  const q=period.match(/^(\d{4})-Q([1-4])$/);
  if(q) return Date.UTC(Number(q[1]),Number(q[2])*3,0);
  if(period.length===4) return Date.UTC(Number(period),11,31);
  const [y,m]=period.split('-').map(Number);return Date.UTC(y,m,0);
}
function format(value,unit,index=false) {return index?value.toFixed(1):unit==='CAD'?'$'+Math.round(value).toLocaleString('en-CA'):value.toFixed(2)+'%';}
function pointsFor(series) {return series.points.filter(p=>Number(p.period.slice(0,4))>=state.from && Number(p.period.slice(0,4))<=state.to && (state.forecast || p.status!=='forecast'));}
function displayed(series) {
  const points=pointsFor(series), base=points[0]?.value;
  return points.map(p=>({...p, y:state.mode==='index'?(base ? p.value/base*100 : null):p.value})).filter(p=>p.y!==null);
}
function extent(g) {const p=g.series.flatMap(s=>s.points).map(p=>p.period).sort();return p[0].replace('-Q',' Q')+' – '+p.at(-1).replace('-Q',' Q');}
function headline(label, group, name, detail) {
  const series=groups[group].series.find(s=>s.name===name), p=series.points.filter(p=>p.status==='observed').at(-1);
  const card=text('article','', 'headline');card.append(text('p',label,'label'),text('strong',format(p.value,groups[group].unit)),text('p',p.period.replace('-Q',' Q')+' · '+detail,'detail'));return card;
}
$('headlines').append(headline('ONTARIO · BANK MORTGAGE ARREARS','provinces','Ontario','90+ days overdue'),headline('GTHA · MIE BALANCES IN ARREARS','private','GTHA','90+ days · balance weighted'),headline('TORONTO AREA · MONTHLY SALE PRICE','prices','Expanded TRREB coverage (2024 onward)','TRREB average · nominal CAD'));
$('retrieved').textContent='Snapshot retrieved '+DATA.retrieved_at.slice(0,10);
$('snapshot').textContent='Source snapshot: '+DATA.retrieved_at+' · Built from committed inputs; no live requests.';
for(const g of DATA.groups){const o=text('option',g.title);o.value=g.id;$('metric').append(o);const tr=document.createElement('tr');tr.append(text('td',g.title),text('td',g.frequency),text('td',extent(g)),text('td',g.source));$('coverage').append(tr);}
for(let y=1980;y<=Math.max(...DATA.groups.flatMap(g=>g.series.flatMap(s=>s.points.map(p=>Number(p.period.slice(0,4))))));y++){for(const id of ['from','to']){const option=text('option',String(y));option.value=y;$(id).append(option);}}
$('from').value=state.from;$('to').value=state.to;
for(const gap of DATA.gaps){const el=text('article','','gap');el.append(text('p','DATA GAP','eyebrow'),text('h3',gap.metric),text('p',gap.detail));$('gaps').append(el);}
for(const source of DATA.sources){const li=document.createElement('li'),a=text('a',source.name);a.href=source.url;a.target='_blank';a.rel='noopener';li.append(a);$('source-list').append(li);}
function legend(g,target,interactive) {
  target.replaceChildren();
  g.series.forEach((s,i)=>{const button=text(interactive?'button':'span','','legend-item');const swatch=text('span','','swatch');swatch.style.setProperty('--series-color',`var(${colors[i%colors.length]})`);button.append(swatch,document.createTextNode(s.name));
    if(interactive){button.type='button';button.setAttribute('aria-pressed',String(!state.hidden.has(s.name)));button.onclick=()=>{state.hidden.has(s.name)?state.hidden.delete(s.name):state.hidden.add(s.name);render();};}
    else {button.style.cssText='display:inline-flex;align-items:center;gap:6px;font-size:12px';}
    target.append(button);
  });
}
function svgNode(tag,attrs={},value) {const el=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v] of Object.entries(attrs))el.setAttribute(k,String(v));if(value!==undefined)el.textContent=value;return el;}
function draw(g,target,domain,interactive=true) {
  target.replaceChildren();
  const series=g.series.map((s,i)=>({...s,color:`var(${colors[i%colors.length]})`,display:displayed(s)})).filter(s=>(!interactive||!state.hidden.has(s.name))&&s.display.length);
  if(!series.length){target.append(text('p','No observations in this selection. Choose another date range or enable a series.','chart-message'));return;}
  const width=Math.max(320,target.clientWidth),height=320,pad={l:76,r:22,t:32,b:48},w=width-pad.l-pad.r,h=height-pad.t-pad.b;
  const all=series.flatMap(s=>s.display.map(p=>p.y)),lo=state.mode==='index'?Math.max(0,Math.min(...all)*.92):0,hi=Math.max(...all)*1.09||1;
  const x=t=>pad.l+(t-domain[0])/(domain[1]-domain[0])*w, y=v=>pad.t+h-(v-lo)/(hi-lo)*h;
  const svg=svgNode('svg',{viewBox:`0 0 ${width} ${height}`,role:'img','aria-label':`${g.title}. ${state.mode==='index'?'Index: first visible value equals 100':g.unit}. ${g.frequency}. ${g.note}`});
  target.append(svg);
  svg.append(svgNode('text',{x:pad.l,y:15,class:'axis-title'},state.mode==='index'?'Index (first visible = 100)':g.unit==='CAD'?'Average sale price (CAD)':'90+ day arrears / delinquency (%)'));
  for(let i=0;i<=5;i++){const v=lo+(hi-lo)*i/5,yy=y(v);svg.append(svgNode('line',{x1:pad.l,x2:width-pad.r,y1:yy,y2:yy,class:'gridline'}));const label=state.mode==='index'?v.toFixed(0):g.unit==='CAD'?'$'+(v/1e6).toFixed(2)+'m':v.toFixed(hi<1?2:1)+'%';svg.append(svgNode('text',{x:pad.l-10,y:yy+4,'text-anchor':'end',class:'axis'},label));}
  for(let i=0;i<=5;i++){const t=domain[0]+(domain[1]-domain[0])*i/5,d=new Date(t);svg.append(svgNode('text',{x:x(t),y:height-26,'text-anchor':i===0?'start':i===5?'end':'middle',class:'axis'},domain[1]-domain[0]<864e5*730?d.toISOString().slice(0,7):String(d.getUTCFullYear())));}
  svg.append(svgNode('text',{x:pad.l+w/2,y:height-6,'text-anchor':'middle',class:'axis-title'},'Observation period (calendar date)'));
  if(g.id==='prices'){
    const boundary=Date.UTC(2024,0,1);if(boundary>domain[0]&&boundary<domain[1]){
      svg.append(svgNode('line',{x1:x(boundary),x2:x(boundary),y1:pad.t,y2:pad.t+h,stroke:'var(--muted)','stroke-dasharray':'3 5'}));
      svg.append(svgNode('text',{x:x(boundary)+5,y:pad.t+12,class:'axis'},'Coverage break'));
    }
  }
  series.forEach(s=>{
    const observed=s.display.filter(p=>p.status==='observed'),forecast=s.display.filter(p=>p.status==='forecast');
    const path=(points,dashed=false)=>{if(points.length<2)return;const d=points.map((p,i)=>(i?'L':'M')+x(stamp(p.period)).toFixed(2)+','+y(p.y).toFixed(2)).join(' ');svg.append(svgNode('path',{d,stroke:s.color,class:'series-line',...(dashed?{'stroke-dasharray':'6 5'}:{})}));};
    path(observed);if(forecast.length)path(observed.length?[observed.at(-1),...forecast]:forecast,true);
    s.display.forEach(p=>{const dot=svgNode('circle',{cx:x(stamp(p.period)),cy:y(p.y),r:2.4,fill:s.color});dot.append(svgNode('title',{},`${s.name} · ${p.period} · ${format(p.value,g.unit)}${p.status==='forecast'?' (forecast)':''}`));svg.append(dot);});
  });
  const cursor=svgNode('line',{y1:pad.t,y2:pad.t+h,stroke:'var(--muted)','stroke-dasharray':'2 3',visibility:'hidden'});svg.append(cursor);
  const overlay=svgNode('rect',{x:pad.l,y:pad.t,width:w,height:h,fill:'transparent'});svg.append(overlay);
  overlay.addEventListener('pointermove',event=>{
    const bounds=svg.getBoundingClientRect(),px=(event.clientX-bounds.left)/bounds.width*width,t=domain[0]+(px-pad.l)/w*(domain[1]-domain[0]);
    // Only report actual observations; do not extrapolate a series beyond its range.
    const nearest=series.map(s=>({s,p:s.display.reduce((a,b)=>Math.abs(stamp(a.period)-t)<Math.abs(stamp(b.period)-t)?a:b)})).filter(({p})=>Math.abs(x(stamp(p.period))-px)<28);
    if(!nearest.length){$('tooltip').hidden=true;cursor.setAttribute('visibility','hidden');return;}
    cursor.setAttribute('x1',px);cursor.setAttribute('x2',px);cursor.setAttribute('visibility','visible');
    const tip=$('tooltip');tip.replaceChildren(text('strong','Published observations'));
    nearest.forEach(({s,p})=>{const row=text('div','','tiprow');row.append(text('span',s.name+' · '+p.period),text('span',format(p.value,g.unit)+(p.status==='forecast'?' (forecast)':'')));tip.append(row);});
    tip.hidden=false;tip.style.left=Math.max(8,Math.min(event.clientX+14,innerWidth-tip.offsetWidth-12))+'px';tip.style.top=Math.max(8,Math.min(event.clientY+12,innerHeight-tip.offsetHeight-10))+'px';
  });
  overlay.addEventListener('pointerleave',()=>{$('tooltip').hidden=true;cursor.setAttribute('visibility','hidden');});
}
function render() {
  const g=groups[state.metric];
  $('chart-title').textContent=g.title;$('definition').textContent=g.note;$('frequency').textContent=g.frequency+' · '+(state.mode==='index'?'Indexed':g.unit);
  $('forecast-control').hidden=g.id!=='outlook';
  legend(g,$('legend'),true);
  const comp=state.compare!=='off' && !['prices','annual'].includes(g.id)?groups[state.compare]:null;
  const selected=[g,...(comp?[comp]:[])].flatMap(g=>g.series.flatMap(s=>pointsFor(s)));
  const domain=selected.length?[Math.min(...selected.map(p=>stamp(p.period))),Math.max(...selected.map(p=>stamp(p.period)))]:[Date.UTC(state.from,0,1),Date.UTC(state.to,11,31)];
  if(domain[0]===domain[1]){domain[0]-=864e5*30;domain[1]+=864e5*30;}
  draw(g,$('primary'),domain);
  $('caption').textContent=`Source: ${g.source} · Available: ${extent(g)} · ${state.from}–${state.to} selection. ${g.id==='outlook'?'Dashed = Fall 2026 CMHC forecast.':''}${state.mode==='index'?' Each series is rebased independently to its first visible observation; levels are not directly comparable.':''}`;
  $('comparison').hidden=!comp;
  if(comp){$('comparison-note').textContent=comp.note;legend(comp,$('comparison-legend'),false);draw(comp,$('secondary'),domain,false);$('comparison-caption').textContent=`Source: ${comp.source} · Available: ${extent(comp)} · Same horizontal date scale as the chart above.`;}
  $('compare').disabled=['prices','annual'].includes(g.id);
  document.querySelectorAll('[data-start]').forEach(button=>button.classList.toggle('active',button.dataset.start==='all'?state.from===1980:state.from===Number(button.dataset.start)));
}
$('metric').onchange=()=>{state.metric=$('metric').value;state.hidden=new Set();if(state.metric==='outlook')groups.outlook.series.forEach(s=>{if(!['Ontario','Canada'].includes(s.name))state.hidden.add(s.name);});render();};
for(const key of ['from','to'])$(key).onchange=()=>{state[key]=Number($(key).value);if(state.from>state.to){state[key==='from'?'to':'from']=state[key];$('from').value=state.from;$('to').value=state.to;}render();};
$('mode').onchange=()=>{state.mode=$('mode').value;render();};$('forecast').onchange=()=>{state.forecast=$('forecast').checked;render();};$('compare').onchange=()=>{state.compare=$('compare').value;render();};
document.querySelectorAll('[data-start]').forEach(b=>b.onclick=()=>{state.from=b.dataset.start==='all'?1980:Number(b.dataset.start);state.to=Number($('to').lastElementChild.value);$('from').value=state.from;$('to').value=state.to;render();});
$('download').onclick=()=>{const rows=[['metric','series','period','value','unit','status','source']];for(const g of DATA.groups)for(const s of g.series)for(const p of s.points)rows.push([g.title,s.name,p.period,p.value,g.unit,p.status,p.source||g.source_url]);const csv=rows.map(row=>row.map(v=>'"'+String(v).replaceAll('"','""')+'"').join(',')).join('\r\n');const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='canada-mortgage-stress.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
let resizeTimer;window.addEventListener('resize',()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(render,100);});
render();
