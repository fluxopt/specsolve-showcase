"""The solve job writes the tree the dashboard reads, and refuses to write over it by accident."""

import itertools
from pathlib import Path

import polars as pl
import pytest
from conftest import SOLVED

from showcase.scenarios import SCENARIOS, YEARS
from showcase.solve import solve


def test_every_scenario_is_a_function_of_nothing():
    for scenario in SCENARIOS.values():
        sources = scenario.sources()
        assert set(sources) == {
            'day',
            'hour',
            'generator',
            'weight',
            'load',
            'avail',
            'invest',
            'cost',
            'rate',
            'cap',
            'existing',
        }, f'{scenario.name} supplies exactly the names the model declares'


def test_the_archive_holds_the_contract(runs: Path):
    for name in SOLVED:
        archive = runs / name
        assert (archive / 'spec.yaml').exists()
        assert (archive / 'sources.parquet').exists()
        assert (archive / 'answer' / 'record.parquet').exists()
        assert (archive / 'answer' / 'sweep.json').exists(), 'a sweep archive carries its manifest'
        total = pl.read_parquet(archive / 'answer' / 'primal' / 'total.parquet')
        assert sorted(total['year'].unique()) == YEARS, 'one frame holds every period'


def test_every_period_solved(runs: Path):
    for name in SOLVED:
        table = pl.read_parquet(runs / name / 'answer' / 'record.parquet')
        assert table['slice'].cast(pl.Int64).to_list() == YEARS, 'the periods come back in order'
        assert table['termination_condition'].unique().to_list() == ['optimal']
        assert table['specsolve_run'].unique().to_list() == [name], 'the record names the archive it sits in'


def test_each_period_inherits_the_last_fleet(runs: Path):
    """What a period started from is what the last one ended with: total - build == previous total."""
    total = pl.read_parquet(runs / 'base' / 'answer' / 'primal' / 'total.parquet')
    build = pl.read_parquet(runs / 'base' / 'answer' / 'primal' / 'build.parquet')
    started_from = total.join(build, on=['year', 'generator', 'specsolve_run'], suffix='_built').with_columns(
        (pl.col('value') - pl.col('value_built')).alias('inherited')
    )
    for earlier, later in itertools.pairwise(YEARS):
        ended = total.filter(pl.col('year') == earlier).sort('generator')['value']
        inherited = started_from.filter(pl.col('year') == later).sort('generator')['inherited']
        assert (ended - inherited).abs().max() < 1e-6, f'{later} did not start from what {earlier} left'


def test_an_existing_archive_is_refused_unless_replaced(runs: Path):
    with pytest.raises(Exception, match='already holds something'):
        solve('base', runs)
    solve('base', runs, replace=True)
