'use strict';
const assert = require('node:assert/strict');
const M = require('../../src/staticsites/assets/plots/chart.js');
const observed = (date,value) => ({date,value});
const spec = {panels:[{id:'a',series:[{points:[observed('2024-01-31',0),observed('2024-02-29',null)]}]},
  {id:'ratio',defaultChoice:'m2',choices:[{key:'m2',series:[{id:'m2',points:[observed('2024-03-31',100)]}]},
                                      {key:'mmf',series:[{id:'mmf',points:[observed('2024-03-31',120)]}]}]}]};
assert.deepEqual(M.dates(spec),['2024-01-31','2024-02-29','2024-03-31']);
assert.equal(M.panels(spec,{}).at(-1).series[0].id,'m2');
assert.equal(M.panels(spec,{ratio:'mmf'}).at(-1).series[0].id,'mmf');
assert.equal(M.nearest(M.dates(spec),'2024-02-27'),'2024-02-29');
const segments = M.segments([observed('2024-01-31',0),observed('2024-02-29',null),observed('2024-03-31',2),
  {...observed('2024-04-30',3),status:'forecast'}]);
assert.deepEqual(segments.map(s=>s.points.map(p=>p.value)),[[0],[2],[2,3]]);
assert.equal(segments.at(-1).status,'forecast');
console.log('5 native chart-model checks passed.');
