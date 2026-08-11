"""Block cpCode creation (root + --unique-cpcode) under --preview, plus
an added precondition: --preview only does anything for a property whose source
ruletree references hostnames beyond that property's --csv rows.

Two seams under test:
1. resolve_root_cpcode / inject_unique_cpcodes: search always runs, create only
   runs when not preview - under preview + not-found, a placeholder id 0 is used
   and a warning is logged naming the property/hostname.
2. has_hostnames_beyond_csv: the new --preview-only precondition gate.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pytest
from test_convert_unique_cpcode import _created_response
from test_convert_unique_cpcode import _found_response
from test_convert_unique_cpcode import _not_found_response
from test_convert_unique_cpcode import _onboard_object
from test_convert_unique_cpcode import _RecordingCpcodeWrapper

REPO_ROOT = Path(__file__).resolve().parent.parent


def _pmuser_origin_child(name, values):
    return {
        'name': name,
        'children': [],
        'behaviors': [{'name': 'setVariable', 'options': {'variableName': 'PMUSER_ORIGIN_HOSTNAME'}}],
        'criteria': [{'name': 'hostname', 'options': {'matchOperator': 'IS_ONE_OF', 'values': values}}],
        'criteriaMustSatisfy': 'all',
    }


def _pmuser_origin_rule_tree(children):
    return {'name': 'default', 'children': [{'name': 'PMUSER_ORIGIN', 'children': children}]}


class TestResolveRootCpcode:
    """convert()'s root-cpcode call-site glue (bin/akamai-onboard.py's per-property
    loop): search always runs; create only runs when not preview.
    """

    def test_preview_and_found_uses_real_id_no_create_no_warning(self, papi, click_args_factory, config_stub, caplog):
        onboard_object = _onboard_object(click_args_factory, config_stub)
        wrapper = _RecordingCpcodeWrapper(
            search_responses={'www.example.com': _found_response('www.example.com', 12345)})

        with caplog.at_level(logging.WARNING, logger='utility_papi'):
            cpcode = papi.resolve_root_cpcode(onboard_object, wrapper, 'www.example.com',
                                              'ctr_1', 'grp_1', 'prd_1', 'my-property', 'www.example.com',
                                              preview=True)

        assert cpcode == 12345
        assert wrapper.search_calls == ['www.example.com']
        assert wrapper.create_calls == []
        assert 'preview run' not in caplog.text

    def test_preview_and_not_found_injects_placeholder_and_warns(self, papi, click_args_factory, config_stub, caplog):
        onboard_object = _onboard_object(click_args_factory, config_stub)
        wrapper = _RecordingCpcodeWrapper(search_responses={'new.example.com': _not_found_response()})

        with caplog.at_level(logging.WARNING, logger='utility_papi'):
            cpcode = papi.resolve_root_cpcode(onboard_object, wrapper, 'new.example.com',
                                              'ctr_1', 'grp_1', 'prd_1', 'my-property', 'new.example.com',
                                              preview=True)

        assert cpcode == 0
        assert wrapper.search_calls == ['new.example.com']
        assert wrapper.create_calls == []
        assert 'my-property' in caplog.text
        assert 'new.example.com' in caplog.text

    def test_non_preview_and_found_uses_real_id(self, papi, click_args_factory, config_stub):
        onboard_object = _onboard_object(click_args_factory, config_stub)
        wrapper = _RecordingCpcodeWrapper(
            search_responses={'www.example.com': _found_response('www.example.com', 12345)})

        cpcode = papi.resolve_root_cpcode(onboard_object, wrapper, 'www.example.com',
                                          'ctr_1', 'grp_1', 'prd_1', 'my-property', 'www.example.com',
                                          preview=False)

        assert cpcode == 12345
        assert wrapper.search_calls == ['www.example.com']
        assert wrapper.create_calls == []

    def test_non_preview_and_not_found_creates_real_cpcode(self, papi, click_args_factory, config_stub):
        onboard_object = _onboard_object(click_args_factory, config_stub)
        wrapper = _RecordingCpcodeWrapper(
            search_responses={'new.example.com': _not_found_response()},
            create_responses={'new.example.com': _created_response(55555)},
        )

        cpcode = papi.resolve_root_cpcode(onboard_object, wrapper, 'new.example.com',
                                          'ctr_1', 'grp_1', 'prd_1', 'my-property', 'new.example.com',
                                          preview=False)

        assert cpcode == 55555
        assert wrapper.search_calls == ['new.example.com']
        assert wrapper.create_calls == ['new.example.com']


class TestInjectUniqueCpcodesPreviewGate:
    """--unique-cpcode's per-hostname cpcode path (inject_unique_cpcodes): same
    found/not-found x preview/non-preview table as the root cpcode path.

    Exercises the real inject_cpcode_behavior/template load, so CWD is pinned to
    repo root, not ~/.akamai-cli.
    """

    @pytest.fixture(autouse=True)
    def _repo_root_cwd(self, monkeypatch):
        monkeypatch.chdir(REPO_ROOT)

    _child = staticmethod(_pmuser_origin_child)
    _rule_tree = staticmethod(_pmuser_origin_rule_tree)

    def test_preview_and_found_uses_real_id_no_create(self, papi, click_args_factory, config_stub, caplog):
        matched = self._child('www.example.com', ['www.example.com'])
        rule_tree = self._rule_tree([matched])
        onboard_object = _onboard_object(click_args_factory, config_stub)
        wrapper = _RecordingCpcodeWrapper(
            search_responses={'www.example.com': _found_response('www.example.com', 67890)})

        with caplog.at_level(logging.WARNING, logger='utility_papi'):
            result = papi.inject_unique_cpcodes(onboard_object, wrapper, 'my-property', rule_tree,
                                                ['www.example.com'], 'ctr_1', 'grp_1', 'prd_1', preview=True)

        assert result == {'www.example.com': 67890}
        assert wrapper.create_calls == []
        assert {'name': 'cpCode', 'options': {'value': {'id': 67890}}} in matched['behaviors']
        assert 'preview run' not in caplog.text

    def test_preview_and_not_found_injects_placeholder_and_warns(self, papi, click_args_factory, config_stub, caplog):
        matched = self._child('new.example.com', ['new.example.com'])
        rule_tree = self._rule_tree([matched])
        onboard_object = _onboard_object(click_args_factory, config_stub)
        wrapper = _RecordingCpcodeWrapper(search_responses={'new.example.com': _not_found_response()})

        with caplog.at_level(logging.WARNING, logger='utility_papi'):
            result = papi.inject_unique_cpcodes(onboard_object, wrapper, 'my-property', rule_tree,
                                                ['new.example.com'], 'ctr_1', 'grp_1', 'prd_1', preview=True)

        assert result == {'new.example.com': 0}
        assert wrapper.create_calls == []
        assert {'name': 'cpCode', 'options': {'value': {'id': 0}}} in matched['behaviors']
        assert 'my-property' in caplog.text
        assert 'new.example.com' in caplog.text

    def test_non_preview_and_found_uses_real_id(self, papi, click_args_factory, config_stub):
        matched = self._child('www.example.com', ['www.example.com'])
        rule_tree = self._rule_tree([matched])
        onboard_object = _onboard_object(click_args_factory, config_stub)
        wrapper = _RecordingCpcodeWrapper(
            search_responses={'www.example.com': _found_response('www.example.com', 67890)})

        result = papi.inject_unique_cpcodes(onboard_object, wrapper, 'my-property', rule_tree,
                                            ['www.example.com'], 'ctr_1', 'grp_1', 'prd_1', preview=False)

        assert result == {'www.example.com': 67890}
        assert wrapper.create_calls == []

    def test_non_preview_and_not_found_creates_real_cpcode(self, papi, click_args_factory, config_stub):
        matched = self._child('new.example.com', ['new.example.com'])
        rule_tree = self._rule_tree([matched])
        onboard_object = _onboard_object(click_args_factory, config_stub)
        wrapper = _RecordingCpcodeWrapper(
            search_responses={'new.example.com': _not_found_response()},
            create_responses={'new.example.com': _created_response(55555)},
        )

        result = papi.inject_unique_cpcodes(onboard_object, wrapper, 'my-property', rule_tree,
                                            ['new.example.com'], 'ctr_1', 'grp_1', 'prd_1', preview=False)

        assert result == {'new.example.com': 55555}
        assert wrapper.create_calls == ['new.example.com']


class TestApplyUniqueCpcodeInjectionPreviewPassthrough:
    """convert()'s --unique-cpcode injection call-site gate (apply_unique_cpcode_injection):
    confirms `preview` threads through to inject_unique_cpcodes rather than being dropped.

    Exercises the real inject_cpcode_behavior/template load, so CWD is pinned to
    repo root, not ~/.akamai-cli.
    """

    @pytest.fixture(autouse=True)
    def _repo_root_cwd(self, monkeypatch):
        monkeypatch.chdir(REPO_ROOT)

    _child = staticmethod(_pmuser_origin_child)
    _rule_tree = staticmethod(_pmuser_origin_rule_tree)

    def test_preview_true_is_forwarded_and_skips_create(self, papi, click_args_factory, config_stub):
        matched = self._child('new.example.com', ['new.example.com'])
        rule_tree = self._rule_tree([matched])
        onboard_object = _onboard_object(click_args_factory, config_stub)
        wrapper = _RecordingCpcodeWrapper(search_responses={'new.example.com': _not_found_response()})

        result = papi.apply_unique_cpcode_injection(onboard_object, wrapper, 'my-property', rule_tree,
                                                     ['new.example.com'], 'ctr_1', 'grp_1', 'prd_1',
                                                     enabled=True, preview=True)

        assert result == {'new.example.com': 0}
        assert wrapper.create_calls == []

    def test_preview_defaults_to_false_and_creates_when_not_found(self, papi, click_args_factory, config_stub):
        matched = self._child('new.example.com', ['new.example.com'])
        rule_tree = self._rule_tree([matched])
        onboard_object = _onboard_object(click_args_factory, config_stub)
        wrapper = _RecordingCpcodeWrapper(
            search_responses={'new.example.com': _not_found_response()},
            create_responses={'new.example.com': _created_response(55555)},
        )

        result = papi.apply_unique_cpcode_injection(onboard_object, wrapper, 'my-property', rule_tree,
                                                     ['new.example.com'], 'ctr_1', 'grp_1', 'prd_1', enabled=True)

        assert result == {'new.example.com': 55555}
        assert wrapper.create_calls == ['new.example.com']


class TestHasHostnamesBeyondCsv:
    """The added --preview precondition: a preview is only meaningful when the
    source ruletree references hostnames beyond this property's --csv rows.
    """

    @staticmethod
    def _pmuser_origin_tree(children):
        return {'name': 'default', 'children': [{'name': 'PMUSER_ORIGIN', 'children': children}]}

    @staticmethod
    def _pmuser_origin_child(name, values):
        return {
            'name': name, 'children': [],
            'criteria': [{'name': 'hostname', 'options': {'values': values}}],
        }

    @staticmethod
    def _page_rules_tree(children):
        return {'name': 'default', 'children': [{'name': 'Page Rules', 'children': children}]}

    @staticmethod
    def _hostname_child(name, values):
        return {
            'name': name, 'children': [],
            'criteria': [{'name': 'hostname', 'options': {'values': values}}],
        }

    def test_exact_match_pmuser_origin_has_no_extra(self, papi):
        rule_tree = self._pmuser_origin_tree([self._pmuser_origin_child('www.example.com', ['www.example.com'])])

        assert papi.has_hostnames_beyond_csv(rule_tree, ['www.example.com']) is False

    def test_extra_pmuser_origin_hostname_is_detected(self, papi):
        rule_tree = self._pmuser_origin_tree([
            self._pmuser_origin_child('www.example.com', ['www.example.com']),
            self._pmuser_origin_child('old.example.com', ['old.example.com']),
        ])

        assert papi.has_hostnames_beyond_csv(rule_tree, ['www.example.com']) is True

    def test_exact_match_page_rules_has_no_extra(self, papi):
        rule_tree = self._page_rules_tree([self._hostname_child('www.example.com', ['www.example.com'])])

        assert papi.has_hostnames_beyond_csv(rule_tree, ['www.example.com']) is False

    def test_extra_page_rules_hostname_is_detected(self, papi):
        rule_tree = self._page_rules_tree([
            self._hostname_child('www.example.com', ['www.example.com']),
            self._hostname_child('old.example.com', ['old.example.com']),
        ])

        assert papi.has_hostnames_beyond_csv(rule_tree, ['www.example.com']) is True

    def test_no_hostname_scoped_content_at_all_has_no_extra(self, papi):
        rule_tree = {'name': 'default', 'children': [{'name': 'Shared Variables', 'children': []}]}

        assert papi.has_hostnames_beyond_csv(rule_tree, ['www.example.com']) is False

    def test_match_is_case_insensitive(self, papi):
        rule_tree = self._pmuser_origin_tree([self._pmuser_origin_child('WWW.EXAMPLE.COM', ['WWW.EXAMPLE.COM'])])

        assert papi.has_hostnames_beyond_csv(rule_tree, ['www.example.com']) is False
