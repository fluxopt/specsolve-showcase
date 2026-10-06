---
title: What if
sql:
  objective: ./data/grid/record.parquet
  total: ./data/grid/primal/total.parquet
  emissions: ./data/grid/expression/emissions.parquet
  carbon: ./data/grid/dual/carbon.parquet
  cap: ./data/grid/source/cap.parquet
  invest: ./data/grid/source/invest.parquet
  rate: ./data/grid/source/rate.parquet
---

<style>
.tile-label { font-size: 0.85rem; color: var(--theme-foreground-muted); }
.tile-value { font-size: 2rem; font-weight: 600; line-height: 1.2; margin: 0.15rem 0; }
.tile-note { font-size: 0.85rem; color: var(--theme-foreground-muted); }
/* The sliders stay in view while the charts they drive scroll under them, just below the site's own fixed header. */
.controls { position: sticky; top: calc(var(--observablehq-header-height) + 1.5rem); z-index: 10; margin: 1rem -1rem; padding: 0.5rem 1rem; background: var(--theme-background-alt); border-bottom: 1px solid var(--theme-foreground-faintest); }
.inputs { display: flex; flex-wrap: wrap; gap: 0.25rem 2rem; align-items: center; }
.inputs form { width: min(100%, 420px); }
/* The sliders step through the grid's own values, which are not numbers a text box can show; the line under them names them. */
.inputs input[type="number"] { display: none; }
.picked { color: var(--theme-foreground-muted); font-size: 0.9rem; margin: 0.25rem 0 0; max-width: none; }
/* On a phone the two sliders stack and would pin a third of the screen, so there they scroll with the page. */
@media (max-width: 640px) { .controls { position: static; } }
</style>

# What if the cap were tighter, or solar cheaper?

Two sliders, and every position of them is a pathway the solve job has already solved and archived. Nothing solves in your browser: moving a slider looks up one of ${points.length} archives, ${solves} solves in all, which reach this page as ${fmt.compact(bytes / 1024)} KB of parquet. The [Session](./session) page asks the same two questions of a live solver, at a cost of 40 MB and a gigabyte of memory; this page answers them on a phone.

```js
import {colorScale, surface} from "./components/palette.js";
import {fmt, tile, sequential} from "./components/format.js";
import {steady} from "./components/steady.js";
```

```sql id=grid
with last as (select max(year) as year from objective),
axes as (
  select c.run, c.value as cap, i.value as solar
  from cap c join invest i on c.run = i.run and c.year = i.year, last
  where c.year = last.year and i.generator = 'solar'
),
pathway as (select run, sum(objective) as cost, bool_and(termination_condition = 'optimal') as optimal from objective group by run)
select a.run, a.cap, a.solar, p.cost, p.optimal, e.value as co2, -d.value as price
from axes a
join pathway p using (run)
join emissions e on e.run = a.run and e.year = (select year from last)
join carbon d on d.run = a.run and d.year = (select year from last)
order by a.cap desc, a.solar
```

```sql id=fleets
select run, year::integer as year, generator, value from total order by run, year, generator
```

```sql id=co2ByYear
select run, year::integer as year, value from emissions order by run, year
```

```sql id=rates
select distinct generator, value from rate
```

```js
const points = grid.toArray().map((d) => ({...d}));
const solves = points.length * new Set(co2ByYear.toArray().map((d) => d.year)).size;
// What this page reads, the same files as the front matter names: the browser has them already, so this costs nothing.
const shipped = [
  FileAttachment("./data/grid/record.parquet"), FileAttachment("./data/grid/primal/total.parquet"),
  FileAttachment("./data/grid/expression/emissions.parquet"), FileAttachment("./data/grid/dual/carbon.parquet"),
  FileAttachment("./data/grid/source/cap.parquet"), FileAttachment("./data/grid/source/invest.parquet"),
  FileAttachment("./data/grid/source/rate.parquet"),
];
const bytes = d3.sum(await Promise.all(shipped.map(async (f) => (await f.arrayBuffer()).byteLength)));

// A cap no fleet here could reach is "no cap": it binds nowhere, and is drawn as its own column.
const reach = 10 * d3.max(points, (d) => d.co2);
const capLabel = (c) => (c > reach ? "no cap" : `${fmt.compact(c)} t`);
const solarLabel = (s) => fmt.compact(s);
for (const d of points) Object.assign(d, {capLabel: capLabel(d.cap), solarLabel: solarLabel(d.solar)});

const caps = [...new Set(points.map((d) => d.cap))].sort((a, b) => b - a);
const solars = [...new Set(points.map((d) => d.solar))].sort((a, b) => a - b);
const lookup = new Map(points.map((d) => [`${d.cap}|${d.solar}`, d]));
const technologies = [...new Set(fleets.toArray().map((d) => d.generator))].sort();
const zeroCarbon = new Set(rates.toArray().filter((d) => d.value === 0).map((d) => d.generator));
const years = [...new Set(co2ByYear.toArray().map((d) => d.year))].sort((a, b) => a - b);
const last = years.at(-1);
```

