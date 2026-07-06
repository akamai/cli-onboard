from __future__ import annotations

import generate_convert_tests as cli_stub
import pytest

from .scenarios import Scenario


def test_no_arguments_requires_layer(capsys):
    with pytest.raises(SystemExit) as exc_info:
        cli_stub.main([])

    assert exc_info.value.code != 0
    captured = capsys.readouterr()
    assert '--layer' in captured.err


def test_layer_local_exits_zero_with_placeholder_message(capsys):
    cli_stub.main(['--layer', 'local'])

    captured = capsys.readouterr()
    assert 'local' in captured.out


def test_invalid_layer_choice_rejected():
    with pytest.raises(SystemExit) as exc_info:
        cli_stub.main(['--layer', 'bogus'])

    assert exc_info.value.code != 0


def test_stub_confirms_scenario_package_wiring(capsys):
    cli_stub.main(['--layer', 'local'])

    captured = capsys.readouterr()
    assert Scenario.__name__ in captured.out
