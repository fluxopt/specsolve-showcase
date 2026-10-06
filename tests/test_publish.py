"""A published directory serves every archive whole, and every path stacked across them, to a client that cannot glob."""

from pathlib import Path

import polars as pl
import pytest
from conftest import SOLVED

from showcase import warehouse


@pytest.fixture(scope='module')
def published(runs: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp('site') / 'runs'
    warehouse.publish(runs, out)
    return out


def test_every_archive_is_copied_whole(runs: Path, published: Path):
    for name in SOLVED:
        written = sorted(p.relative_to(runs / name) for p in (runs / name).rglob('*') if p.is_file())
        copied = sorted(p.relative_to(published / name) for p in (published / name).rglob('*') if p.is_file())
        assert copied == written, f'{name} is published as the solve wrote it'


def test_a_stacked_path_is_the_glob_it_stands_for(runs: Path, published: Path):
    stacked = pl.read_parquet(published / 'answer/primal/total.parquet').sort('specsolve_run', 'year', 'generator')
    globbed = pl.read_parquet(runs / '*' / 'answer/primal/total.parquet').sort('specsolve_run', 'year', 'generator')
    assert stacked.equals(globbed)


def test_the_stacked_catalogue_lists_every_file_it_points_at(published: Path):
    catalog = pl.read_parquet(published / 'catalog.parquet')
    assert sorted(catalog['specsolve_run'].unique()) == SOLVED, 'one catalogue across every run'
    for run, path in catalog.select('specsolve_run', 'path').unique().iter_rows():
        assert (published / run / path).is_file(), f'{run}/{path} is listed and not published'
        assert (published / path).is_file(), f'{path} is listed and not stacked'


def test_a_directory_already_there_is_refused(runs: Path, published: Path):
    with pytest.raises(FileExistsError):
        warehouse.publish(runs, published)
