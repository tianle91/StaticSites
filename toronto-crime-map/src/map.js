/* Pure helpers keep filtering and counting consistent across pins and summary. */
function selectRows(rows, filters) {
  return rows.filter(r => r.source === filters.source &&
    filters.categories.has(r.category) &&
    (!filters.neighbourhood || r.neighbourhood === filters.neighbourhood) &&
    (!filters.query || [r.offence, r.event_id, r.division, r.neighbourhood, r.premises].join(' ').toLowerCase().includes(filters.query)) &&
    r[filters.basis] && (!filters.from || r[filters.basis] >= filters.from) &&
    (!filters.to || r[filters.basis] <= filters.to));
}
function summarize(rows) {
  const groups = new Map();
  for (const r of rows) {
    if (!groups.has(r.neighbourhood)) groups.set(r.neighbourhood, {name:r.neighbourhood, count:0, incidents:new Set()});
    const g = groups.get(r.neighbourhood); g.count++; g.incidents.add(r.event_id);
  }
  return [...groups.values()].sort((a,b) => b.count-a.count || a.name.localeCompare(b.name));
}
// Use the same locate-control and blue-dot convention as the other maps.
// Keep this outside the crime cluster layer so filters do not remove the marker.
function addLocationControl(map, status) {
  let button, youMarker = null, accuracyCircle = null;
  function finish(message) {
    button.disabled = false;
    button.removeAttribute('aria-busy');
    status.textContent = message;
  }
  function locate() {
    if (!navigator.geolocation) {
      status.textContent = 'Location is unavailable. Use a browser with location support on HTTPS or localhost.';
      return;
    }
    button.disabled = true;
    button.setAttribute('aria-busy', 'true');
    status.textContent = 'Finding your location…';
    navigator.geolocation.getCurrentPosition(pos => {
      const ll = [pos.coords.latitude, pos.coords.longitude];
      if (youMarker) youMarker.setLatLng(ll);
      else youMarker = L.circleMarker(ll, {radius:8, color:'#fff', weight:2,
        fillColor:'#2b8cbe', fillOpacity:1}).addTo(map).bindPopup('You are here');
      const accuracy = pos.coords.accuracy;
      if (Number.isFinite(accuracy) && accuracy > 0) {
        if (accuracyCircle) accuracyCircle.setLatLng(ll).setRadius(accuracy);
        else accuracyCircle = L.circle(ll, {radius:accuracy, color:'#2b8cbe',
          weight:1, fillOpacity:0.08, interactive:false}).addTo(map);
      } else if (accuracyCircle) {
        map.removeLayer(accuracyCircle);
        accuracyCircle = null;
      }
      map.setView(ll, 14);
      finish('Centered on your location.' + (Number.isFinite(accuracy) && accuracy > 0
        ? ' Browser accuracy: about ' + Math.max(1, Math.round(accuracy)).toLocaleString() + ' m.' : ''));
    }, error => {
      const messages = {
        1:'Location access was denied. Enable location for this site in your browser, then try again.',
        2:'Your location could not be determined. Try again when a position is available.',
        3:'Finding your location timed out. Please try again.'
      };
      finish(messages[error.code] || 'Your location could not be determined. Please try again.');
    }, {enableHighAccuracy:true, timeout:8000, maximumAge:60000});
  }
  const LocateControl = L.Control.extend({
    options:{position:'topleft'},
    onAdd() {
      const container = L.DomUtil.create('div', 'leaflet-bar');
      button = L.DomUtil.create('button', 'locate-button', container);
      button.type = 'button';
      button.id = 'locate';
      button.title = 'Center on my location';
      button.setAttribute('aria-label', 'Center on my location');
      button.textContent = '◎';
      L.DomEvent.disableClickPropagation(container);
      L.DomEvent.disableScrollPropagation(container);
      L.DomEvent.on(button, 'click', locate);
      return container;
    }
  });
  map.addControl(new LocateControl());
  // No startup request: visitors choose when to share their location.
}
if (typeof module !== 'undefined') module.exports = {selectRows, summarize};
if (typeof document !== 'undefined') {
  const data = JSON.parse(document.getElementById('crime-data').textContent);
  const rows = data.rows.map(row => Object.fromEntries(data.columns.map((key,i) => [key,row[i]])));
  const $ = id => document.getElementById(id);
  const colors = {'Assault':'#ba5e40','Break and Enter':'#8364a6','Auto Theft':'#267ba0','Robbery':'#bd8740','Theft Over':'#458474','Homicide':'#9c3651','Shootings / discharges':'#5f4a95'};
  const map = L.map('map', {preferCanvas:true}).setView([43.71,-79.39],11);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution:'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors', maxZoom:19
  }).addTo(map);
  addLocationControl(map, $('location-status'));
  // Group repeated published coordinates before clustering. Synchronous insertion
  // prevents a previous filter's deferred chunks from reappearing after reset.
  const clusters = L.markerClusterGroup({maxClusterRadius:45,
    iconCreateFunction: cluster => L.divIcon({className:'',iconSize:[42,42],
      html:'<div class="cluster">'+cluster.getAllChildMarkers().reduce((n,m)=>n+m.options.recordCount,0).toLocaleString()+'</div>'})});
  map.addLayer(clusters);
  const option = (value,label) => { const o=document.createElement('option');o.value=value;o.textContent=label;return o; };
  const allCategories = Object.keys(colors).slice(0,5);
  for (const category of allCategories) {
    const label=document.createElement('label'), input=document.createElement('input'), swatch=document.createElement('span');
    input.type='checkbox';input.value=category;input.checked=true;input.addEventListener('change',()=>update());
    swatch.className='swatch';swatch.style.background=colors[category];label.append(input,swatch,document.createTextNode(category));$('categories').append(label);
  }
  const checks = () => [...$('categories').querySelectorAll('input')];
  function configure() {
    const source=$('source').value;
    const subset=rows.filter(r=>r.source===source);
    $('categories').hidden=source!=='main';
    // CSS grid would otherwise override the browser's hidden default.
    $('categories').style.display=source==='main'?'grid':'none';
    $('basis').value=source==='main'?'reported':'occurred';$('basis').disabled=source!=='main';
    $('neighbourhood').replaceChildren(option('','All neighbourhoods'));
    for (const name of [...new Set(subset.map(r=>r.neighbourhood))].sort()) $('neighbourhood').append(option(name,name));
    $('from').value=data.start_year+'-01-01';$('to').value=data.sources[source].latest_date;
    $('scope').textContent=(source==='main'?'Reports':'Occurrences')+' from '+data.start_year+' onward · latest included '+data.sources[source].latest_date+'. '+(source==='main'?'Sexual violations are excluded.':'This layer can overlap the other datasets.');
    $('status').textContent='Snapshot: '+data.fetched_at.slice(0,10)+' · '+data.start_year+' onward';
    $('snapshot').textContent='Fetched '+data.fetched_at+'. Last included dates vary by dataset; this is not a live feed.';
  }
  function popup(group) {
    const box=document.createElement('div'), title=document.createElement('strong');
    title.textContent=group.length.toLocaleString()+' records · approximate intersection';box.append(title);
    for (const r of group.slice(0,20)) {
      const event=document.createElement('div');event.className='event';
      const lines=[r.category+' · '+r.offence, 'Incident '+r.event_id,
        (r.reported?'Reported '+r.reported+' · ':'')+'Occurred '+(r.occurred||'not specified'),
        r.neighbourhood+' · '+r.division];
      if (r.premises) lines.push('Premises: '+r.premises);
      if (r.source==='shooting') lines.push('Deaths: '+(r.deaths??'not specified')+' · Injuries: '+(r.injuries??'not specified'));
      for (const line of lines) { const p=document.createElement('p');p.textContent=line;event.append(p); }box.append(event);
    }
    if(group.length>20) {const p=document.createElement('p');p.textContent='Showing the first 20 records at this published point. Narrow the date or offence filters for more detail.';box.append(p);}
    return box;
  }
  function update(fit=false) {
    const source=$('source').value;
    const filtered=selectRows(rows,{source,categories:new Set(source==='main'?checks().filter(c=>c.checked).map(c=>c.value):[source==='homicide'?'Homicide':'Shootings / discharges']),
      neighbourhood:$('neighbourhood').value,query:$('search').value.trim().toLowerCase(),basis:$('basis').value,from:$('from').value,to:$('to').value});
    const points=new Map();let mapped=0;
    for(const r of filtered) if(r.lat!==null && r.lon!==null) {
      const key=r.lat+','+r.lon;if(!points.has(key)) points.set(key,[]);points.get(key).push(r);mapped++;
    }
    clusters.clearLayers();
    const markers=[];
    for(const group of points.values()) {
      const r=group[0],color=new Set(group.map(r=>r.category)).size===1?colors[r.category]:'#254b60';
      const marker=L.marker([r.lat,r.lon],{recordCount:group.length,
        title:group.length+' records at approximate location',
        icon:L.divIcon({className:'',iconSize:[32,32],html:'<div class="pin" style="background:'+color+'">'+group.length+'</div>'})});
      marker.bindPopup(()=>popup(group));markers.push(marker);
    }
    clusters.addLayers(markers);
    const incidents=new Set(filtered.map(r=>r.event_id)).size;
    $('stats').replaceChildren();
    const strong=document.createElement('strong');strong.textContent=filtered.length.toLocaleString();
    $('stats').append(strong,document.createTextNode(' records'));
    const p=document.createElement('div');p.textContent=incidents.toLocaleString()+' distinct incidents in this dataset';$('stats').append(p);
    const missing=document.createElement('div');missing.className='muted';missing.textContent=mapped.toLocaleString()+' mapped · '+(filtered.length-mapped).toLocaleString()+' without valid coordinates';$('stats').append(missing);
    $('summary').replaceChildren();
    for(const g of summarize(filtered)) {
      const tr=document.createElement('tr'),name=document.createElement('td'),button=document.createElement('button');
      button.type='button';button.className='link';button.textContent=g.name;button.onclick=()=>{$('neighbourhood').value=g.name;update(true);};name.append(button);tr.append(name);
      for(const n of [g.count,g.incidents.size]) {const td=document.createElement('td');td.textContent=n.toLocaleString();tr.append(td);}$('summary').append(tr);
    }
    $('empty').hidden=mapped>0;$('empty').textContent=filtered.length?'Matching records have no valid coordinates.':'No records match these filters.';
    if(fit && markers.length) map.fitBounds(L.latLngBounds(markers.map(m=>m.getLatLng())),{padding:[35,35],maxZoom:15});
  }
  let timer;
  $('search').addEventListener('input',()=>{clearTimeout(timer);timer=setTimeout(()=>update(),220);});
  for(const id of ['basis','from','to']) $(id).addEventListener('change',()=>update());
  $('neighbourhood').addEventListener('change',()=>update(true));
  $('source').addEventListener('change',()=>{configure();update();});
  $('reset').onclick=()=>{$('source').value='main';$('search').value='';checks().forEach(c=>c.checked=true);configure();map.setView([43.71,-79.39],11);update();};
  configure();update();
}
