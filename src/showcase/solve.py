"""The solve job: one archive per scenario, written where the dashboard reads.

This is the only module that imports specsolve. It runs the pathway one period at
a time, each period inheriting the fleet the last one left, and archives the
spec, the sources and the answer under ``<runs>/<scenario>/``.

    showcase-solve --runs runs            # every scenario
    showcase-solve --runs runs base       # one of them
    showcase-solve --runs runs --replace  # over what a previous job wrote
    showcase-grid --runs grid             # the what-if grid, one archive per point
    showcase-hedge --runs hedge           # one period planned against many futures
"""

from __future__ import annotations

import argparse
import multiprocessing
import os
import shutil
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import polars as pl
import specsolve as sps

from showcase.scenarios import OMEGAS, SCENARIOS, Scenario, alone, expected, futures, grid, hedge_sources

MODEL = Path(__file__).parents[2] / 'models' / 'pathway.yaml'
HEDGE = Path(__file__).parents[2] / 'models' / 'hedge.yaml'


def solve(scenario: str, runs: Path, *, replace: bool = False, cases: dict[str, Scenario] = SCENARIOS) -> Path:
    """Solve one scenario into ``runs/<scenario>/`` and return that directory.

    An archive is written whole, so a directory that already exists is refused
    unless ``replace`` is set, in which case it is removed first. Every period
    is asserted to have solved to optimality: a dashboard that quietly shows a
    partial pathway is worse than a job that fails. ``cases`` is where the
    name is looked up: the four scenarios, or the points of :func:`grid`.
    """
    target = runs / scenario
    if replace and target.exists():
        shutil.rmtree(target)
    runs_ = sps.solve_over(
        MODEL,
        cases[scenario].sources(),
        sps.EachCoordinate('year'),
        carry={'existing': 'total'},
        archive=target,
    )
    conditions = runs_.record['termination_condition'].to_list()
    assert all(c == 'optimal' for c in conditions), f'{scenario}: a period did not solve to optimality: {conditions}'
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


def hedge_cases() -> dict[str, dict[str, pl.DataFrame]]:
    """The sources of every archive the hedge writes, by archive name, but the one that depends on another's answer.

    ``risk-<omega>`` is the plan at one weight on the tail, in hundredths.
    ``perfect-<future>`` is the plan that knew which future would arrive.
    ``average`` is the plan against the expected future alone; the solve job
    then runs its fleet in every future as ``average-tested``.
    """
    drawn = futures()
    plan = hedge_sources(drawn)
    return {
        **{f'risk-{round(omega * 100):03d}': hedge_sources(drawn, omega=omega) for omega in OMEGAS},
        **{f'perfect-{f.name}': alone(plan, f.name) for f in drawn},
        'average': expected(plan),
    }


def solve_hedge(name: str, sources: dict[str, pl.DataFrame], runs: Path) -> dict[str, float]:
    """Solve the hedge once into ``runs/<name>/`` and return what it built, by generator.

    Asserted optimal, as a scenario is.
    """
    result = sps.solve(HEDGE, sources, archive=runs / name)
    assert result.termination_condition == 'optimal', f'{name}: {result.termination_condition}'
    return dict(result.primal('build').select('generator', 'value').iter_rows())


def hedge_main(argv: list[str] | None = None) -> None:
    """Solve every case of the hedge, in parallel, into one directory of archives, then test the average plan.

    ``--replace`` removes the whole directory first. The workers are spawned
    rather than forked: the sources are built here, and a fork of a process
    whose polars pool has run hangs.
    """
    parser = argparse.ArgumentParser(description='plan one period against many futures and archive each plan')
    parser.add_argument('--runs', type=Path, default=Path('hedge'), help='the directory the risk page reads')
    parser.add_argument('--replace', action='store_true', help='remove the directory first')
    parser.add_argument('--jobs', type=int, default=os.cpu_count(), help='solves in flight at once')
    args = parser.parse_args(argv)
    if args.replace and args.runs.exists():
        shutil.rmtree(args.runs)
    cases = hedge_cases()
    with ProcessPoolExecutor(args.jobs, mp_context=multiprocessing.get_context('spawn')) as pool:
        built = dict(zip(cases, pool.map(solve_hedge, cases, cases.values(), [args.runs] * len(cases)), strict=True))
    solve_hedge('average-tested', hedge_sources(futures(), build=built['average']), args.runs)
    print(f'{len(cases) + 1} plans: archived under {args.runs}')  # noqa: T201


if __name__ == '__main__':
    main()
