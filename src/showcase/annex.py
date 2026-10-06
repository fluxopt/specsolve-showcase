"""The model as solved: every declaration typeset, with what the archive says it cost.

The other two views are each half of this one. The model page prints the spec
with no data bound; the dashboard prints the answer with no math beside it.
An annex is what a reader outside this repository asks for — a regulator, a
reviewer, a client — and it is the two joined: the equation, in the notation
the symbols file declares, and under it what the solver made of that equation.

Nothing here imports specsolve. The equations come from mathspec, which has no
solver in it, and the numbers come from the parquet the solve job archived.
The join is by declaration name, which is the one key both sides share.

The stitching below is the whole reason ``fluxopt/specsolve#1648`` is open: the
typesetter renders a model and the result frames carry the answer, and holding
one against the other is left to every caller that wants this page.
"""

from __future__ import annotations

from pathlib import Path

import mathspec
import polars as pl

from showcase import warehouse

#: Below this a dual is read as zero, so the row costs nothing at the margin.
PRICED = 1e-9

KINDS = {
    'dual': ('Constraints', 'what the row costs at the optimum'),
    'expression': ('Named expressions', 'the quantity the model gives a name'),
    'primal': ('Variables', 'what the solver was free to choose'),
}


def _summary(kind: str, frame: pl.DataFrame) -> str:
    """A markdown table of what the archive says about one declaration.

    A constraint is one equation and many rows, so what is printed is the shape
    of the whole block rather than a row of it.

    *Priced* counts the rows whose dual is non-zero, which is not the same as
    the rows that bind: an equality binds everywhere by construction, and its
    dual is still zero wherever moving the right-hand side would not move the
    objective. On the reference run 86 of `balance`'s 288 rows are priced, and
    that spread by hour is the thing worth reading.
    """
    values = frame['value']
    if kind == 'dual':
        priced = frame.filter(pl.col('value').abs() > PRICED)
        largest = priced['value'].abs().max() if len(priced) else 0.0
        return (
            '| rows | priced | largest shadow price |\n|---:|---:|---:|\n'
            f'| {len(frame):,} | {len(priced):,} | {largest:,.2f} |\n'
        )
    if kind == 'expression' and 'year' in frame.columns:
        periods = frame.group_by('year').agg(pl.col('value').sum()).sort('year')
        head = '| ' + ' | '.join(str(y) for y in periods['year']) + ' |'
        rule = '|' + '---:|' * len(periods)
        body = '| ' + ' | '.join(f'{v:,.1f}' for v in periods['value']) + ' |'
        return f'{head}\n{rule}\n{body}\n'
    return (
        '| rows | total | non-zero |\n|---:|---:|---:|\n'
        f'| {len(frame):,} | {values.sum():,.1f} | {len(frame.filter(pl.col("value").abs() > PRICED)):,} |\n'
    )


def annex(runs: Path, run: str, symbols: Path) -> str:
    """The annex for one archived run, as markdown with ``tex`` fences.

    Args:
        runs: The directory of archives.
        run: Which archive in it — the scenario the solve job named.
        symbols: The notation the equations are printed in. A symbol that names
            nothing in the model fails, the way the model page fails.

    Returns:
        Markdown: a period table, then one section per kind, then one
        subsection per declaration with its equation and its numbers.
    """
    model = runs / run / 'spec.yaml'
    records = warehouse.records(runs).filter(pl.col('run') == run).sort('year')
    catalogue = warehouse.catalogue(runs)

    periods = '| period | ' + ' | '.join(str(y) for y in records['year']) + ' | total |\n'
    periods += '|---' * (len(records) + 2) + '|\n'
    periods += '| objective | ' + ' | '.join(f'{v:,.0f}' for v in records['objective'])
    periods += f' | **{records["objective"].sum():,.0f}** |\n'

    out = [f'{periods}\nEvery period solved to `{records["termination_condition"].unique().to_list()[0]}`.\n']
    for kind, (heading, gloss) in KINDS.items():
        rows = catalogue.filter(pl.col('kind') == kind).sort('name')
        if not len(rows):
            continue
        out.append(f'## {heading}\n\n{gloss[0].upper() + gloss[1:]}.\n')
        for entry in rows.iter_rows(named=True):
            line = mathspec.typeset_declaration(model, entry['name'], 'markdown', symbols=symbols)
            frame = warehouse.frame(runs, kind, entry['name']).filter(pl.col('run') == run)
            keyed = ', '.join(f'`{d}`' for d in entry['dims']) or 'nothing'
            out.append(f'### {entry["name"]}\n\nKeyed by {keyed}.\n\n```tex\n{line}\n```\n\n{_summary(kind, frame)}')
    return '\n'.join(out)


def main(argv: list[str] | None = None) -> None:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description='print one archived run as an annex: the math, with what it cost')
    parser.add_argument('run', help='which archive in the directory')
    parser.add_argument('--runs', type=Path, default=Path('runs'), help='the directory of archives')
    parser.add_argument(
        '--symbols',
        type=Path,
        default=Path(__file__).parents[2] / 'models' / 'pathway.symbols.yaml',
        help='the notation to print in',
    )
    args = parser.parse_args(argv)
    sys.stdout.write(annex(args.runs, args.run, args.symbols))