```js
const capInput = Inputs.range([0, caps.length - 1], {label: `CO₂ cap in ${last}`, step: 1, value: Math.floor(caps.length / 2)});
const solarInput = Inputs.range([0, solars.length - 1], {label: `Solar build cost in ${last}, per MW`, step: 1, value: Math.floor(solars.length / 2)});

// A click on either grid moves both sliders, so the sliders stay the one place the selection lives.
function select(d) {
  capInput.value = caps.indexOf(d.cap);
  solarInput.value = solars.indexOf(d.solar);
  capInput.dispatchEvent(new Event("input", {bubbles: true}));
  solarInput.dispatchEvent(new Event("input", {bubbles: true}));
}
```

<div class="controls">
<div class="inputs">

```js
const capIndex = view(capInput);
```

```js
const solarIndex = view(solarInput);
```

</div>

<p class="picked">Showing the archive <code>${here.run}</code>: ${here.cap > reach ? "no cap" : `a cap of ${fmt.plain(here.cap)} t`} in ${last}, and solar at ${fmt.plain(here.solar)} per MW to build.</p>

</div>

```js
const here = lookup.get(`${caps[capIndex]}|${solars[solarIndex]}`);
const uncapped = lookup.get(`${caps[0]}|${here.solar}`);
const fleet = fleets.toArray().filter((d) => d.run === here.run);
const finalFleet = fleet.filter((d) => d.year === last);
const cleanShare = d3.sum(finalFleet.filter((d) => zeroCarbon.has(d.generator)), (d) => d.value) / d3.sum(finalFleet, (d) => d.value);
const premium = here.cost / uncapped.cost - 1;
```


<div class="grid grid-cols-4">
  ${tile("Pathway cost", fmt.compact(here.cost), here === uncapped ? "annualised, summed over the periods" : `${fmt.percent(premium)} more than with no cap, at this solar cost`)}
  ${tile(`CO₂ in ${last}`, `${fmt.compact(here.co2)} t`, here === uncapped ? "what the cheapest fleet emits" : `against ${fmt.compact(uncapped.co2)} t with no cap`)}
  ${tile("Carbon price", `${fmt.plain(here.price)} /t`, here.price > 1e-6 ? `the dual of the cap: what one tonne less would cost` : "the cap does not bind, so a tonne is free")}
  ${tile("Zero-carbon fleet", fmt.percent(cleanShare), `share of capacity standing in ${last}`)}
</div>

<div class="grid grid-cols-2">
  <div class="card">
    <h2>Standing capacity, MW</h2>
    <p class="muted">The fleet this point builds, period by period. Only the last period is capped, so it is the one that changes.</p>
    ${steady("fleet", (width) => Plot.plot({
      width, height: 280, marginLeft: 50,
      x: {label: null, tickFormat: "d"},
      y: {grid: true, label: "MW"},
      color: colorScale(technologies, dark),
      marks: [
        Plot.barY(fleet, {x: "year", y: "value", fill: "generator", stroke: surface, strokeWidth: 2, tip: {format: {x: "d", y: ",.1f"}}}),
        Plot.ruleY([0]),
      ],
    }))}
  </div>
  <div class="card">
    <h2>CO₂ per period, t</h2>
    <p class="muted">This point, against the same solar cost with no cap. The mark in ${last} is the cap.</p>
    ${steady("co2", (width) => {
      const rows = [
        ...co2ByYear.toArray().filter((d) => d.run === uncapped.run).map((d) => ({...d, series: "no cap"})),
        ...(here === uncapped ? [] : co2ByYear.toArray().filter((d) => d.run === here.run).map((d) => ({...d, series: "this point"}))),
      ];
      const series = [...new Set(rows.map((d) => d.series))];
      return Plot.plot({
        width, height: 280, marginLeft: 50, marginRight: 70,
        x: {label: null, tickFormat: "d", ticks: years},
        y: {grid: true, label: "tonnes", tickFormat: "s", zero: true},
        color: {domain: ["this point", "no cap"], range: ["var(--theme-foreground-focus)", "var(--theme-foreground-faint)"], legend: series.length > 1},
        marks: [
          Plot.lineY(rows.filter((d) => d.series === "no cap"), {x: "year", y: "value", stroke: "series", strokeWidth: 2, strokeDasharray: "4 3"}),
          Plot.lineY(rows.filter((d) => d.series === "this point"), {x: "year", y: "value", stroke: "series", strokeWidth: 2}),
          Plot.dot(rows, {x: "year", y: "value", fill: "series", r: 4, stroke: surface, strokeWidth: 2, tip: {format: {x: "d", y: ",.0f", fill: false}, channels: {series: "series"}}}),
          here.cap <= reach ? Plot.tickY([{year: last, value: here.cap}], {x: "year", y: "value", stroke: "var(--theme-foreground)", strokeWidth: 2}) : null,
          here.cap <= reach ? Plot.text([{year: last, value: here.cap}], {x: "year", y: "value", text: () => "cap", dx: -14, textAnchor: "end", fill: "var(--theme-foreground-muted)"}) : null,
          Plot.text(rows.filter((d) => d.year === last), {x: "year", y: "value", text: "series", dx: 8, dy: -10, textAnchor: "start", fill: "var(--theme-foreground-muted)"}),
        ],
      });
    })}
  </div>
