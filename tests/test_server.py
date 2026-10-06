"""The server is a second producer over the same contract, and that is what these assert.

Nothing here checks HTTP for its own sake. The claims are that a solve asked
for over HTTP lands as the archive `showcase-solve` would have written, that
every existing reader sees it with no change, and that the registry survives
the process because it was never in the process to begin with.
"""

import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server import jobs
from server.app import create_app
from showcase import warehouse
from showcase.scenarios import SCENARIOS


def wait_for(client: TestClient, scenario: str, state: str, seconds: float = 120.0) -> dict:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        run = client.get(f'/runs/{scenario}').json()
        if run['state'] == state:
            return run
        assert run['state'] != 'failed', f'{scenario} failed: {run.get("error")}'
        time.sleep(0.2)
        continue
    raise AssertionError(f'{scenario} never reached {state}; last was {run}')


@pytest.fixture
def served(tmp_path: Path) -> TestClient:
    return TestClient(create_app(tmp_path))


def test_an_empty_directory_describes_every_scenario_as_absent(served: TestClient):
    runs = served.get('/runs').json()
    assert sorted(runs) == sorted(SCENARIOS), 'the registry lists the scenarios, not the directories'
    assert {run['state'] for run in runs.values()} == {'absent'}, 'nothing is archived yet'


def test_a_solve_asked_for_over_http_is_the_archive_every_reader_already_reads(served: TestClient, tmp_path: Path):
    """The whole point: a second producer, and no consumer learns that it exists."""
    accepted = served.post('/runs/base')
    assert accepted.status_code == 202
    assert accepted.json()['state'] == 'queued'

    run = wait_for(served, 'base', 'archived')
    assert run['periods'] == 4, 'the pathway is four investment periods'
    assert run['optimal'] is True

    records = warehouse.records(tmp_path)
    assert records['run'].unique().to_list() == ['base'], "the site's own client reads it, unchanged"
    assert run['objective'] == pytest.approx(records['objective'].sum())
    catalogue = warehouse.catalogue(tmp_path)
    assert 'total' in catalogue['name'].to_list(), 'and finds the quantities the dashboard plots'


def test_the_registry_outlives_the_process_that_wrote_it(served: TestClient, tmp_path: Path):
    """No database: a second app over the same directory reports what the first one produced."""
    served.post('/runs/base')
    wait_for(served, 'base', 'archived')

    fresh = TestClient(create_app(tmp_path))
    assert fresh.get('/runs/base').json()['state'] == 'archived', 'the archive is the registry'
    assert fresh.get('/runs/carbon_cap').json()['state'] == 'absent'


def test_a_scenario_already_in_flight_is_refused_rather_than_queued_twice(
    served: TestClient, monkeypatch: pytest.MonkeyPatch
):
    """The first solve is held until the second request is answered, so the refusal does not race the solver."""
    release = threading.Event()
    solve = jobs.solve

    def held(*args, **kwargs):
        assert release.wait(60), 'the test never released the solve'
        return solve(*args, **kwargs)

    monkeypatch.setattr(jobs, 'solve', held)
    assert served.post('/runs/base').status_code == 202
    second = served.post('/runs/base')
    release.set()
    assert second.status_code == 409
    assert 'already in flight' in second.json()['detail']
    wait_for(served, 'base', 'archived')


def test_a_scenario_the_model_does_not_have_names_the_ones_it_does(served: TestClient):
    for request in (served.get('/runs/nope'), served.post('/runs/nope')):
        assert request.status_code == 404
        assert 'carbon_cap' in request.json()['detail'], 'the message lists the valid scenarios'


def test_the_server_writes_nothing_beside_the_archive(served: TestClient, tmp_path: Path):
    served.post('/runs/base')
    wait_for(served, 'base', 'archived')
    assert sorted(p.name for p in tmp_path.iterdir()) == ['base'], 'no database, no journal, no lock file'
