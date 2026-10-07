"""The cases the planner solves: one set of sources per scenario.

A scenario is a function from nothing to the sources the model declares. Every
table that varies by period carries a ``year`` column, which is the axis the
solve job slices on; every other table passes through to each period unchanged.
The numbers are synthetic and chosen to make the periods answer differently.
"""

from __future__ import annotations

import functools
import itertools
import math
import random
from collections.abc import Callable
from dataclasses import dataclass

import polars as pl

YEARS = [2030, 2035, 2040, 2045]
DAYS = ['winter', 'shoulder', 'summer']
HOURS = list(range(24))
GENERATORS = ['solar', 'wind', 'gas']

#: How many real days each typical day stands for; the three sum to a year.
WEIGHT = {'winter': 120.0, 'shoulder': 125.0, 'summer': 120.0}

#: Peak demand in MW on each typical day, before growth.
PEAK = {'winter': 100.0, 'shoulder': 80.0, 'summer': 90.0}

#: Demand relative to the base year; each period is solved against its own.
GROWTH = {2030: 1.0, 2035: 1.2, 2040: 1.4, 2045: 1.6}

#: Annualised build cost per MW. Solar and wind get cheaper; gas does not.
INVEST = {
    2030: {'solar': 42000.0, 'wind': 60000.0, 'gas': 55000.0},
    2035: {'solar': 34000.0, 'wind': 54000.0, 'gas': 55000.0},
    2040: {'solar': 28000.0, 'wind': 50000.0, 'gas': 55000.0},
    2045: {'solar': 24000.0, 'wind': 47000.0, 'gas': 55000.0},
}

#: Gas fuel cost per MWh, rising each period.
FUEL = {2030: 55.0, 2035: 70.0, 2040: 85.0, 2045: 100.0}

#: Tonnes of CO2 per MWh.
RATE = {'solar': 0.0, 'wind': 0.0, 'gas': 0.4}

#: The fleet the pathway starts from: some gas, and nothing else.
EXISTING = {'solar': 0.0, 'wind': 0.0, 'gas': 60.0}


def _load_shape(day: str, hour: int) -> float:
    """Demand as a fraction of the day's peak: a morning shoulder and an evening peak."""
    evening = math.exp(-((hour - 18) ** 2) / 12)
    morning = 0.6 * math.exp(-((hour - 8) ** 2) / 10)
    floor = 0.45 if day == 'winter' else 0.4
    return floor + (1 - floor) * max(evening, morning)


def _solar(day: str, hour: int) -> float:
    """A daylight bell, taller and wider in summer."""
    daylight = {'winter': 8.0, 'shoulder': 11.0, 'summer': 14.0}[day]
    peak = {'winter': 0.35, 'shoulder': 0.6, 'summer': 0.85}[day]
    half = daylight / 2
    if abs(hour - 12.5) >= half:
        return 0.0
    return peak * math.cos(math.pi * (hour - 12.5) / daylight)


def _wind(day: str, hour: int) -> float:
    """Windier in winter and at night, and never quite still."""
    base = {'winter': 0.45, 'shoulder': 0.35, 'summer': 0.25}[day]
    return base + 0.15 * math.cos(2 * math.pi * (hour - 3) / 24)


def sources(
    *,
    growth: dict[int, float] = GROWTH,
    invest: dict[int, dict[str, float]] = INVEST,
    fuel: dict[int, float] = FUEL,
    cap: dict[int, float] | None = None,
) -> dict[str, pl.DataFrame]:
    """The sources for one scenario, each keyword replacing one input.

    ``cap`` is the CO2 cap per year in tonnes; ``None`` leaves the cap far above
    what any fleet here could emit, so the constraint binds nowhere.
    """
    cap = cap or dict.fromkeys(YEARS, 1e12)
    return {
        'day': pl.DataFrame({'day': DAYS}),
        'hour': pl.DataFrame({'hour': HOURS}),
        'generator': pl.DataFrame({'generator': GENERATORS}),
        'weight': pl.DataFrame({'day': DAYS, 'value': [WEIGHT[d] for d in DAYS]}),
        'load': pl.DataFrame(
            [
                {'year': y, 'day': d, 'hour': h, 'value': round(PEAK[d] * growth[y] * _load_shape(d, h), 3)}
                for y in YEARS
                for d in DAYS
                for h in HOURS
            ]
        ),
        'avail': pl.DataFrame(
            [
                {'day': d, 'hour': h, 'generator': g, 'value': round(_avail(g, d, h), 4)}
                for d in DAYS
                for h in HOURS
                for g in GENERATORS
            ]
        ),
        'invest': pl.DataFrame([{'year': y, 'generator': g, 'value': invest[y][g]} for y in YEARS for g in GENERATORS]),
        'cost': pl.DataFrame(
            [{'year': y, 'generator': g, 'value': fuel[y] if g == 'gas' else 0.0} for y in YEARS for g in GENERATORS]
        ),
        'rate': pl.DataFrame({'generator': GENERATORS, 'value': [RATE[g] for g in GENERATORS]}),
        'cap': pl.DataFrame({'year': YEARS, 'value': [cap[y] for y in YEARS]}),
        'existing': pl.DataFrame({'generator': GENERATORS, 'value': [EXISTING[g] for g in GENERATORS]}),
    }


