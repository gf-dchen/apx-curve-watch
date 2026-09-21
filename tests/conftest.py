"""Test-wide guard: nothing in the suite may reach APX.

A test that forgets to patch the fetch layer would otherwise issue a real,
credentialed prod call and quietly assert against whatever the live book says
-- which happened once while wiring the day-ahead review in. Patching the token
call makes that fail loudly at the seam instead.
"""

import pytest
from gfem.foundry.bidding import apx_client


@pytest.fixture(autouse=True)
def _no_live_apx(monkeypatch):
    def _refuse(*args, **kwargs):
        raise AssertionError("test reached live APX -- patch the fetch instead")

    monkeypatch.setattr(apx_client, "get_token", _refuse)
