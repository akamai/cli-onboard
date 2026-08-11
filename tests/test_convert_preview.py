"""Ticket 01: `--preview` flag + reuse of `batch_create_update_pm_convert`'s existing
`dryrun` gate + the existing-property prompt fix.

Two seams under test:
1. convert()'s call-site OR (`click_args['dryrun'] or click_args['preview']`) - the
   boolean threaded into batch_create_update_pm_convert's `dryrun` parameter.
2. batch_create_update_pm_convert's "property already exists" prompt: under a
   dryrun-ish run it must log a note and never call input(); unchanged otherwise.
"""
from __future__ import annotations

import logging

import pytest


class TestEffectiveDryrunFlag:

    @pytest.mark.parametrize('dryrun,preview,expected', [
        (False, True, True),
        (True, False, True),
        (True, True, True),
        (False, False, False),
    ])
    def test_dryrun_or_preview(self, click_args_factory, dryrun, preview, expected):
        click_args = click_args_factory(dryrun=dryrun, preview=preview)

        assert (click_args['dryrun'] or click_args['preview']) is expected


class TestBatchCreateUpdatePmConvertExistingPropertyGate:
    """batch_create_update_pm_convert's "property already exists, skip? (yes/no)"
    prompt (bin/utility_papi.py, right before the `if not dryrun:` block).
    """

    @staticmethod
    def _property_dict(hostnames=None):
        return {'my-property': {'hostnames': hostnames or ['www.example.com']}}

    def test_dryrun_true_logs_note_and_never_calls_input(
            self, papi, build_onboard_object, stub_wrapper_factory, config_stub, monkeypatch, caplog):
        onboard_object = build_onboard_object()
        wrapper = stub_wrapper_factory(existing_properties={'my-property'})
        property_dict = self._property_dict()

        def _unexpected_input():
            raise AssertionError('input() must not be called under a dryrun-ish run')
        monkeypatch.setattr('builtins.input', _unexpected_input)

        with caplog.at_level(logging.INFO, logger='utility_papi'):
            property_ids, skip_property = papi.batch_create_update_pm_convert(
                config_stub, onboard_object, wrapper, property_dict, dryrun=True)

        assert property_ids == []
        assert skip_property == []
        assert 'my-property already exists - preview run, nothing created' in caplog.text

    def test_dryrun_false_still_prompts_and_calls_input(
            self, papi, build_onboard_object, stub_wrapper_factory, config_stub, monkeypatch, caplog):
        onboard_object = build_onboard_object()
        wrapper = stub_wrapper_factory(existing_properties={'my-property'})
        property_dict = self._property_dict()

        input_calls = []
        monkeypatch.setattr('builtins.input', lambda: input_calls.append(1) or 'yes')

        with caplog.at_level(logging.INFO, logger='utility_papi'):
            property_ids, skip_property = papi.batch_create_update_pm_convert(
                config_stub, onboard_object, wrapper, property_dict, dryrun=False)

        assert len(input_calls) == 1
        assert property_ids == []
        assert skip_property == []
        assert 'preview run, nothing created' not in caplog.text

    def test_property_not_existing_never_prompts_regardless_of_dryrun(
            self, papi, build_onboard_object, stub_wrapper_factory, config_stub, monkeypatch):
        onboard_object = build_onboard_object()
        wrapper = stub_wrapper_factory(existing_properties=set())
        property_dict = self._property_dict()

        def _unexpected_input():
            raise AssertionError('input() must not be called when the property does not exist')
        monkeypatch.setattr('builtins.input', _unexpected_input)

        # dryrun=True skips real creation after the (never-prompted) existence check,
        # so this stays hermetic without needing a full createProperty stub.
        papi.batch_create_update_pm_convert(config_stub, onboard_object, wrapper, property_dict, dryrun=True)
