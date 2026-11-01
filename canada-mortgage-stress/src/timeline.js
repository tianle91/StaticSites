/* Pure selection and date math, shared by the renderer and offline checks.
 * Both metrics use one calendar domain, regardless of their reporting cadence.
 */
(function (root) {
  'use strict';

  function stamp(period) {
    const quarter = period.match(/^(\d{4})-Q([1-4])$/);
    if (quarter) return Date.UTC(Number(quarter[1]), Number(quarter[2]) * 3, 0);
    if (period.length === 4) return Date.UTC(Number(period), 11, 31);
    const [year, month] = period.split('-').map(Number);
    return Date.UTC(year, month, 0);
  }

  function domain(state) {
    return [Math.max(Date.UTC(state.from, 0, 1), state.coverageStart ?? -Infinity),
      Math.min(Date.UTC(state.to + 1, 0, 1), state.coverageEnd ?? Infinity)];
  }

  function xPosition(period, state, width, left = 76, right = 76) {
    const [start, end] = domain(state);
    return left + (stamp(period) - start) / (end - start) * (width - left - right);
  }

  function pointsFor(series, state) {
    return series.points.filter(point => {
      const year = Number(point.period.slice(0, 4));
      return year >= state.from && year <= state.to &&
        stamp(point.period) >= (state.coverageStart ?? -Infinity) &&
        stamp(point.period) <= (state.coverageEnd ?? Infinity) &&
        (state.forecast || point.status !== 'forecast');
    });
  }

  function visibleSeries(series, state) {
    const points = pointsFor(series, state);
    const base = points[0]?.value;
    // An index with a zero base is undefined; never invent a replacement base.
    return points.map(point => ({
      ...point,
      y: state.mode === 'index' ? (base ? point.value / base * 100 : null) : point.value,
    })).filter(point => point.y !== null);
  }

  function panels(data, state) {
    const groups = Object.fromEntries(data.groups.map(group => [group.id, group]));
    const result = [];
    if (state.bank) {
      const group = groups[state.bankType === 'monthly' ? 'outlook' : 'provinces'];
      result.push({
        ...group, id: 'bank', title: 'Ontario bank mortgage arrears', geography: 'Ontario',
        axis: '90+ days overdue (% of accounts)',
        series: group.series.filter(series => series.name === 'Ontario'),
      });
    }
    if (state.prices) {
      const group = groups[state.priceType === 'annual' ? 'annual' : 'prices'];
      result.push({
        ...group, id: 'prices', title: 'Toronto-area average sale price', geography: 'TRREB market area · regional context',
        axis: 'Average sale price (CAD)', breakAt: state.priceType === 'monthly' ? '2024-01' : null,
      });
    }
    return result;
  }

  function monthOrdinal(period) {
    const date = new Date(stamp(period));
    return date.getUTCFullYear() * 12 + date.getUTCMonth();
  }

  function overlapYears(data, state) {
    // Intersect at the metric level: the two price vintages together form the
    // price history. Intersecting each individual path would lose all years.
    const coverage = panels(data, state).map(panel => new Set(panel.series.flatMap(series =>
      series.points.filter(point => state.forecast || point.status !== 'forecast')
        .map(point => Number(point.period.slice(0, 4))))));
    return coverage.length ? [...coverage[0]].filter(year => coverage.every(years => years.has(year)))
      .sort((a, b) => a - b) : [];
  }

  function sharedBounds(data, state) {
    const ranges = panels(data,state).map(panel => panel.series.flatMap(series =>
      series.points.filter(point => state.forecast || point.status !== 'forecast')
        .map(point => stamp(point.period))));
    return [Math.max(...ranges.map(points => Math.min(...points))),
      Math.min(...ranges.map(points => Math.max(...points)))];
  }

  function nearestObservation(series, period, frequency, state) {
    const points = pointsFor(series, state);
    if (!points.length) return null;
    const month = monthOrdinal(period);
    // Do not extend a stale series past its actual published coverage.
    if (month < monthOrdinal(points[0].period) || month > monthOrdinal(points.at(-1).period)) return null;
    const point = points.reduce((best, candidate) =>
      Math.abs(monthOrdinal(candidate.period) - month) < Math.abs(monthOrdinal(best.period) - month)
        ? candidate : best);
    const tolerance = frequency === 'Annual' ? 6 : frequency === 'Quarterly' ? 1 : 0;
    return Math.abs(monthOrdinal(point.period) - month) <= tolerance ? point : null;
  }

  function selectionRows(data, state) {
    const rows = [['metric', 'geography', 'series', 'period', 'value', 'unit', 'status', 'display_value', 'display_unit', 'source']];
    for (const panel of panels(data, state)) {
      for (const series of panel.series) {
        for (const point of visibleSeries(series, state)) {
          rows.push([panel.title, panel.geography, series.name, point.period, point.value, panel.unit,
            point.status, point.y, state.mode === 'index' ? 'index (first visible = 100)' : panel.unit,
            point.source || panel.source_url]);
        }
      }
    }
    return rows;
  }

  const api = { stamp, domain, xPosition, pointsFor, visibleSeries, panels, overlapYears, sharedBounds, nearestObservation, selectionRows };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.MortgageTimeline = api;
})(typeof globalThis === 'undefined' ? this : globalThis);
