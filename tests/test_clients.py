"""Two clients, no client library: the archive is parquet, so anything that reads parquet is one.

The page these two feed claims they answer the same four questions off the same
directory. That claim is what this module holds them to — if one drifts, the
page is wrong and so is the argument the repository makes.
"""

import ast
import os
import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).parents[1]
SQL = ROOT / 'clients' / 'headline.sql'
NUMBERS = ['pathway_cost', 'emissions_cut', 'zero_carbon_share', 'carbon_price']

sys.path.insert(0, str(ROOT / 'clients'))
from headline import headline  # noqa: E402


def in_sql(runs: Path) -> dict[str, dict[str, float]]:
    """The SQL client, pointed at *runs* — the only edit a reader makes to run it elsewhere."""
    query = SQL.read_text().replace("'runs/", f"'{runs.as_posix()}/")
    rows = duckdb.sql(query).pl().to_dicts()
    return {row['run']: {k: row[k] for k in NUMBERS} for row in rows}


def test_the_two_clients_answer_the_same_four_questions(runs: Path):
    sql = in_sql(runs)
    assert sorted(sql) == ['base', 'cheap_solar'], 'one row per archive in the directory, named by it'
    for run, expected in sql.items():
        got = headline(runs / run)
        assert sorted(got) == sorted(NUMBERS), 'the polars client answers the four the page prints'
        for number in NUMBERS:
            assert got[number] == pytest.approx(expected[number], rel=1e-9), (
                f'{run}: {number} differs between the two clients'
            )


def test_the_client_needs_nothing_this_repository_ships():
    """It imports polars and the standard library and nothing else — the claim the page makes for it."""
    tree = ast.parse((ROOT / 'clients' / 'headline.py').read_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split('.')[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split('.')[0])
    assert imported == {'sys', 'pathlib', 'polars'}, 'no specsolve, no showcase warehouse, no client library'


def test_a_scenario_that_binds_its_cap_prices_carbon(runs: Path):
    """`cheap_solar` leaves the cap slack, so its shadow price is zero; the numbers are not all zero."""
    numbers = headline(runs / 'cheap_solar')
    assert numbers['carbon_price'] == 0.0, 'the cap does not bind in cheap_solar, so carbon is free'
    assert numbers['pathway_cost'] > 0 and 0 < numbers['zero_carbon_share'] <= 1


def test_the_clients_page_teaches_the_archive_rather_than_printing_a_result(runs: Path):
    """The page's job is to show the shape, the queries and the sources; the agreement is CI's job."""
    done = subprocess.run(
        [sys.executable, str(ROOT / 'site' / 'src' / 'clients.md.py')],
        env={**os.environ, 'SHOWCASE_RUNS': str(runs)},
        capture_output=True,
        check=True,
    )
    page = done.stdout.decode()
    assert page.startswith('---\ntitle: Clients\nsql:'), (
        'front matter first, and it registers the tables the queries read'
    )

    front = page.split('---')[1]
    for table in ('objective', 'metrics', 'digests', 'total', 'emissions'):
        assert f'{table}: ./data/runs/' in front, f'{table} is registered, so the live queries can reach it'

    for kind in ('primal/', 'dual/', 'expression/'):
        assert kind in page, f'the tree names {kind}, which is what the archive is made of'
    assert 'spec.yaml' in page and 'sources.parquet' in page

    assert page.count('```sql id=') == 2, 'the two record queries are live, and their SQL is shown'
    assert 'DuckDBClient.of(' in page and 'db.query(typed)' in page, 'and the last one is editable'

    for source in ('def headline(run: Path)', 'union_by_name = true'):
        assert source in page, 'both client sources are printed from the files that run'


def test_the_clients_page_says_when_there_is_nothing_to_read(tmp_path: Path):
    done = subprocess.run(
        [sys.executable, str(ROOT / 'site' / 'src' / 'clients.md.py')],
        env={**os.environ, 'SHOWCASE_RUNS': str(tmp_path)},
        capture_output=True,
    )
    assert done.returncode != 0
    assert b'holds no archive' in done.stderr


def test_the_sql_client_names_the_fix_when_there_is_no_archive(tmp_path: Path):
    """A wrong directory, or a fresh clone where the solve job has not run, is the likely first failure."""
    query = SQL.read_text().replace("'runs/", f"'{(tmp_path / 'runs').as_posix()}/")
    with pytest.raises(duckdb.Error) as raised:
        duckdb.sql(query).fetchall()
    assert 'showcase-solve' in str(raised.value), 'the message names the command that fixes it'
    assert 'repository root' in str(raised.value), 'and the directory it is run from'
