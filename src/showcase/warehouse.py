"""Queries over a directory of archives, with no specsolve in the process.

Every archive the solve job writes is a tree of parquet files, so the whole
directory is a table per glob. Every file carries ``specsolve_run``, which is
the archive's directory name; the tables here call it ``run``.
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import duckdb
import polars as pl

#: The kind of value frame each directory of an archive holds.
KINDS = {'answer/primal': 'primal', 'answer/dual': 'dual', 'answer/expression': 'expression', 'sources': 'source'}


def records(runs: Path) -> pl.DataFrame:
    """One row per run and period: how it terminated, what it reached, when."""
    return _union(runs, 'answer/record.parquet').sort('run', 'year')


def metrics(runs: Path) -> pl.DataFrame:
    """One row per run and period: how big the model was and what it cost to solve."""
    return _union(runs, 'answer/metrics.parquet').sort('run', 'year')


def inputs(runs: Path) -> pl.DataFrame:
    """One row per run and source: what each input's bytes digest to."""
    return _union(runs, 'sources.parquet').sort('run', 'source')


def catalogue(runs: Path) -> pl.DataFrame:
    """Every kind and name the archives hold, with the dimensions each is keyed by, in the order the file holds them.

    Listed by the ``catalog.parquet`` each archive carries, so a model with
    other variables lists other rows and nothing here has to change. A
    dimension's own labels carry no ``value`` and are left out.
    """
    glob = (runs.resolve() / '*' / 'catalog.parquet').as_posix()
    listed = duckdb.execute(
        """
        select distinct specsolve_run, path, name from read_parquet(?)
        where kind <> 'dimension' order by path, specsolve_run
        """,
        [glob],
    ).pl()
    rows = [
        {
            'kind': KINDS[path.rsplit('/', 1)[0]],
            'name': name,
            'dims': [c for c in pl.read_parquet_schema(runs / run / path) if c not in {'value', 'specsolve_run'}],
        }
        for run, path, name in listed.unique(subset='path', keep='first', maintain_order=True).iter_rows()
    ]
    return pl.DataFrame(rows, schema={'kind': pl.String, 'name': pl.String, 'dims': pl.List(pl.String)})


def frame(runs: Path, kind: str, name: str) -> pl.DataFrame:
    """One value frame across every run: ``(run, <dims…>, value)``."""
    path = next(k for k, v in KINDS.items() if v == kind)
    return _union(runs, f'{path}/{name}.parquet')


def changed_inputs(runs: Path, base: str, other: str) -> list[str]:
    """The sources whose bytes differ between two runs, by name."""
    digests = inputs(runs).pivot('run', index='source', values='digest')
    return digests.filter(pl.col(base) != pl.col(other))['source'].sort().to_list()


def bundle(runs: Path) -> bytes:
    """The whole directory as one zip: the record tables, one frame per catalogue entry across every run, the catalogue, and the model.

    What the site ships, whichever directory it reads: the scenarios and the
    what-if grid are bundled by the same call.
    """

    def parquet(table: pl.DataFrame) -> bytes:
        buffer = io.BytesIO()
        table.write_parquet(buffer)
        return buffer.getvalue()

    listed = catalogue(runs)
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('record.parquet', parquet(records(runs)))
        zf.writestr('metrics.parquet', parquet(metrics(runs)))
        zf.writestr('sources.parquet', parquet(inputs(runs)))
        for row in listed.iter_rows(named=True):
            zf.writestr(f'{row["kind"]}/{row["name"]}.parquet', parquet(frame(runs, row['kind'], row['name'])))
        zf.writestr('catalogue.json', json.dumps(listed.to_dicts(), indent=1))
        zf.writestr('spec.yaml', next(iter(sorted(runs.glob('*/spec.yaml')))).read_text())
    return out.getvalue()


def _union(runs: Path, member: str) -> pl.DataFrame:
    """One file of every archive, stacked, with ``specsolve_run`` as ``run`` and a record's slice as ``year``."""
    glob = (runs.resolve() / '*' / member).as_posix()
    table = duckdb.execute('select * from read_parquet(?, union_by_name = true)', [glob]).pl()
    if 'slice' in table.columns:
        table = table.with_columns(pl.col('slice').cast(pl.Int64).alias('year')).drop('slice_axis', 'slice')
    return table.rename({'specsolve_run': 'run'}).select('run', pl.exclude('run'))
