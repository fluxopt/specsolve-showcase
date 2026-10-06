"""Solve on request, over the archive the site already reads.

The point of this module is how little of it there is. The archive is the
contract between the halves, so a second producer is additive: it writes the
same directories `showcase-solve` writes, and every reader — the site, a DuckDB
shell, `clients/` — keeps working with no change and no knowledge that a server
exists.

**There is no database.** A finished run is described by the archive it wrote,
which already records its status, its objective and when it was solved, so the
registry below is a query over the directory plus whatever this process still
has in flight. What that costs is history: an archive is keyed by scenario, so
re-solving one replaces it, and the registry says what is there now rather than
what has ever been asked for.

    uv sync --extra server
    uv run showcase-serve --runs runs
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

import polars as pl
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from server.jobs import Queue
from showcase import warehouse
from showcase.scenarios import SCENARIOS

INDEX = """<!doctype html><meta charset=utf-8><title>Solve server</title>
<body style="font:16px/1.5 system-ui;max-width:40rem;margin:4rem auto;padding:0 1rem">
<h1>Solve server</h1>
<p>A second producer over the archive the dashboard reads. It writes the same
directories <code>showcase-solve</code> writes, and holds no database.</p>
<ul>
  <li><a href="/runs">/runs</a> — what the archive describes, plus what is in flight</li>
  <li><a href="/docs">/docs</a> — the API</li>
</ul>
"""


def create_app(runs: Path) -> FastAPI:
    """The app, reading and writing *runs*.

    Args:
        runs: The archive directory, the same one the site's loader reads.
    """
    app = FastAPI(title='Solve server', summary='Solves scenarios into the archive the dashboard reads.')
    jobs = Queue(runs)

    def archived() -> dict[str, dict[str, Any]]:
        """What the directory says, read through the same client the site's loader uses."""
        if not any(runs.glob('*/answer/record.parquet')):
            return {}
        rows = (
            warehouse.records(runs)
            .group_by('run')
            .agg(
                periods=pl.len(),
                objective=pl.col('objective').sum(),
                solved_at=pl.col('solved_at').max(),
                optimal=pl.col('termination_condition').eq('optimal').all(),
            )
        )
        return {row.pop('run'): {'state': 'archived', **row} for row in rows.to_dicts()}

    @app.get('/', response_class=HTMLResponse, include_in_schema=False)
    def index() -> str:
        return INDEX

    @app.get('/runs', summary='Every scenario the archive describes, plus every one in flight')
    def list_runs() -> dict[str, dict[str, Any]]:
        registry = archived()
        for scenario, pending in jobs.in_flight().items():
            registry[scenario] = {'state': pending.state, 'submitted': pending.submitted, 'error': pending.error}
        return {name: registry.get(name, {'state': 'absent'}) for name in sorted(SCENARIOS)}

    @app.get('/runs/{scenario}', summary='One scenario')
    def read_run(scenario: str) -> dict[str, Any]:
        if scenario not in SCENARIOS:
            raise HTTPException(404, f'no such scenario: {scenario}. Try one of {sorted(SCENARIOS)}')
        return list_runs()[scenario]

    @app.post('/runs/{scenario}', status_code=202, summary='Solve one scenario, replacing its archive')
    def submit(scenario: str) -> dict[str, Any]:
        if scenario not in SCENARIOS:
            raise HTTPException(404, f'no such scenario: {scenario}. Try one of {sorted(SCENARIOS)}')
        try:
            pending = jobs.submit(scenario)
        except KeyError:
            raise HTTPException(409, f'{scenario} is already in flight; GET /runs/{scenario} for its state') from None
        return {'scenario': pending.scenario, 'state': pending.state, 'submitted': pending.submitted}

    return app


app = create_app(Path(os.environ.get('SHOWCASE_RUNS', 'runs')))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description='serve solves into the archive the dashboard reads')
    parser.add_argument('--runs', type=Path, default=Path('runs'), help='the directory the dashboard reads')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args(argv)

    import uvicorn

    uvicorn.run(create_app(args.runs), port=args.port)


if __name__ == '__main__':
    main()
