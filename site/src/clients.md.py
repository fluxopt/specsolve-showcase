"""Reading the archive: what is in it, what a query gets back, and how to run one yourself.

A page loader, because two of its sections are facts about the directory on
disk — the tree the solve job wrote, and the source of the two clients in
`clients/`. Everything else on the page is a live query, run by DuckDB in the
reader's browser against the same parquet the other pages read.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
runs = Path(os.environ.get('SHOWCASE_RUNS', '../runs'))
archives = sorted(p.parent.name for p in runs.glob('*/spec.yaml'))
if not archives:
    sys.exit(f'{runs.resolve()} holds no archive: run `showcase-solve --runs {runs}` first')

run = archives[0]


def kb(path: Path) -> str:
    return f'{path.stat().st_size / 1024:.1f} kB'


def tree(root: Path) -> str:
    """The archive's shape rather than its file list: what each directory is for, and how much of it there is."""
    answer = root / 'answer'
    rows = [
        ('├── spec.yaml', kb(root / 'spec.yaml'), 'the spec, as solved'),
        ('├── catalog.parquet', kb(root / 'catalog.parquet'), 'every name, its kind, path and dimensions'),
        ('├── sources.parquet', kb(root / 'sources.parquet'), '(specsolve_run, source, digest)'),
        ('├── sources/', f'{len(list((root / "sources").glob("*.parquet")))} files', 'every input, as solved'),
        ('└── answer/', '', ''),
        ('    ├── record.parquet', kb(answer / 'record.parquet'), 'one row per period: status, objective'),
        ('    ├── metrics.parquet', kb(answer / 'metrics.parquet'), 'one row per period: size, seconds'),
    ]
    kinds = [d for d in ('primal', 'dual', 'expression') if (answer / d).is_dir()]
    for index, kind in enumerate(kinds):
        quantities = sorted(q.stem for q in (answer / kind).glob('*.parquet'))
        elbow = '    └──' if index == len(kinds) - 1 else '    ├──'
        rows.append((f'{elbow} {kind}/', f'{len(quantities)} files', ', '.join(quantities)))
    return '\n'.join(f'{name:<28}{size:>9}   {gloss}'.rstrip() for name, size, gloss in rows)


sources = {name: (ROOT / 'clients' / name).read_text().rstrip() for name in ('headline.py', 'headline.sql')}

sys.stdout.write(f"""---
title: Clients
sql:
  objective: ./data/runs/record.parquet
  metrics: ./data/runs/metrics.parquet
  digests: ./data/runs/sources.parquet
  total: ./data/runs/primal/total.parquet
  emissions: ./data/runs/expression/emissions.parquet
---

# Reading the archive

Every other page here is a client. So is a DuckDB shell, a notebook, and a BI tool pointed at the directory. None of them is privileged, because **the contract is the directory, not a library** — and this page is where you learn to read it.

Every result below is a real query, run by DuckDB in your browser against the same parquet the dashboard reads. The SQL is above each one, and you can change the last one.

## What the solve job wrote

One archive per scenario. This is `{run}`, by shape rather than by file — every quantity is one file, every period in it:

```text
runs/{run}/
{tree(runs / run)}
```

Three kinds of thing are in there. **`spec.yaml` and `sources/`** are what was solved — the spec and every input, so the run reproduces. **`answer/`** is what came back: `primal/` per variable, `dual/` per constraint, `expression/` per named quantity, one file each. **`record.parquet`, `metrics.parquet` and `sources.parquet`** are the record: one row per period saying how it terminated, what it cost to build and solve, and what each input's bytes digest to.

## What a query gets back

A value frame carries the model's own dimensions, a `value`, and the run it came from. Nothing else, and no index:

```sql id=shape
select * from total order by run, year, generator limit 6
```

```js
display(Inputs.table(shape, {{maxHeight: 220}}));
```

Those column names — `year`, `generator` — are the model's, not this repository's. They come from the spec that was solved, which is why a reader who has never seen the model can still group by `generator`, and why two quantities keyed the same way join without a mapping table.

## Two rules, one query each

**Every file carries `specsolve_run`**, the archive's directory name, so any file concatenates across archives with a single glob and needs no path parsing. The site's loader calls it `run`, and reads the period off the record's `slice`:

```sql id=records
select run, year, termination_condition, round(objective) as objective from objective order by run, year limit 5
```

```js
display(Inputs.table(records, {{maxHeight: 200}}));
```

**The archive carries its own catalogue.** `catalog.parquet` lists every quantity, its kind, its path and the dimensions that key it, written by the solve. Nothing is declared twice:

```js
const catalogue = await FileAttachment("data/runs.zip").zip().then((z) => z.file("catalogue.json")).then((f) => f.json());
display(Inputs.table(catalogue.map((d) => ({{kind: d.kind, name: d.name, "keyed by": d.dims.join(", ") || "nothing"}})), {{maxHeight: 260}}));
```

## Run one yourself

The tables above are registered; edit the query and it re-runs. `objective`, `metrics`, `digests`, `total` and `emissions` are in scope.

```js
const db = await DuckDBClient.of({{
  objective: FileAttachment("data/runs/record.parquet"),
  metrics: FileAttachment("data/runs/metrics.parquet"),
  digests: FileAttachment("data/runs/sources.parquet"),
  total: FileAttachment("data/runs/primal/total.parquet"),
  emissions: FileAttachment("data/runs/expression/emissions.parquet"),
}});
```

```js
const typed = view(Inputs.textarea({{
  label: "SQL",
  rows: 4,
  submit: "Run",
  value: "select run, year, sum(value) as capacity\\nfrom total\\ngroup by run, year\\norder by run, year",
}}));
```

```js
const answer = await db.query(typed).then((rows) => Inputs.table(rows, {{maxHeight: 300}}))
  .catch((error) => html`<div class="warning" style="padding:0.5rem 1rem"><b>${{error.name}}</b>: ${{error.message}}</div>`);
display(answer);
```

## The same thing, in your own tools

Neither of these imports specsolve, and neither imports this repository's `warehouse.py`. Both answer the four numbers the [pathway page](./) leads with, and `tests/test_clients.py` holds them to each other on every archive in the directory — so a drift between them fails CI rather than reaching this page.

<details><summary><b>Ten lines of polars</b> — <code>uv run python clients/headline.py runs/{run}</code></summary>

```python
{sources['headline.py']}
```

</details>

<details><summary><b>One DuckDB query</b>, every scenario at once — <code>duckdb -c ".read clients/headline.sql"</code></summary>

`runs/` is written by the solve job rather than checked in, and the globs are
relative, so both of these matter:

```bash
uv run showcase-solve --runs runs     # once, if runs/ is not there yet
duckdb -c ".read clients/headline.sql"
```

Get either wrong and the query says which one to run, rather than reporting a
path that does not exist.

```sql
{sources['headline.sql']}
```

</details>
""")
