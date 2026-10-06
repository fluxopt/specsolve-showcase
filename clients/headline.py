"""The four headline numbers off an archive, in polars, with no specsolve and no client library.

    uv run python clients/headline.py runs/base

The archive is a table per glob, so reading it needs nothing this repository
ships. `headline.sql` answers the same four questions in DuckDB, and
`tests/test_clients.py` holds the two to each other.
"""

import sys
from pathlib import Path

import polars as pl


def headline(run: Path) -> dict[str, float]:
    frames = lambda name: pl.read_parquet(run / 'answer' / f'{name}.parquet')
    at = lambda frame, year: frame.filter(pl.col('year') == year)['value'].sum()

    objective = pl.read_parquet(run / 'answer/record.parquet')
    first, last = objective['slice'].cast(pl.Int64).min(), objective['slice'].cast(pl.Int64).max()
    emissions, fleet = frames('expression/emissions'), at(frames('primal/total'), last)
    clean = pl.read_parquet(run / 'sources/rate.parquet').filter(pl.col('value') == 0)['generator'].to_list()

    return {
        'pathway_cost': objective['objective'].sum(),
        'emissions_cut': 1 - at(emissions, last) / at(emissions, first),
        'zero_carbon_share': frames('primal/total')
        .filter(pl.col('year') == last, pl.col('generator').is_in(clean))['value']
        .sum()
        / fleet,
        'carbon_price': -at(frames('dual/carbon'), last) + 0.0,
    }


if __name__ == '__main__':
    for name, value in headline(Path(sys.argv[1] if len(sys.argv) > 1 else 'runs/base')).items():
        print(f'{name:<18} {value:>15,.4f}')
