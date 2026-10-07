"""The solve job: one archive per scenario, written where the dashboard reads.

This is the only module that imports specsolve. It runs the pathway one period at
a time, each period inheriting the fleet the last one left, and archives the
spec, the sources and the answer under ``<runs>/<scenario>/``.

    showcase-solve --runs runs            # every scenario
    showcase-solve --runs runs base       # one of them
    showcase-solve --runs runs --replace  # over what a previous job wrote
    showcase-grid --runs grid             # the what-if grid, one archive per point
"""

from __future__ import annotations

import argparse
import os
import shutil
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import specsolve as sps

from showcase.scenarios import SCENARIOS, Scenario, grid

MODEL = Path(__file__).parents[2] / 'models' / 'pathway.yaml'


def solve(scenario: str, runs: Path, *, replace: bool = False, cases: dict[str, Scenario] = SCENARIOS) -> Path:
    """Solve one scenario into ``runs/<scenario>/`` and return that directory.

    An archive is written whole, so a directory that already exists is refused
    unless ``replace`` is set. The archive is written under a hidden directory
    of ``runs`` and renamed into place, so a reader globbing ``runs/*/`` never
    sees one half-written, and an archive being replaced stays readable until
    the new one lands. Every period is asserted to have solved to optimality
    before it lands: a dashboard that quietly shows a partial pathway is worse
    than a job that fails. ``cases`` is where the name is looked up: the four
    scenarios, or the points of :func:`grid`.
    """
    target = runs / scenario
    if target.exists() and not replace:
        raise FileExistsError(f'{target} already holds something; pass replace=True to solve it again')
    runs.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=runs, prefix='.') as staging:
        written = Path(staging) / scenario
        runs_ = sps.solve_over(
            MODEL,
            cases[scenario].sources(),
            sps.EachCoordinate('year'),
            carry={'existing': 'total'},
            archive=written,
        )
        conditions = runs_.record['termination_condition'].to_list()
        assert all(c == 'optimal' for c in conditions), (
            f'{scenario}: a period did not solve to optimality: {conditions}'
        )
        if target.exists():
            target.rename(Path(staging) / 'replaced')
        written.rename(target)
    return target


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description='solve the pathway and archive each scenario')
    parser.add_argument('scenarios', nargs='*', choices=[*SCENARIOS, []], help='which to solve; all by default')
    parser.add_argument('--runs', type=Path, default=Path('runs'), help='the directory the dashboard reads')
    parser.add_argument('--replace', action='store_true', help='remove an archive that is already there')
    args = parser.parse_args(argv)
    for name in args.scenarios or list(SCENARIOS):
        target = solve(name, args.runs, replace=args.replace)
        print(f'{name}: archived at {target}')  # noqa: T201


def _solve_point(name: str, runs: Path) -> Path:
    return solve(name, runs, cases=grid())


def grid_main(argv: list[str] | None = None) -> None:
    """Solve every point of the grid, in parallel, into one directory of archives.

    The same archive as a scenario's, so every reader of ``runs/`` reads this
    directory too. ``--replace`` removes the whole directory first, so a point
    dropped from the grid does not linger in it.
    """
    parser = argparse.ArgumentParser(description='solve the what-if grid and archive each point')
    parser.add_argument('--runs', type=Path, default=Path('grid'), help='the directory the what-if page reads')
    parser.add_argument('--replace', action='store_true', help='remove the directory first')
    parser.add_argument('--jobs', type=int, default=os.cpu_count(), help='solves in flight at once')
    args = parser.parse_args(argv)
    if args.replace and args.runs.exists():
        shutil.rmtree(args.runs)
    names = list(grid())
    with ProcessPoolExecutor(args.jobs) as pool:
        done = list(pool.map(_solve_point, names, [args.runs] * len(names)))
    print(f'{len(done)} points: archived under {args.runs}')  # noqa: T201


if __name__ == '__main__':
    main()
