"""Guards the `akamai pm ...` shell-out call sites against reintroducing
`shell=True` with an interpolated string (CWE-78 command-injection shape).
`bin/utility.py` and `bin/wrapper_api.py` build the command on directly
callable methods, so those are covered by mocking `subprocess.run` and
asserting the call shape. `bin/akamai-onboard.py`'s three sites live deep
inside a Click command body that needs heavy setup to invoke end-to-end, so
those are covered the same way `test_batch_create_waf_production_gate.py`
covers similarly embedded logic in this file: a source-inspection guard.
"""
from __future__ import annotations

import inspect
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import utility
import wrapper_api


class FakeResponse:
    def __init__(self, ok: bool, text: str = ''):
        self.ok = ok
        self.text = text


class FakeSession:
    def __init__(self, response):
        self._response = response

    def get(self, url, *args, **kwargs):
        return self._response


class TestUtilityCheckCliPrereqSubprocessShellOut:
    def _make_utility(self, monkeypatch):
        util = utility.utility(check_prereqs=False)
        monkeypatch.setattr(util, 'installedCommandCheck', lambda name: True)
        monkeypatch.setattr(util, 'executeCommand', lambda command: True)
        return util

    def test_group_missing_runs_list_command_without_shell(self, monkeypatch):
        util = self._make_utility(monkeypatch)
        click_args = {'group': None, 'contract': 'ctr_123'}
        config = SimpleNamespace(account_key=None)

        with patch('subprocess.run') as mock_run, pytest.raises(SystemExit):
            util.check_cli_prereq(click_args, config)

        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        assert args[0] == ['akamai', 'pm', 'lg']
        assert kwargs.get('shell', False) is False

    def test_contract_missing_runs_list_command_without_shell(self, monkeypatch):
        util = self._make_utility(monkeypatch)
        click_args = {'group': 'grp_1', 'contract': None}
        config = SimpleNamespace(account_key='1-ABC')

        with patch('subprocess.run') as mock_run, pytest.raises(SystemExit):
            util.check_cli_prereq(click_args, config)

        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        assert args[0] == ['akamai', 'pm', 'lc', '-s', 'default', '-a', '1-ABC']
        assert kwargs.get('shell', False) is False


class TestGetSelectableHostnamesSubprocessShellOut:
    def test_invalid_contract_group_runs_list_command_without_shell(self):
        session = FakeSession(FakeResponse(ok=False, text='error'))
        wrapper = wrapper_api.apiCallsWrapper(session=session, access_hostname='example.com', account_switch_key='1-ABCD')

        with patch('subprocess.run') as mock_run, pytest.raises(SystemExit):
            wrapper.get_selectable_hostnames(contract_id=123, group_id=456)

        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        assert args[0] == ['akamai', 'pm', '-s', 'default', 'lg', '-a', '1-ABCD']
        assert kwargs.get('shell', False) is False


class TestBatchCreateSourceNoLongerUsesShellTrue:
    def test_source_has_no_shell_true_subprocess_calls(self, akamai_onboard_module):
        source = inspect.getsource(akamai_onboard_module.batch_create.callback)

        assert 'shell=True' not in source
        assert source.count('shlex.split(command)') == 3
