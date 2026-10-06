"""Nothing past the solve job imports specsolve, and the site's loader ships what the pages read."""

import ast
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
LOADER = ROOT / 'site' / 'src' / 'data' / 'runs.zip.py'
GRID_LOADER = ROOT / 'site' / 'src' / 'data' / 'grid.zip.py'
MODEL_PAGE = ROOT / 'site' / 'src' / 'model.md.py'
ANNEX = ROOT / 'src' / 'showcase' / 'annex.py'
ANNEX_PAGE = ROOT / 'site' / 'src' / 'annex.md.py'
READERS = [ROOT / 'src' / 'showcase' / 'warehouse.py', ANNEX, LOADER, GRID_LOADER, MODEL_PAGE, ANNEX_PAGE]


def imported_by(module: Path) -> set[str]:
    names = set()
    for node in ast.walk(ast.parse(module.read_text())):
        if isinstance(node, ast.Import):
            names.update(alias.name.split('.')[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split('.')[0])
    return names


@pytest.mark.parametrize('module', READERS, ids=lambda p: p.name)
def test_a_reader_imports_no_specsolve(module: Path):
    assert 'specsolve' not in imported_by(module), f'{module.name} reads parquet; only the solve job imports specsolve'


def test_the_loader_ships_every_table(runs: Path, tmp_path: Path):
    """The zip the pages read: the record tables, one frame per catalogue entry, the catalogue and the model."""
    done = subprocess.run(
        [sys.executable, str(LOADER)],
        env={**os.environ, 'SHOWCASE_RUNS': str(runs)},
        capture_output=True,
        check=True,
    )
    out = tmp_path / 'runs.zip'
    out.write_bytes(done.stdout)
    names = set(zipfile.ZipFile(out).namelist())
    assert {'record.parquet', 'metrics.parquet', 'sources.parquet', 'catalogue.json', 'spec.yaml'} <= names
    assert {
        'primal/total.parquet',
        'dual/balance.parquet',
        'expression/emissions.parquet',
        'source/load.parquet',
    } <= names
    assert 'source/day.parquet' not in names, 'a table of labels is not shipped'


def test_the_loader_says_when_there_is_nothing_to_read(tmp_path: Path):
    done = subprocess.run(
        [sys.executable, str(LOADER)], env={**os.environ, 'SHOWCASE_RUNS': str(tmp_path)}, capture_output=True
    )
    assert done.returncode != 0
    assert b'holds no archive' in done.stderr


def test_the_grid_loader_ships_what_the_what_if_page_reads(grid: Path, tmp_path: Path):
    """The grid is bundled exactly as the scenarios are, and holds the two inputs the sliders move and the dual they show."""
    done = subprocess.run(
        [sys.executable, str(GRID_LOADER)],
        env={**os.environ, 'SHOWCASE_GRID': str(grid)},
        capture_output=True,
        check=True,
    )
    out = tmp_path / 'grid.zip'
    out.write_bytes(done.stdout)
    names = set(zipfile.ZipFile(out).namelist())
    assert {
        'record.parquet',
        'primal/total.parquet',
        'expression/emissions.parquet',
        'dual/carbon.parquet',
        'source/cap.parquet',
        'source/invest.parquet',
        'source/rate.parquet',
    } <= names


def test_the_grid_loader_names_its_own_command(tmp_path: Path):
    done = subprocess.run(
        [sys.executable, str(GRID_LOADER)], env={**os.environ, 'SHOWCASE_GRID': str(tmp_path)}, capture_output=True
    )
    assert done.returncode != 0
    assert b'showcase-grid' in done.stderr


def test_the_model_page_typesets_what_was_solved(runs: Path):
    """The page loader prints the archive's spec as math, in the site's own delimiters rather than GitHub's."""
    done = subprocess.run(
        [sys.executable, str(MODEL_PAGE)],
        env={**os.environ, 'SHOWCASE_RUNS': str(runs)},
        capture_output=True,
        check=True,
    )
    page = done.stdout.decode()
    assert page.startswith('---\ntitle: Model\n---'), 'a page loader prints front matter first'
    assert '```tex\n\\min' in page, 'the objective is a TeX block'
    assert '${tex`\\mathcal{G}`}' in page, 'a symbol in the legend is inline TeX'
    assert '```math' not in page and '$`' not in page, "none of GitHub's delimiters survive"
    assert 'accumulate' in page and 'existing' in page, 'the constraint that carries the fleet is printed'
    assert 'x^{0}' in page and 'E^{\\max}' in page, 'the symbol table is applied, not the derived names'