</div>

```js
function heatmap(fill, {label, type = "linear", format}, width) {
  const plot = Plot.plot({
    width, height: 360, marginLeft: 60, marginBottom: 60,
    x: {label: `CO₂ cap in ${last}, tighter →`, labelOffset: 55, domain: caps.map(capLabel), tickRotate: -35},
    y: {label: "solar build cost, per MW ↑", domain: solars.map(solarLabel), reverse: true},
    color: {type, range: sequential, interpolate: "rgb", legend: true, label, tickFormat: "s"},
    marks: [
      Plot.cell(points, {x: "capLabel", y: "solarLabel", fill, inset: 1, tip: {channels: {cap: "capLabel", "solar cost": "solarLabel", [label]: fill}, format: {x: false, y: false, fill: false, [label]: format}}}),
      Plot.cell([here], {x: "capLabel", y: "solarLabel", fill: "none", stroke: "var(--theme-foreground)", strokeWidth: 2.5}),
    ],
  });
  plot.style.cursor = "pointer";
  plot.addEventListener("click", () => plot.value && select(plot.value));
  return plot;
}
```

<div class="grid grid-cols-2">
  <div class="card">
    <h2>Pathway cost, over the whole grid</h2>
    <p class="muted">Every archive at once. Click a cell to move the sliders to it.</p>
    ${steady("cost", (width) => heatmap("cost", {label: "pathway cost", format: ",.0f"}, width))}
  </div>
  <div class="card">
    <h2>Carbon price in ${last}, over the whole grid</h2>
    <p class="muted">The dual of the cap, per tonne. It is zero wherever the cap does not bind, and climbs steeply for the last tonnes.</p>
    ${steady("price", (width) => heatmap("price", {label: "carbon price", type: "sqrt", format: ",.0f"}, width))}
  </div>
</div>

```js
const line = points.filter((d) => d.solar === here.solar).sort((a, b) => b.cap - a.cap);
// The price is the slope of this curve at the point: the tangent drawn through it has slope −price.
const span = (d3.max(points, (d) => d.co2) - d3.min(points, (d) => d.co2)) / 4;
const tangent = [
  {co2: here.co2 - span, cost: here.cost + here.price * span},
  {co2: here.co2 + span, cost: here.cost - here.price * span},
];
```

<div class="card">
  <h2>What cutting the last tonnes costs</h2>
  <p class="muted">Pathway cost against CO₂ in ${last}, one curve per solar cost; the one you picked is drawn, the others are grey. The dashed line through the point has the carbon price as its slope, and it touches the curve: the dual the solver returns is the rate at which cost rises as the cap tightens, read off one solve rather than two.</p>
  ${steady("frontier", (width) => Plot.plot({
    width, height: 380, marginLeft: 60, marginRight: 30,
    x: {label: `CO₂ in ${last}, t`, tickFormat: "s", reverse: true, grid: true},
    y: {label: "pathway cost", tickFormat: "s", grid: true},
    marks: [
      Plot.line(points, {x: "co2", y: "cost", z: "solar", sort: {channel: "x"}, stroke: "var(--theme-foreground-faintest)", strokeWidth: 1.5}),
      Plot.line(line, {x: "co2", y: "cost", stroke: "var(--theme-foreground-focus)", strokeWidth: 2}),
      Plot.line(tangent, {x: "co2", y: "cost", stroke: "var(--theme-foreground)", strokeWidth: 2, strokeDasharray: "5 4", clip: true}),
      Plot.dot(line, {x: "co2", y: "cost", fill: "var(--theme-foreground-focus)", r: 4, stroke: surface, strokeWidth: 2, channels: {cap: "capLabel", price: "price"}, tip: {format: {x: ",.0f", y: ",.0f", price: ",.0f"}}}),
      Plot.dot([here], {x: "co2", y: "cost", r: 8, stroke: "var(--theme-foreground)", strokeWidth: 2, fill: null}),
      Plot.text([here], {x: "co2", y: "cost", text: () => `${here.capLabel}: ${fmt.plain(here.price)} /t`, dy: -16, fill: "var(--theme-foreground)", fontWeight: 600}),
    ],
  }))}
</div>

<div class="card">
  <h2>Every point</h2>
  ${Inputs.table(points, {columns: ["capLabel", "solar", "cost", "co2", "price", "optimal"], header: {capLabel: "cap", solar: "solar cost", cost: "pathway cost", co2: `CO₂ in ${last}`, price: "carbon price"}, format: {solar: fmt.plain, cost: fmt.plain, co2: fmt.plain, price: fmt.plain}})}
</div>
