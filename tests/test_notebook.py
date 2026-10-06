"""The modelling-session notebook runs top to bottom, accepts the model it ships, and solves both stories."""

import importlib.util
from pathlib import Path

NOTEBOOK = Path(__file__).parents[1] / 'notebooks' / 'session.py'


def load_app():
    spec = importlib.util.spec_from_file_location('session', NOTEBOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.app


def test_the_session_runs_and_solves():
    _, defs = load_app().run()
    assert defs['problem'] is None, 'the model as shipped is accepted by the language'
    assert defs['result'].termination_condition == 'optimal'
    assert defs['runs'].record['termination_condition'].unique().to_list() == ['optimal'], (
        'every period of the pathway solved'
    )
