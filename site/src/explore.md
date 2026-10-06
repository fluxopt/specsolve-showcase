---
title: Explore
---

# Explore the archive

This page knows nothing about the model. It lists every quantity the archives hold, reads each one's dimensions off the parquet, and pivots on them: the model's own dimensions group the rows, the scenario splits the columns. Point the solve job at a different specsolve model and this page shows it unchanged.

```js
import {pivot} from "./components/pivot.js";

const archive = FileAttachment("data/runs.zip").zip();
document.head.append(html`<style>${await FileAttachment("perspective.css").text()}</style>`);
const {perspective} = await import(await FileAttachment("perspective.js").url());
const client = await perspective.worker();
```

```js
const catalogue = await archive.file("catalogue.json").json();
const entries = catalogue.map((d) => ({...d, label: `${d.kind}: ${d.name}`, table: `${d.kind}_${d.name}`}));
const db = await DuckDBClient.of(Object.fromEntries(entries.map((d) => [d.table, archive.file(`${d.kind}/${d.name}.parquet`)])));
```

```js
const picked = view(Inputs.select(entries, {label: "Quantity", format: (d) => d.label, value: entries.find((d) => d.kind === "primal") ?? entries[0]}));
```

```js
const rows = (await db.query(`select * from "${picked.table}"`)).toArray();
const viewer = await pivot(client, rows, picked);
```

<div class="card">
  <h2>${picked.name} <span class="muted">(${picked.kind}), keyed by ${picked.dims.join(", ") || "nothing"}</span></h2>
  <p class="muted">Drag a dimension between <em>Group By</em>, <em>Split By</em> and <em>Where</em> to re-pivot, or change the plugin to chart it. Nothing on this page is written per quantity.</p>
  ${viewer}
</div>

<style>
/* A custom element is inline by default, so it takes no height until it is told to. */
perspective-viewer { display: block; height: 600px; }
</style>