def _avail(generator: str, day: str, hour: int) -> float:
    if generator == 'solar':
        return _solar(day, hour)
    if generator == 'wind':
        return _wind(day, hour)
    return 1.0


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    sources: Callable[[], dict[str, pl.DataFrame]]


def _cheap_solar() -> dict[str, pl.DataFrame]:
    invest = {y: {**INVEST[y], 'solar': INVEST[y]['solar'] * 0.6} for y in YEARS}
    return sources(invest=invest)


def _high_demand() -> dict[str, pl.DataFrame]:
    return sources(growth={2030: 1.0, 2035: 1.35, 2040: 1.7, 2045: 2.1})


def _carbon_cap() -> dict[str, pl.DataFrame]:
    return sources(cap={2030: 120_000.0, 2035: 80_000.0, 2040: 40_000.0, 2045: 10_000.0})


SCENARIOS: dict[str, Scenario] = {
    s.name: s
    for s in [
        Scenario('base', 'the reference assumptions', sources),
        Scenario('cheap_solar', 'solar builds at 60% of the reference cost', _cheap_solar),
        Scenario('high_demand', 'demand grows twice as fast', _high_demand),
        Scenario('carbon_cap', 'a CO2 cap that tightens every period', _carbon_cap),
    ]
}


#: The what-if grid: a CO2 cap on the last period, in tonnes, and a multiplier on
#: solar's build cost in every period. ``None`` is no cap. Every point is one
#: pathway, archived like a scenario, so a static page can answer two sliders
#: from the archives rather than from a solver.
GRID_CAPS = [None, 20_000.0, 17_500.0, 15_000.0, 12_500.0, 10_000.0, 7_500.0, 5_000.0, 2_500.0, 0.0]
GRID_SOLAR = [0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4]


def _point(cap: float | None, solar: float) -> dict[str, pl.DataFrame]:
    invest = {y: {**INVEST[y], 'solar': INVEST[y]['solar'] * solar} for y in YEARS}
    return sources(invest=invest, cap=None if cap is None else {**dict.fromkeys(YEARS, 1e12), YEARS[-1]: cap})


def grid() -> dict[str, Scenario]:
    """One scenario per point of the grid, named for its two inputs.

    The name is only a directory name: a reader takes the cap and the solar
    cost from the archived sources, where the solve read them.
    """
    points = {}
    for cap, solar in itertools.product(GRID_CAPS, GRID_SOLAR):
        name = f'cap-{"none" if cap is None else int(cap)}_solar-{round(solar * 100):03d}'
        described = f'{"no cap" if cap is None else f"{cap:,.0f} t of CO2"} in {YEARS[-1]}, solar at {solar:.0%}'
        points[name] = Scenario(name, described, functools.partial(_point, cap, solar))
    return points


#: The hedge: the pathway's 2035, planned once against many futures rather than
#: once per scenario. The fleet is built before the future is known and run in
#: each of them, so what is built is a hedge across all of them at once.
HEDGE_YEAR = 2035
HEDGE_GENERATORS = [*GENERATORS, 'peaker']

#: How many futures the plan weighs, each equally likely, and the seed they are drawn from.
FUTURES = 60
SEED = 2035

#: A peaker is cheap to build and dear to run: insurance against the futures that need it.
PEAKER = {'invest': 22000.0, 'fuel': 1.6, 'rate': 0.6}

#: What a MWh of demand left unserved costs.
VOLL = 3000.0

#: Where the tail begins: the worst tenth of the futures.
ALPHA = 0.9

#: How much of the operating cost is priced in the tail. One is left out: a plan
#: that prices nothing but the tail is indifferent to how the other futures run.
OMEGAS = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]


@dataclass(frozen=True)
class Future:
    """What one future draws: how much demand grew, what gas costs, and how the weather ran."""

    name: str
    growth: float
    gas: float
    wind: float
    solar: float
    lull: bool


def futures(n: int = FUTURES, seed: int = SEED) -> list[Future]:
    """Draw ``n`` futures, the same ones for the same seed.

    Demand and the gas price are lognormal, so a few futures run far above the
    rest. One winter in ten is a lull, when the wind drops to a quarter of its
    usual output for the whole typical day.
    """
    rng = random.Random(seed)
    drawn = []
    for i in range(n):
        drawn.append(
            Future(
                name=f'f{i:02d}',
                growth=round(GROWTH[HEDGE_YEAR] * rng.lognormvariate(0, 0.08), 4),
                gas=round(FUEL[HEDGE_YEAR] * rng.lognormvariate(0, 0.35), 2),
                wind=round(min(max(rng.gauss(1, 0.15), 0.5), 1.4), 4),
                solar=round(min(max(rng.gauss(1, 0.08), 0.7), 1.2), 4),
                lull=rng.random() < 0.1,
            )
        )
    return drawn


