"""The hedge: one period planned against many futures, and the plans it is measured against."""

from pathlib import Path

import polars as pl
import pytest

from showcase.scenarios import FUTURES, OMEGAS, VOLL, alone, expected, futures, hedge_sources
from showcase.solve import hedge_cases, solve_hedge

#: The risk-neutral and the most risk-averse plan, two plans with foresight, and the average plan.
SOLVED = ['risk-000', 'risk-090', 'perfect-f00', 'perfect-f01', 'average']


@pytest.fixture(scope='module')
def hedge(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A few cases of the hedge, solved as ``showcase-hedge`` solves them, with the average plan tested after."""
    directory = tmp_path_factory.mktemp('hedge')
    cases = hedge_cases()
    built = {name: solve_hedge(name, cases[name], directory) for name in SOLVED}
    solve_hedge('average-tested', hedge_sources(futures(), build=built['average']), directory)
    return directory


def read(hedge: Path, run: str, path: str) -> pl.DataFrame:
    return pl.read_parquet(hedge / run / f'{path}.parquet').drop('specsolve_run', strict=False)


def objective(hedge: Path, run: str) -> float:
    return read(hedge, run, 'answer/record')['objective'][0]


def test_every_case_supplies_the_same_names():
    cases = hedge_cases()
    assert len(cases) == len(OMEGAS) + FUTURES + 1, 'one plan per weight on the tail, one per future, and the average'
    names = set(hedge_sources(futures()))
    for name, sources in cases.items():
        assert set(sources) == names, f'{name} supplies exactly the names the model declares'


def test_the_futures_are_drawn_the_same_every_time():
    assert futures() == futures()
    probability = hedge_sources(futures())['probability']['value']
    assert probability.sum() == pytest.approx(1.0), 'the futures are equally likely and nothing else'


def test_the_average_future_is_the_expectation_of_every_input():
    sources = hedge_sources(futures())
    average = expected(sources)
    assert average['future']['future'].to_list() == ['average']
    mean = sources['load'].group_by('day', 'hour').agg(pl.col('value').mean())
    joined = average['load'].join(mean, on=['day', 'hour'], suffix='_mean')
    assert (joined['value'] - joined['value_mean']).abs().max() < 1e-9, 'each hour of load is the mean over futures'


def test_a_future_alone_is_certain():
    alone_ = alone(hedge_sources(futures()), 'f03')
    assert alone_['probability'].select('future', 'value').rows() == [('f03', 1.0)]
    assert alone_['load']['future'].unique().to_list() == ['f03']


def test_every_plan_solved_and_the_tested_plan_built_what_the_average_plan_built(hedge: Path):
    for run in [*SOLVED, 'average-tested']:
        assert read(hedge, run, 'answer/record')['termination_condition'][0] == 'optimal', run
    average = read(hedge, 'average', 'answer/primal/build').sort('generator')
    tested = read(hedge, 'average-tested', 'answer/primal/build').sort('generator')
    assert (average['value'] - tested['value']).abs().max() < 1e-6, 'the tested plan builds nothing of its own'


def test_planning_against_every_future_beats_planning_against_the_average(hedge: Path):
    """The value of the stochastic solution: the average plan, run in every future, costs more than the hedge."""
    assert objective(hedge, 'average-tested') > objective(hedge, 'risk-000')
    shed = read(hedge, 'average-tested', 'answer/expression/unserved')
    assert (shed['value'] > 0).sum() > FUTURES // 4, 'the average plan leaves demand unserved in many futures'


def test_aversion_to_the_tail_lowers_the_tail(hedge: Path):
    """The page computes the tail from each future's operating cost, so it holds at a weight of zero too."""

    def tail(run: str) -> float:
        opex = read(hedge, run, 'answer/expression/opex')['value'].sort(descending=True)
        return opex.head(FUTURES // 10).mean()

    assert tail('risk-090') < tail('risk-000')


@pytest.mark.parametrize('run', ['risk-000', 'risk-090'])
def test_the_tail_duals_reweight_the_futures(hedge: Path, run: str):
    """The page reads each future's risk-adjusted probability as ``(1 - omega) * probability + dual``."""
    omega = read(hedge, run, 'sources/omega')['value'][0]
    dual = read(hedge, run, 'answer/dual/tail_excess')
    assert dual['value'].min() >= -1e-9, 'the dual of a lower bound on the excess is not negative'
    assert dual['value'].sum() == pytest.approx(omega, abs=1e-6), 'the tail duals sum to the weight on the tail'


def test_a_shed_hour_is_priced_at_the_value_of_lost_load(hedge: Path):
    """The page divides the balance dual by the day's weight and the future's risk-adjusted probability."""
    run = 'average-tested'
    probability = read(hedge, run, 'sources/probability').rename({'value': 'probability'})
    weight = read(hedge, run, 'sources/weight').rename({'value': 'weight'})
    shed = read(hedge, run, 'answer/primal/shed').rename({'value': 'shed'})
    price = (
        read(hedge, run, 'answer/dual/balance')
        .join(weight, on='day')
        .join(probability, on='future')
        .join(shed, on=['future', 'day', 'hour'])
        .with_columns(price=pl.col('value') / (pl.col('weight') * pl.col('probability')))
    )
    assert price['price'].max() == pytest.approx(VOLL), 'no hour is priced above the value of lost load'
    shed_hours = price.filter(pl.col('shed') > 1e-6)['price']
    assert shed_hours.len() > 0
    assert (shed_hours - VOLL).abs().max() < 1e-6, 'every hour that sheds demand is priced at the value of lost load'
