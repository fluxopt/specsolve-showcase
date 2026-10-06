---
title: Provenance
sql:
  objective: ./data/runs/record.parquet
  metrics: ./data/runs/metrics.parquet
  sources: ./data/runs/sources.parquet
---

# Where the numbers came from

Each archive records how every period terminated, what the model cost to build and solve, a digest of the spec it answered, and a digest of every input. So two runs can say which input differs between them without reading either one.

```sql id=runs
select distinct run from sources order by run
```

```js
const scenarios = runs.toArray().map((d) => d.run);
const one = view(Inputs.select(scenarios, {label: "Between"}));
const other = view(Inputs.select(scenarios, {label: "and", value: scenarios[1] ?? scenarios[0]}));
```

```sql id=changed
select a.source
from sources a join sources b using (source)
where a.run = ${one} and b.run = ${other} and a.digest <> b.digest
order by source
```

<div class="card">
  <h2>Which input differs</h2>
  <p>${changed.numRows ? changed.toArray().map((d) => html`<code>${d.source}</code>`) : html`<em>the same bytes on every input</em>`}</p>
</div>

```sql id=solves
select run, year::integer as year, status, termination_condition, objective, spec_digest, solved_at from objective order by run, year
```

```sql id=cost
select run, year::integer as year, columns, rows, nonzeros, build_seconds, solve_seconds from metrics order by run, year
```

<div class="card">
  <h2>Each solve</h2>
  ${Inputs.table(solves, {format: {year: (d) => String(d), objective: (d) => d.toLocaleString("en", {maximumFractionDigits: 0})}})}
</div>

<div class="card">
  <h2>What it cost</h2>
  ${Inputs.table(cost, {format: {year: (d) => String(d), build_seconds: (d) => d.toFixed(3), solve_seconds: (d) => d.toFixed(3)}})}
</div>

<div class="card">
  <h2>The model, as solved</h2>
  <pre>${await FileAttachment("data/runs/spec.yaml").text()}</pre>
</div>
