# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "marimo",
# ]
# ///

# A modelling session on specsolve, as a marimo notebook.
#
#   uv run marimo edit notebooks/session.py      # live: edit the YAML, the data, the sliders
#   uv run python notebooks/session.py           # top to bottom, as a script
#   uv run marimo export html notebooks/session.py -o session.html
#   uv run marimo export html-wasm notebooks/session.py -o app --mode run   # runs in the browser
#
# The model is a document. Edit it in the cell below and the typeset math, the
# validation and the solve all follow, because every cell that reads it re-runs.

import marimo

__generated_with = '0.24.2'
app = marimo.App(width='medium', app_title='A modelling session on specsolve')


@app.cell(hide_code=True)
async def _():
    import sys

    pathway_text = None
    notice = None
    if sys.platform == 'emscripten':
        # In the browser: specsolve, mathspec and this repository's wheel sit beside this page, at the versions locked.
        import json

        import marimo as _mo
        import micropip
        from pyodide.http import pyfetch

        # Pyodide runs in a worker, so a relative URL would resolve against the worker's script: build them off the page.
        here = _mo.notebook_location()
        manifest = json.loads(await (await pyfetch(str(here / 'wheels' / 'manifest.json'))).string())
        await micropip.install(['polars', 'highspy', 'numpy', 'pydantic', 'pyparsing', 'pyyaml', 'altair'])
        await micropip.install([str(here / 'wheels' / name) for name in manifest], deps=False)
        pathway_text = await (await pyfetch(str(here / 'models' / 'pathway.yaml'))).string()
        notice = _mo.callout(
            _mo.md(
                '**This notebook is running in your browser**, Python and solver included, and holds about 1 GB of '
                'memory in this tab after a solve. A desktop browser is fine with that; a phone browser is not, and '
                'will reload the page. Nothing you do here leaves your machine.'
            ),
            kind='warn',
        )
    ready = True
    notice
    return pathway_text, ready


@app.cell(hide_code=True)
def _(ready):
    assert ready
    import re

    import altair as alt
    import marimo as mo
    import mathspec as ms
    import polars as pl
    import specsolve as sps

    return alt, mo, ms, pl, re, sps


@app.cell(hide_code=True)
def _(alt):
    # The site's palette (site/src/components/palette.js): one hue per technology, fixed whatever else is on screen.
    hues = {'gas': '#2a78d6', 'biomass': '#eb6834', 'wind': '#1baf7a', 'solar': '#eda100'}
    by_technology = alt.Color(
        'generator:N', scale=alt.Scale(domain=list(hues), range=list(hues.values())), title='technology'
    )
    return (by_technology,)