def _future_avail(future: Future, generator: str, day: str, hour: int) -> float:
    base = _avail('gas' if generator == 'peaker' else generator, day, hour)
    if generator == 'wind':
        return min(base * future.wind * (0.25 if future.lull and day == 'winter' else 1.0), 1.0)
    if generator == 'solar':
        return min(base * future.solar, 1.0)
    return base


def _fuel(future: Future, generator: str) -> float:
    return {'gas': future.gas, 'peaker': future.gas * PEAKER['fuel']}.get(generator, 0.0)


def hedge_sources(
    drawn: list[Future], *, omega: float = 0.0, build: dict[str, float] | None = None
) -> dict[str, pl.DataFrame]:
    """The sources of the hedge over the drawn futures, each equally likely.

    ``build`` pins what is built, generator by generator, so the plan is run
    rather than chosen; ``None`` leaves each between nothing and 1000 MW.
    """
    invest = {**INVEST[HEDGE_YEAR], 'peaker': PEAKER['invest']}
    rate = {**RATE, 'peaker': PEAKER['rate']}
    existing = {**EXISTING, 'peaker': 0.0}
    names = [f.name for f in drawn]
    return {
        'future': pl.DataFrame({'future': names}),
        'day': pl.DataFrame({'day': DAYS}),
        'hour': pl.DataFrame({'hour': HOURS}),
        'generator': pl.DataFrame({'generator': HEDGE_GENERATORS}),
        'probability': pl.DataFrame({'future': names, 'value': [1 / len(drawn)] * len(drawn)}),
        'weight': pl.DataFrame({'day': DAYS, 'value': [WEIGHT[d] for d in DAYS]}),
        'load': pl.DataFrame(
            [
                {'future': f.name, 'day': d, 'hour': h, 'value': round(PEAK[d] * f.growth * _load_shape(d, h), 3)}
                for f in drawn
                for d in DAYS
                for h in HOURS
            ]
        ),
        'avail': pl.DataFrame(
            [
                {'future': f.name, 'day': d, 'hour': h, 'generator': g, 'value': round(_future_avail(f, g, d, h), 4)}
                for f in drawn
                for d in DAYS
                for h in HOURS
                for g in HEDGE_GENERATORS
            ]
        ),
        'invest': pl.DataFrame({'generator': HEDGE_GENERATORS, 'value': [invest[g] for g in HEDGE_GENERATORS]}),
        'cost': pl.DataFrame(
            [{'future': f.name, 'generator': g, 'value': _fuel(f, g)} for f in drawn for g in HEDGE_GENERATORS]
        ),
        'rate': pl.DataFrame({'generator': HEDGE_GENERATORS, 'value': [rate[g] for g in HEDGE_GENERATORS]}),
        'voll': pl.DataFrame({'value': [VOLL]}),
        'existing': pl.DataFrame({'generator': HEDGE_GENERATORS, 'value': [existing[g] for g in HEDGE_GENERATORS]}),
        'build_min': pl.DataFrame(
            {'generator': HEDGE_GENERATORS, 'value': [(build or {}).get(g, 0.0) for g in HEDGE_GENERATORS]}
        ),
        'build_max': pl.DataFrame(
            {'generator': HEDGE_GENERATORS, 'value': [(build or {}).get(g, 1000.0) for g in HEDGE_GENERATORS]}
        ),
        'alpha': pl.DataFrame({'value': [ALPHA]}),
        'omega': pl.DataFrame({'value': [omega]}),
    }


def alone(sources: dict[str, pl.DataFrame], future: str) -> dict[str, pl.DataFrame]:
    """The hedge's sources narrowed to one future, which is then certain.

    What a planner with perfect foresight solves: the fleet is chosen knowing
    which future arrives.
    """
    narrowed = {k: v.filter(pl.col('future') == future) if 'future' in v.columns else v for k, v in sources.items()}
    return {**narrowed, 'probability': narrowed['probability'].with_columns(value=pl.lit(1.0))}


def expected(sources: dict[str, pl.DataFrame]) -> dict[str, pl.DataFrame]:
    """The hedge's sources with every input that varies by future replaced by its expectation, as one certain future.

    What a planner who plans against the average solves. The future is named ``average``.
    """
    probability = sources['probability'].rename({'value': 'probability'})
    averaged = {}
    for name, table in sources.items():
        if name in {'future', 'probability'} or 'future' not in table.columns:
            continue
        keys = [c for c in table.columns if c not in {'future', 'value'}]
        averaged[name] = (
            table.join(probability, on='future')
            .group_by(keys, maintain_order=True)
            .agg((pl.col('value') * pl.col('probability')).sum())
            .select(pl.lit('average').alias('future'), *keys, 'value')
        )
    return {
        **sources,
        **averaged,
        'future': pl.DataFrame({'future': ['average']}),
        'probability': pl.DataFrame({'future': ['average'], 'value': [1.0]}),
    }
