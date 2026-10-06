"""The queries read the archive directory as tables, and derive the run where the frame does not carry it."""

from pathlib import Path

from conftest import SOLVED as SCENARIOS

from showcase import warehouse
from showcase.scenarios import YEARS


def test_records_stack_every_run(runs: Path):
    table = warehouse.records(runs)
    assert table['run'].unique().sort().to_list() == SCENARIOS
    assert len(table) == len(SCENARIOS) * len(YEARS), 'one row per run and period'


def test_a_value_frame_names_its_run(runs: Path):
    table = warehouse.frame(runs, 'primal', 'total')
    assert table.columns == ['run', 'year', 'generator', 'value'], 'run first, then the columns of the model itself'
    assert table['run'].unique().sort().to_list() == SCENARIOS


def test_the_catalogue_is_read_off_the_archive(runs: Path):
    table = warehouse.catalogue(runs)
    listed = {(row['kind'], row['name']): row['dims'] for row in table.iter_rows(named=True)}
    assert listed[('primal', 'p')] == ['year', 'day', 'hour', 'generator']
    assert listed[('dual', 'balance')] == ['year', 'day', 'hour']
    assert listed[('expression', 'emissions')] == ['year']
    assert listed[('source', 'load')] == ['year', 'day', 'hour']
    assert ('source', 'day') not in listed, 'a table of labels has no value to plot'
    assert len(table) == len(listed), 'two runs of one model list each quantity once'


def test_the_changed_input_is_named(runs: Path):
    assert warehouse.changed_inputs(runs, 'base', 'cheap_solar') == ['invest'], (
        'cheap_solar changes the build cost and nothing else'
    )


def test_an_input_is_read_the_same_way(runs: Path):
    table = warehouse.frame(runs, 'source', 'load')
    assert table.columns == ['run', 'year', 'day', 'hour', 'value'], 'run first, then the columns the model declared'
    assert table['run'].unique().sort().to_list() == SCENARIOS