@app.cell(hide_code=True)
def _(mo):
    mo.callout(
        mo.md(
            'An example of what you build on [specsolve](https://github.com/fluxopt/specsolve): a modelling session where the '
            'model is a document, the data is a table, and every answer is a table too. specsolve runs unchanged, here in '
            'your browser or on a machine of your own. '
            '[The source](https://github.com/fluxopt/specsolve-showcase/blob/main/notebooks/session.py) is one file.'
        ),
        kind='info',
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # A modelling session on specsolve

        In specsolve the model is a document: a YAML file that says what the variables,
        constraints and objective *are*. Nothing below is a builder. Edit the file in
        the cell that holds it and every cell that reads it re-runs: the math is
        typeset again, the file is checked again, and the solve runs again on the
        data you have given it.

        Three things to try, in order:

        1. In the model, add a cap on emissions under `constraints:` —
           `carbon: {dims: [], expression: emissions <= 40}` — and watch the math,
           the dispatch and the prices change: biomass, dearer than gas but clean, comes
           on. The named expression `emissions` is already declared, so no new data
           is needed.
        2. Break something on purpose, such as `sum(p, over=snapshto)`, and read the
           error: it names what is wrong and what to write instead.
        3. Edit the cost of gas in the data table, then move the sliders under the
           pathway further down.
        """
    )
    return


@app.cell(hide_code=True)
def _(mo):
    model = mo.ui.code_editor(
        value="""description: "least-cost dispatch: four generators meet a load over one day"
version: 0

dimensions:
  snapshot: {dtype: int, description: hours of the day}
  generator: {dtype: str, description: generating units}

parameters:
  p_max: {dims: [generator], description: "capacity, in MW"}
  cost: {dims: [generator], description: variable cost per MWh}
  rate: {dims: [generator], description: tonnes of CO2 per MWh}
  avail: {dims: [snapshot, generator], description: "capacity factor, between 0 and 1"}
  load: {dims: [snapshot], description: "demand, in MW"}

variables:
  p: {dims: [snapshot, generator], bounds: {lower: 0}, description: output}

expressions:
  emissions: sum(rate * p)

constraints:
  capacity:
    dims: [snapshot, generator]
    expression: p <= p_max * avail
  balance:
    dims: [snapshot]
    expression: sum(p, over=generator) == load

objective:
  sense: minimize
  expression: sum(cost * p)
""",
        language='yaml',
        min_height=520,
        label='The model. Edit it.',
    )
    model
    return (model,)


@app.cell(hide_code=True)
def _(mo, model, ms, sps):
    try:
        spec = ms.to_spec(model.value)
        sps.check(model.value)
        problem = None
    except Exception as error:  # a LanguageError names the rewrite; show it where the author is looking
        spec = None
        problem = mo.callout(mo.md(f'**The file is refused.**\n\n```\n{error}\n```'), kind='danger')
    problem
    return problem, spec


@app.cell(hide_code=True)
def _(mo, ms, re, spec):
    def typeset(spec):
        """mathspec prints GitHub's math delimiters; marimo's Markdown reads TeX's."""
        text = ms.to_markdown(spec, legend=False)
        text = re.sub(r'```math\n(.*?)\n```', lambda m: f'$$\n{m.group(1)}\n$$', text, flags=re.S)
        return re.sub(r'\$`(.+?)`\$', lambda m: f'${m.group(1)}$', text)

    mo.md(
        '## The same file, as math\n\nPrinted by the language, from the file alone: no data binds and nothing is solved.\n\n'
        + (typeset(spec) if spec is not None else '*Fix the file above first.*')
    )
    return


@app.cell
def _(mo, pl):
    generators = ['wind', 'solar', 'gas', 'biomass']
    cost = mo.ui.data_editor(
        pl.DataFrame({'generator': generators, 'value': [10.0, 5.0, 60.0, 90.0]}),
        editable_columns=['value'],
        label='cost — variable cost per MWh. Edit a number.',
    )
    load_scale = mo.ui.slider(0.5, 2.0, step=0.1, value=1.0, label='load, relative to the day below')
    mo.vstack([cost, load_scale])
    return cost, generators, load_scale


@app.cell
def _(cost, generators, load_scale, pl):
    import math

    hours = list(range(24))
    shape = [0.55 + 0.45 * max(math.exp(-((h - 18) ** 2) / 12), 0.6 * math.exp(-((h - 8) ** 2) / 10)) for h in hours]
    solar = [max(0.0, math.cos(math.pi * (h - 12.5) / 12)) * 0.8 if abs(h - 12.5) < 6 else 0.0 for h in hours]
    sources = {
        'snapshot': hours,
        'generator': generators,
        'p_max': pl.DataFrame({'generator': generators, 'value': [60.0, 50.0, 120.0, 40.0]}),
        'cost': pl.DataFrame(cost.value),
        'rate': pl.DataFrame({'generator': generators, 'value': [0.0, 0.0, 0.4, 0.0]}),
        'load': pl.DataFrame({'snapshot': hours, 'value': [round(100 * s * load_scale.value, 2) for s in shape]}),
        'avail': pl.DataFrame(
            [
                {'snapshot': h, 'generator': g, 'value': (solar[h] if g == 'solar' else 1.0)}
                for h in hours
                for g in generators
            ]
        ),
    }
    return (sources,)


@app.cell
def _(mo, model, sources, spec, sps):
    result = (
        sps.solve(model.value, {k: v for k, v in sources.items() if k in {*spec.parameters, *spec.dimensions}})
        if spec
        else None
    )
    mo.md(
        f'## Solved\n\n**{result.termination_condition}**, objective **{result.objective:,.0f}**, '
        f'emissions **{result.evaluate("emissions")["value"][0]:,.0f} t**.'
        if result is not None and result.has_primal
        else f'## Solved\n\n*{result.termination_condition if result is not None else "Nothing to solve yet"}: no values to read.*'
    )
    return (result,)


@app.cell
def _(alt, by_technology, mo, result):
    if result is not None and result.has_primal:
        output = result.primal('p')
        price = result.dual('balance')
        dispatch = (
            alt.Chart(output)
            .mark_area()
            .encode(x=alt.X('snapshot:Q', title='hour'), y=alt.Y('value:Q', title='MW'), color=by_technology)
            .properties(width=380, height=220, title='Output by hour')
        )
        prices = (
            alt.Chart(price)
            .mark_line(interpolate='step-after', point=True)
            .encode(x=alt.X('snapshot:Q', title='hour'), y=alt.Y('value:Q', title='per MW'))
            .properties(width=380, height=220, title='Price of one more MW of load (the dual of balance)')
        )
        charts = mo.hstack([dispatch, prices])
    else:
        charts = mo.md('')
    charts
    return


@app.cell(hide_code=True)
def _(mo, result):
    mo.md(
        "Every answer is a tidy table keyed by the model's own labels, so it goes straight into a chart, a join or a file:\n\n"
        "```python\nresult.primal('p')          # (snapshot, generator, value)\nresult.dual('balance')      # (snapshot, value)\n"
        "result.evaluate('emissions')  # a named expression at the solution\n```"
    )
    (mo.ui.table(result.primal('p'), page_size=8) if result is not None and result.has_primal else None)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        ## A pathway: the same idea, one period at a time

        `models/pathway.yaml` is one investment period. `solve_over` runs it once per
        year and hands each year's standing capacity to the next as its `existing`
        fleet, which is the `carry=`. The two sliders change the data; the model
        does not change.
        """
    )
    return


@app.cell
def _(mo):
    cap_2045 = mo.ui.slider(5_000, 60_000, step=5_000, value=10_000, label='CO2 cap in 2045, tonnes')
    solar_factor = mo.ui.slider(0.4, 1.4, step=0.1, value=1.0, label='solar build cost, relative to the reference')
    mo.vstack([cap_2045, solar_factor])
    return cap_2045, solar_factor


@app.cell
def _(cap_2045, pathway_text, solar_factor, sps):
    from showcase.scenarios import INVEST, YEARS
    from showcase.scenarios import sources as pathway_sources
    from showcase.solve import MODEL

    pathway = pathway_text or MODEL.read_text()
    invest = {y: {**INVEST[y], 'solar': INVEST[y]['solar'] * solar_factor.value} for y in YEARS}
    cap = {y: (cap_2045.value if y == YEARS[-1] else 1e12) for y in YEARS}
    runs = sps.solve_over(
        pathway, pathway_sources(invest=invest, cap=cap), sps.EachCoordinate('year'), carry={'existing': 'total'}
    )
    return (runs,)


@app.cell
def _(alt, by_technology, mo, runs):
    fleet = (
        alt.Chart(runs.primal('total'))
        .mark_bar()
        .encode(x=alt.X('year:O', title='period'), y=alt.Y('value:Q', title='MW standing'), color=by_technology)
        .properties(width=380, height=220, title='Standing capacity after each period')
    )
    emitted = (
        alt.Chart(runs.evaluate('emissions'))
        .mark_line(point=True)
        .encode(x=alt.X('year:O', title='period'), y=alt.Y('value:Q', title='tonnes'))
        .properties(width=380, height=220, title='Emissions per period')
    )
    mo.vstack(
        [mo.hstack([fleet, emitted]), mo.ui.table(runs.record.select('year', 'termination_condition', 'objective'))]
    )
    return


if __name__ == '__main__':
    app.run()
