---
title: Pathway
sql:
  objective: ./data/runs/record.parquet
  total: ./data/runs/primal/total.parquet
  build: ./data/runs/primal/build.parquet
  emissions: ./data/runs/expression/emissions.parquet
  capex: ./data/runs/expression/capex.parquet
  opex: ./data/runs/expression/opex.parquet
  cap: ./data/runs/source/cap.parquet
  rate: ./data/runs/source/rate.parquet
  carbon: ./data/runs/dual/carbon.parquet
---

<style>
.tile-label { font-size: 0.85rem; color: var(--theme-foreground-muted); }
.tile-value { font-size: 2rem; font-weight: 600; line-height: 1.2; margin: 0.15rem 0; }
.tile-note { font-size: 0.85rem; color: var(--theme-foreground-muted); }
.inputs { display: flex; flex-wrap: wrap; gap: 0.25rem 2rem; align-items: center; margin: 1rem 0; }
</style>

# Capacity-expansion pathway

One model, four scenarios, each solved one investment period at a time with the fleet carried forward. Every number on this page is a query over the parquet that [specsolve](https://github.com/fluxopt/specsolve) archived, run by DuckDB in your browser.

```js
import {colorScale, surface} from "./components/palette.js";
import {fmt, tile, diverging} from "./components/format.js";
```

```sql id=runs
select distinct run from objective order by run
```

```sql id=cost
select run, year::integer as year, objective as value from objective order by run, year
```

```sql id=co2
select run, year::integer as year, value from emissions order by run, year
```

```sql id=bound
select run, year::integer as year, value from cap order by run, year
```

```sql id=carbonPrice
select run, year::integer as year, -value as value from carbon order by run, year
```

```sql id=fleet
select run, year::integer as year, generator, value from total order by run, year, generator
```

```sql id=built
select run, year::integer as year, generator, value from build order by run, year, generator
```

```sql id=spend
select run, year::integer as year, generator, 'build' as kind, value from capex
union all
select run, year::integer as year, generator, 'run' as kind, value from opex
order by run, year, generator, kind
```

```sql id=rates
select run, generator, value from rate
```

```js
const scenarios = runs.toArray().map((d) => d.run);
const years = [...new Set(cost.toArray().map((d) => d.year))].sort((a, b) => a - b);
const technologies = [...new Set(fleet.toArray().map((d) => d.generator))].sort();
const first = years[0], last = years.at(-1);
const of = (table, run) => table.toArray().filter((d) => d.run === run);
```

<div class="inputs">

```js
const chosen = view(Inputs.checkbox(scenarios, {value: scenarios, label: "Scenarios"}));
```

```js
const focus = view(Inputs.select(scenarios, {label: "Focus on"}));
```

```js
const other = view(Inputs.select(scenarios, {label: "Compare with", value: scenarios[1] ?? scenarios[0]}));
```

```js
const highlight = view(Inputs.radio(["all", ...technologies], {label: "Technology", value: "all"}));
```

</div>

```js
const dim = (d) => (highlight === "all" || d.generator === highlight ? 1 : 0.25);
const pick = (table) => table.toArray().filter((d) => chosen.includes(d.run));
const sum = (rows) => rows.reduce((s, d) => s + d.value, 0);
const at = (table, run, year) => table.toArray().filter((d) => d.run === run && d.year === year);

const pathwayCost = sum(of(cost, focus));
const emissionsCut = 1 - sum(at(co2, focus, last)) / sum(at(co2, focus, first));
const zeroCarbon = new Set(of(rates, focus).filter((d) => d.value === 0).map((d) => d.generator));
const finalFleet = at(fleet, focus, last);
const zeroCarbonShare = sum(finalFleet.filter((d) => zeroCarbon.has(d.generator))) / sum(finalFleet);
const lastPrice = sum(at(carbonPrice, focus, last));
```

<div class="grid grid-cols-4">
  ${tile("Pathway cost", fmt.compact(pathwayCost), `${focus}: annualised cost summed over ${years.length} periods`)}
  ${tile("Emissions cut", fmt.percent(emissionsCut), `${focus}: ${first} to ${last}`)}
  ${tile("Zero-carbon fleet", fmt.percent(zeroCarbonShare), `${focus}: share of capacity in ${last}, by emission rate`)}
  ${tile("Carbon price", lastPrice > 1e-6 ? `${fmt.plain(lastPrice)} /t` : "0 /t", lastPrice > 1e-6 ? `${focus}: the cap binds in ${last}` : `${focus}: the cap does not bind in ${last}`)}
</div>

```js
function byPeriod(rows, {label, width, height = 280}) {
  return Plot.plot({
    width,
    height,
    marginLeft: 60,
    x: {label: "period", tickFormat: "d", ticks: years},
    y: {grid: true, label, tickFormat: "s", zero: true},
    color: colorScale(scenarios, dark),
    marks: [
      Plot.lineY(rows, {x: "year", y: "value", stroke: "run", strokeWidth: 2}),
      Plot.dot(rows, {x: "year", y: "value", fill: "run", r: 4, stroke: surface, strokeWidth: 2}),
      Plot.ruleX(rows, Plot.pointerX({x: "year", stroke: "var(--theme-foreground-faint)"})),
      Plot.tip(rows, Plot.pointerX({x: "year", y: "value", channels: {scenario: "run"}, format: {x: "d", y: ",.0f", fill: false}})),
    ],
  });
}
const half = Math.max(320, (width - 16) / 2 - 34);
```

<div class="grid grid-cols-2">
<div class="card">
<h2>Annualised cost per period</h2>
<p class="muted">Click a period to select it below.</p>

```js
const pointed = view(byPeriod(pick(cost), {label: "cost", width: half}));
```

</div>
<div class="card">
<h2>CO₂ emitted per period, t</h2>

```js
display(byPeriod(pick(co2), {label: "tonnes", width: half}));
```

</div>
</div>

```js
const period = pointed?.year ?? last;
```

<div class="grid grid-cols-2">
  <div class="card">
    <h2>Standing capacity, MW — ${focus}</h2>
    ${resize((width) => Plot.plot({
      width, height: 280, marginLeft: 60,
      x: {label: "period", tickFormat: "d"},
      y: {grid: true, label: "MW"},
      color: colorScale(technologies, dark),
      marks: [
        Plot.barY(of(fleet, focus), {x: "year", y: "value", fill: "generator", fillOpacity: dim, stroke: surface, strokeWidth: 2, tip: {format: {x: "d", y: ",.1f"}}}),
        Plot.text([{year: period, top: sum(at(fleet, focus, period))}], {x: "year", y: "top", text: ["▼ selected"], dy: -10, fill: "var(--theme-foreground-muted)"}),
      ],
    }))}
  </div>
  <div class="card">
    <h2>Built in the period, MW — ${focus}</h2>
    ${resize((width) => Plot.plot({
      width, height: 280, marginLeft: 60,
      x: {label: "period", tickFormat: "d"},
      y: {grid: true, label: "MW"},
      color: colorScale(technologies, dark),
      marks: [
        Plot.barY(of(built, focus), {x: "year", y: "value", fill: "generator", fillOpacity: dim, stroke: surface, strokeWidth: 2, tip: {format: {x: "d", y: ",.1f"}}}),
        Plot.text([{year: period, top: sum(at(built, focus, period))}], {x: "year", y: "top", text: ["▼ selected"], dy: -10, fill: "var(--theme-foreground-muted)"}),
      ],
    }))}
  </div>
</div>

<p>Selected period: <strong>${period}</strong>. ${html`<a href="./dispatch?run=${focus}&year=${period}">See how ${focus} dispatches the fleet in ${period} →</a>`}</p>

<div class="card">
  <h2>What the cost is made of</h2>
  <p class="muted">Annualised cost of building, and of running, per technology and period. One column per scenario.</p>
  ${resize((width) => Plot.plot({
    width, height: 360, marginLeft: 60, marginRight: 60,
    x: {label: null, tickFormat: "d"},
    y: {grid: true, label: "cost", tickFormat: "s"},
    fx: {label: null, domain: chosen},
    fy: {label: null, domain: ["build", "run"], tickFormat: (d) => (d === "build" ? "to build" : "to run")},
    color: colorScale(technologies, dark),
    marks: [
      Plot.barY(pick(spend), {x: "year", y: "value", fx: "run", fy: "kind", fill: "generator", fillOpacity: dim, stroke: surface, strokeWidth: 1.5, tip: {format: {x: "d", y: ",.0f"}}}),
    ],
  }))}
</div>

```js
const capShown = pick(bound).filter((d) => d.value < 5 * Math.max(...co2.toArray().map((e) => e.value)));
const binding = pick(co2).filter((d) => bound.toArray().some((c) => c.run === d.run && c.year === d.year && d.value >= c.value * (1 - 1e-6)));
```

<div class="card">
  <h2>Emissions against the cap</h2>
  <p class="muted">Bars are what each period emitted; the step line is the cap it was given. A cap far above any fleet's emissions is left off the chart.</p>
  ${resize((width) => Plot.plot({
    width, height: 300, marginLeft: 60,
    x: {label: null, tickFormat: "d"},
    y: {grid: true, label: "tonnes", tickFormat: "s"},
    fx: {label: null, domain: chosen},
    color: colorScale(scenarios, dark),
    marks: [
      Plot.barY(pick(co2), {x: "year", y: "value", fx: "run", fill: "run", stroke: surface, strokeWidth: 2, tip: {format: {x: "d", y: ",.0f"}}}),
      Plot.lineY(capShown, {x: "year", y: "value", fx: "run", stroke: "var(--theme-foreground)", strokeWidth: 2, curve: "step", strokeDasharray: "4 3"}),
      Plot.text(binding, {x: "year", y: "value", fx: "run", text: ["binding"], dy: -10, fill: "var(--theme-foreground)"}),
    ],
  }))}
</div>

```js
const key = (d) => `${d.year}|${d.generator}`;
const base = new Map(of(built, focus).map((d) => [key(d), d.value]));
const delta = of(built, other).map((d) => ({year: d.year, generator: d.generator, delta: d.value - (base.get(key(d)) ?? 0)}));
const deltaCost = sum(of(cost, other)) - pathwayCost;
const deltaCo2 = sum(of(co2, other)) - sum(of(co2, focus));
```

<div class="grid grid-cols-2">
  ${tile("Pathway cost", fmt.signed(deltaCost), `${other} against ${focus}, summed over the pathway`)}
  ${tile("Emissions", fmt.signed(deltaCo2) + " t", `${other} against ${focus}, summed over the pathway`)}
</div>

<div class="card">
  <h2>What ${other} builds, compared with ${focus}</h2>
  <p class="muted">Capacity built per period, in MW, ${other} minus ${focus}.</p>
  ${resize((width) => Plot.plot({
    width, height: 260, marginLeft: 60,
    x: {label: null, domain: technologies},
    fx: {label: null, tickFormat: "d"},
    y: {grid: true, label: "MW more, or fewer"},
    marks: [
      Plot.ruleY([0]),
      Plot.barY(delta, {x: "generator", y: "delta", fx: "year", fill: (d) => (d.delta >= 0 ? diverging.more : diverging.less), stroke: surface, strokeWidth: 2, tip: {format: {y: "+,.1f"}}}),
    ],
  }))}
</div>

<div class="card">
  <h2>Every solve</h2>
  ${Inputs.table(pick(cost), {columns: ["run", "year", "value"], header: {value: "objective"}, format: {year: (d) => String(d), value: fmt.plain}})}
</div>
