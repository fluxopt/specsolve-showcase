# specsolve-showcase

An example of what you build on [specsolve](https://github.com/fluxopt/specsolve):
a capacity-expansion planner, shaped the way a production application is: a **solve job** that writes
archives, an **archive directory** that is the contract between the halves, and
an **interactive site** that reads the archives in the browser and never
imports specsolve. GitHub Actions runs the job and publishes the site to GitHub
Pages, so there is no server anywhere.

**Live:** <https://fluxopt.github.io/specsolve-showcase/>

```text
showcase-solve ──┐                                    ┌──▶ observable build ──▶ GitHub Pages
   (specsolve)      ├──▶ runs/<scenario>/ ───────────────┤     (Python loaders)     (DuckDB-WASM
showcase-serve ──┘      (parquet + yaml)              │                           + Plot
   (specsolve, on request)                               ├──▶ clients/, a DuckDB shell, a notebook
showcase-grid ─────▶ grid/<point>/ ───────────────────┘
   (specsolve, 110 points)  (the same archive)
```

The point of the repository is the middle box. specsolve archives a solve as tidy
parquet: one file per variable, dual and named expression, keyed by the model's
own dimensions, with a `value` column. A directory of archives is therefore a
table per glob, and anything that reads parquet is already a client. The site
is one such client. So is a DuckDB shell, a notebook, or a BI tool pointed at
the same directory.

## Run it

Requires Python 3.12, [uv](https://docs.astral.sh/uv/) and Node 20 or later.

```bash
uv sync --all-extras
uv run showcase-solve --runs runs       # four scenarios, four periods each, a few seconds
uv run showcase-grid --runs grid        # the what-if grid: 110 pathways, in parallel, about ten seconds
uv run marimo export html notebooks/session.py -o site/src/session.html
cd site && npm ci && npm run dev        # the site, live, with the loader re-run on edit
uv run marimo edit notebooks/session.py # the notebook, live, with a local kernel
```

`showcase-solve base` solves one scenario. An archive is written whole, so a
directory that already exists is refused; `--replace` removes it first.

## What the model is

[`models/pathway.yaml`](models/pathway.yaml) is one investment period of a
pathway: what to build, and how the fleet runs on three typical days of 24
hours. It never mentions the period. The solve job slices every source to one
year, runs the periods in order, and hands each period's standing capacity to
the next as its `existing` fleet. The addition `total == existing + build` is a
constraint in the file, where a reviewer reads it, and not arithmetic in the
driver.

The file also names three expressions, `capex`, `opex` and `emissions`, and a
`carbon` constraint over the last of them. Naming a quantity once means the
number the constraint bounds and the number the site plots are one definition.

Four scenarios live in [`src/showcase/scenarios.py`](src/showcase/scenarios.py),
each a function that returns the model's sources. Only data differs:

| scenario | what changes |
|---|---|
| `base` | the reference assumptions |
| `cheap_solar` | solar builds at 60% of the reference cost |
| `high_demand` | demand grows twice as fast |
| `carbon_cap` | a CO2 cap that tightens every period, and binds in the last |

## What the archive holds

Every `runs/<scenario>/` is what `sps.solve_over(…, archive=)` wrote:

```text
runs/base/
    spec.yaml                           the spec, as solved
    catalog.parquet                     (specsolve_run, path, name, kind, description, dtype, column, dim)
    sources/<name>.parquet              every input, as solved
    sources.parquet                     (specsolve_run, source, digest)
    axis.json                           how the sources were sliced
    answer/
        record.parquet                  (slice_axis, slice, status, termination_condition, objective, …, specsolve_run)
        metrics.parquet                 (slice_axis, slice, rows, columns, nonzeros, …, specsolve_run)
        primal/<variable>.parquet       (year, <dims…>, value, specsolve_run)
        dual/<constraint>.parquet       the same shape, for a shadow price
        expression/<name>.parquet       the same shape, for a named expression
```

Two rules make a directory of these a warehouse, and
[`src/showcase/warehouse.py`](src/showcase/warehouse.py) is the whole Python
client:

- **Every file carries `specsolve_run`**, the archive's directory name, so
  any one of them concatenates across archives with a single glob, such as
  `read_parquet('runs/*/answer/primal/total.parquet')`.
- **The archive carries its catalogue.** `catalog.parquet` lists every
  quantity, its kind, its path and the dimensions that key it. Nothing is
  declared twice.

From a DuckDB shell, the same directory:

```sql
select specsolve_run as run, slice::integer as year, objective
from read_parquet('runs/*/answer/record.parquet', union_by_name = true)
order by run, year;
```

Both need `runs/` to exist: it is what the solve job writes, and it is not
checked in.

[`clients/`](clients/) takes that further: `headline.py` and `headline.sql`
answer the same four questions off the archive, in polars and in DuckDB, and
neither imports anything this repository ships. `tests/test_clients.py` holds
them to each other on every archive in the directory, and the site's
**Clients** page prints both sources beside the numbers each returned at build
time.

## How the site reads it

The site is an [Observable Framework](https://observablehq.com/framework/)
app under [`site/`](site/). Its one data loader,
[`site/src/data/runs.zip.py`](site/src/data/runs.zip.py), runs the warehouse
queries above at build time and ships the result as a zip of parquet files,
one per quantity across every run. Each page registers the tables it needs in
its front matter and queries them with SQL, run by DuckDB-WASM in the
browser; the charts are [Observable Plot](https://observablehq.com/plot/), and
every input re-runs only the cells that depend on it.

A third loader, [`site/src/perspective.css.js`](site/src/perspective.css.js),
prints Perspective's own stylesheet out of the installed package, because that
stylesheet carries the labels its settings panel prints. Reading it from
`node_modules` at build time is what keeps a copy of it out of the tree.

A second loader, [`site/src/model.md.py`](site/src/model.md.py), prints a
whole page: the spec out of the archive, typeset as equations by the
language's own `to_markdown`, in the notation
[`models/pathway.symbols.yaml`](models/pathway.symbols.yaml) declares. A
symbol that names nothing in the model fails the build. It imports [mathspec](https://github.com/energy-models/mathspec),
the language package, which has no solver in it. No data binds and nothing is
solved to produce that page, so the math it shows is exactly what the YAML
states, and the other pages show what the solver made of it.

**Annex** is the two halves joined. Every declaration the archive holds is
typeset in the same notation the model page uses, and under each equation is
what the solver made of it: how many rows a constraint has, how many of them
carry a non-zero price, and the largest price among them; what a named
expression came to in each period; what a variable was free to choose. The
join is [`src/showcase/annex.py`](src/showcase/annex.py), which imports no
specsolve — the equations come from mathspec and the numbers come from the
parquet. An annex is about one run, and any of them prints:

```bash
uv run showcase-annex carbon_cap --runs runs
```

That stitching is the whole reason
[`fluxopt/specsolve#1648`](https://github.com/fluxopt/specsolve/issues/1648) is open:
the typesetter renders a model, the result frames carry the answer, and holding
one against the other is left to every caller that wants the page.

**What if** is the page that makes a static site feel like a solver. The
questions the notebook's two sliders ask — a tighter CO2 cap in the last
period, a different solar build cost — have a finite set of answers worth
asking, so [`showcase-grid`](src/showcase/solve.py) solves all of them ahead of
time: 10 caps by 11 solar costs, 110 pathways, 440 solves, in about ten seconds
on a laptop. Each point is archived exactly as a scenario is, under
`grid/<point>/`, and [`site/src/data/grid.zip.py`](site/src/data/grid.zip.py)
bundles that directory with the same `warehouse.bundle` the scenarios use. The
page takes each point's cap and solar cost from its archived sources, not from
its name. Moving a slider then looks up an archive rather than solving one, so
the page answers on a phone from about 20 KB of parquet. It draws
the whole grid at once as two heatmaps, cost and carbon price, where a click
moves the sliders. It also draws the cost-emissions frontier with a tangent
whose slope is the dual of the cap: the price the solver returns is the rate
at which cost rises as the cap tightens, read off one solve rather than two.

Three pages know the model by name, because they tell its story. **Pathway**
leads with four headline numbers, breaks the cost into building and running
per technology, sets emissions against the cap, and compares two scenarios as
a difference; clicking a period there selects it, and a link carries the
scenario and period into **Dispatch**, where a slider moves through the
periods over all three typical days with the net load drawn, and a heatmap
shows the price by hour and period. **Provenance** shows what was solved and
what differs between runs. **Clients** reads the archive twice more, in ten
lines of polars and one DuckDB query, to show that the directory needs no
client library at all. **Explore** knows nothing. It lists every quantity
in the catalogue and hands one to a
[Perspective](https://perspective.finos.org/) pivot table, keyed by the
dimensions it reads off the parquet: the model's own dimensions group the rows,
the scenario splits the columns, and re-pivoting, filtering and charting are
the component's, not the page's. Point the solve job at a different specsolve
model and that page shows it unchanged. That is the property this repository
exists to demonstrate.

## The modelling session

The site is what specsolve produces unattended. [`notebooks/session.py`](notebooks/session.py)
is the other half: a [marimo](https://marimo.io) notebook in which the model
is a document you edit by hand. A dispatch model sits in a code cell; change
it and the typeset math, the validation and the solve all re-run, because
every cell that reads it depends on it. A data editor changes the cost table,
and two sliders re-solve the pathway with a different cap and solar cost.

```bash
uv run marimo edit notebooks/session.py
```

The site's **Session** page runs the notebook in the browser: in run mode by
default, where the model, the data and the sliders are live and the code is
out of sight, and in edit mode one link away.
marimo's WASM export loads Python through Pyodide, whose distribution carries highspy, polars
and the rest of specsolve's dependencies. `tools/wasm_bundle.py` puts specsolve
and mathspec, at the versions locked here, and this repository's own wheel beside the page,
with the pathway model, and the notebook's first cell installs them when it
finds itself under Pyodide. Nothing runs on a server. The page also links the
notebook as it ran at the last build, a static export, as the fallback.

## What the checks say

`uv run pytest` solves two scenarios into a temporary directory and asserts:

- the archive holds the tree above, every period solved to optimality, and
  each period started from the fleet the last one left;
- the warehouse queries name the run on every row, list the catalogue from the
  archive's own `catalog.parquet`, and name `invest` as the one input `cheap_solar` changed;
- every point of the what-if grid supplies the model's inputs, caps only the
  last period, and archives the cap and solar cost the page keys it by; the
  grid's loader ships the tables the page reads;
- nothing past the solve job imports specsolve; the site's data loader ships every
  table the pages read, or says what is missing; and the model page prints the
  archived spec as TeX in the site's own delimiters;
- the notebook runs top to bottom and exports with both solves optimal.

CI runs the same, then the pipeline end to end: the job and the grid, then the site build.
A push to `main` also deploys the site to GitHub Pages.

## Solving on request

[`server/`](server/) is the second producer, and it exists to show that adding
one is additive rather than a rewrite. It writes the same directories
`showcase-solve` writes, so every reader above — the site, `clients/`, a DuckDB
shell — keeps working with no change and no knowledge that it is running.

```bash
uv sync --extra server
uv run showcase-serve --runs runs     # then POST /runs/base, GET /runs
```

**It holds no database.** A finished run is described by the archive it wrote,
which already records its status, its objective and when it was solved, so
`GET /runs` is a query over the directory plus whatever this process still has
in flight. A second server over the same directory reports the same registry,
which `tests/test_server.py` asserts.

What that costs is history. An archive is keyed by scenario, so re-solving one
replaces it, and the registry says what is there now rather than what has ever
been asked for. Keeping the second thing is a run registry, and a run registry
is a table about people and process rather than about the model — it is not in
this repository and it is not in specsolve.

## What it is not

There is no authentication, no container and no database. Each would sit on the
same contract, and none is needed to show it; the first of them that is
genuinely needed is the point at which `server/` stops being an illustration.
The numbers are synthetic and chosen so that the periods and the scenarios
answer differently.
