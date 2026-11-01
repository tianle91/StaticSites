/* Optional browser-model checks using only Node 18+ built-ins. Run from any cwd:
 * node canada-mortgage-stress/tests/test_timeline.cjs
 */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const T = require('../src/timeline.js');
const data = JSON.parse(fs.readFileSync(path.join(__dirname, '../data/series.json'), 'utf8'));
const base = { bank:true, prices:true, bankType:'quarterly', priceType:'monthly',
  from:2020, to:2026, mode:'raw', forecast:false };
let count = 0;
function test(name, run) { run(); count++; console.log('ok - ' + name); }

test('plot selection contains only Ontario bank arrears and Toronto-area prices', () => {
  const panels = T.panels(data, base);
  assert.deepEqual(panels.map(p => p.id), ['bank','prices']);
  assert.deepEqual(panels[0].series.map(s => s.name), ['Ontario']);
  assert.equal(panels[1].unit, 'CAD');
});
test('selection changes cannot change the shared time domain', () => {
  const original = T.domain(base);
  for (const change of [{ bank:false },{ prices:false },{ bankType:'monthly' },{ priceType:'annual' },{ forecast:true }]) {
    assert.deepEqual(T.domain({...base,...change}), original);
  }
});
test('the same calendar date has the same x coordinate in quarterly, monthly and annual plots', () => {
  for (const width of [320,700,1100]) {
    assert.equal(T.xPosition('2025-Q4',base,width),T.xPosition('2025-12',base,width));
    assert.equal(T.xPosition('2025',base,width),T.xPosition('2025-12',base,width));
  }
  assert.equal(T.stamp('2020-Q1'),Date.UTC(2020,2,31));
});
test('date filters include the chosen years and do not manufacture observations', () => {
  const state = {...base,from:2023,to:2023};
  const bank = T.panels(data,state)[0].series[0];
  assert.deepEqual(T.pointsFor(bank,state).map(p=>p.period),['2023-Q1','2023-Q2','2023-Q3','2023-Q4']);
  assert.equal(T.pointsFor(T.panels(data,state)[1].series[0],state).length,12);
});
test('forecast exclusion and the observed/forecast boundary are preserved', () => {
  const state = {...base,bankType:'monthly',to:2027};
  const bank = T.panels(data,state)[0].series[0];
  const observed = T.pointsFor(bank,state);
  assert.equal(observed.at(-1).period,'2026-06');
  const included = T.pointsFor(bank,{...state,forecast:true});
  assert.equal(included.length-observed.length,12);
  assert.equal(included.at(-1).period,'2027-06');
});
test('price types switch without joining across the monthly coverage break', () => {
  const monthly = T.panels(data,base).at(-1);
  assert.equal(monthly.series.length,2);
  assert.equal(monthly.series[0].points.at(-1).period,'2023-12');
  assert.equal(monthly.series[1].points[0].period,'2024-01');
  const annual = T.panels(data,{...base,priceType:'annual'}).at(-1);
  assert.equal(annual.frequency,'Annual');
  assert.equal(annual.breakAt,null);
});
test('indexed mode rebases each visible report vintage independently', () => {
  const state = {...base,mode:'index',from:2022};
  for (const panel of T.panels(data,state)) for (const series of panel.series) {
    const values=T.visibleSeries(series,state);
    assert.equal(values[0].y,100);
    assert.equal(values[0].value,T.pointsFor(series,state)[0].value);
  }
});
test('the shared inspector returns exact observations, never interpolated or carried-forward values', () => {
  const panels=T.panels(data,base);
  const bank=panels[0].series[0];
  assert.equal(T.nearestObservation(bank,'2026-06','Quarterly',base).value,.32);
  assert.equal(T.nearestObservation(bank,'2026-09','Quarterly',base),null);
  assert.equal(T.nearestObservation(bank,'1994-01','Quarterly',base),null);
  assert.equal(T.nearestObservation(panels[1].series[1],'2026-09','Monthly',base).value,1006409);
});
test('CSV follows selected plots, dates and forecast setting', () => {
  const state={...base,bankType:'monthly',private:false,prices:false,from:2026,to:2027};
  const rows=T.selectionRows(data,state);
  assert.equal(rows.length,7); // Header + Jan–June observed Ontario bank data.
  assert(rows.slice(1).every(row=>row[1]==='Ontario' && row[6]==='observed'));
  assert.equal(T.selectionRows(data,{...state,forecast:true}).length,19);
});
test('regional CSV exports preserve raw units, indexed values and report URLs', () => {
  const rows=T.selectionRows(data,{...base,bank:false,private:false,mode:'index',from:2024});
  assert.equal(rows.length,34);
  assert.equal(rows[1][7],100);
  assert.equal(rows[1][5],'CAD');
  assert.match(rows[1][9],/mw2512\.pdf$/);
  assert(rows.slice(1).every(row=>row[1].includes('TRREB')));
});
test('shared years exclude years available in only one metric', () => {
  assert.deepEqual(T.overlapYears(data,{...base,bankType:'monthly',forecast:true}),[2021,2022,2023,2024,2025,2026]);
  assert.deepEqual(T.overlapYears(data,base),[2020,2021,2022,2023,2024,2025,2026]);
  assert.deepEqual(T.overlapYears(data,{...base,priceType:'annual'}).slice(0,2),[1995,1996]);
  assert.equal(T.overlapYears(data,{...base,priceType:'annual'}).at(-1),2025);
});
test('fixed monthly series clip chart, inspection and export to exact shared coverage', () => {
  const state={...base,bankType:'monthly',forecast:true,from:2021,to:2026};
  [state.coverageStart,state.coverageEnd]=T.sharedBounds(data,state);
  assert.deepEqual(T.domain(state),[Date.UTC(2021,0,31),Date.UTC(2026,8,30)]);
  const panels=T.panels(data,state);
  const bank=T.pointsFor(panels[0].series[0],state);
  assert.equal(bank.length,69);
  assert.equal(bank.filter(p=>p.status==='forecast').length,3);
  assert.equal(bank.at(-1).period,'2026-09');
  assert.equal(T.nearestObservation(panels[0].series[0],'2026-10','Monthly',state),null);
  const rows=T.selectionRows(data,state).slice(1);
  assert.equal(rows.length,138);
  assert(rows.every(row=>row[3]>='2021-01' && row[3]<='2026-09'));
  assert.equal(T.xPosition('2026-09',state,900),824);
});
console.log(count + ' timeline checks passed.');
