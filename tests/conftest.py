import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import dify_plugin  # noqa: E402,F401  (gevent patches the socket module here, before the fake server starts)

from tests import fake_api  # noqa: E402

_server, _url = fake_api.start()
os.environ["FAXFORAGENTS_API_URL"] = _url


@pytest.fixture(autouse=True)
def _reset_calls():
    fake_api.Handler.calls.clear()
    yield


@pytest.fixture
def calls():
    return fake_api.Handler.calls
