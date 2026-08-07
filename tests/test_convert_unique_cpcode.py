from __future__ import annotations

import copy
import logging
from pathlib import Path

import pytest
from test_cpcode_lookup import _FakeResponse

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestFindPmuserOriginNode:
    def test_finds_top_level_child(self, papi):
        rule_tree = {
            'name': 'default',
            'children': [
                {'name': 'Shared Variables', 'children': []},
                {'name': 'PMUSER_ORIGIN', 'children': [
                    {'name': 'www.example.com', 'children': []},
                ]},
            ],
        }

        node = papi.find_pmuser_origin_node(rule_tree)

        assert node is not None
        assert node['name'] == 'PMUSER_ORIGIN'
        assert node['children'][0]['name'] == 'www.example.com'

    def test_finds_node_nested_deeper_than_one_level(self, papi):
        rule_tree = {
            'name': 'default',
            'children': [
                {'name': 'Outer', 'children': [
                    {'name': 'PMUSER_ORIGIN', 'children': []},
                ]},
            ],
        }

        node = papi.find_pmuser_origin_node(rule_tree)

        assert node is not None
        assert node['name'] == 'PMUSER_ORIGIN'

    def test_returns_none_when_absent(self, papi):
        rule_tree = {'name': 'default', 'children': [{'name': 'Origin', 'children': []}]}

        assert papi.find_pmuser_origin_node(rule_tree) is None

    def test_returns_none_for_leaf_rule_with_no_children_key(self, papi):
        assert papi.find_pmuser_origin_node({'name': 'default'}) is None

    def test_root_itself_named_pmuser_origin(self, papi):
        rule_tree = {'name': 'PMUSER_ORIGIN', 'children': []}

        assert papi.find_pmuser_origin_node(rule_tree) is rule_tree


class TestPruneCsvUnmatchedPmuserOriginChildren:

    @staticmethod
    def _child(name, values):
        return {
            'name': name,
            'children': [],
            'behaviors': [{'name': 'setVariable', 'options': {'variableName': 'PMUSER_ORIGIN_HOSTNAME'}}],
            'criteria': [{'name': 'hostname', 'options': {'matchOperator': 'IS_ONE_OF', 'values': values}}],
            'criteriaMustSatisfy': 'all',
        }

    @staticmethod
    def _rule_tree(children):
        return {'name': 'default', 'children': [{'name': 'PMUSER_ORIGIN', 'children': children}]}

    def test_no_pmuser_origin_node_is_a_noop(self, papi):
        rule_tree = {'name': 'default', 'children': [{'name': 'Origin', 'children': []}]}
        before = copy.deepcopy(rule_tree)

        pruned = papi.prune_pmuser_origin_children('my-property', rule_tree, ['www.example.com'])

        assert pruned == []
        assert rule_tree == before

    def test_wildcard_child_is_preserved(self, papi):
        wildcard = self._child('*.example.com', ['*.example.com'])
        rule_tree = self._rule_tree([wildcard])

        pruned = papi.prune_pmuser_origin_children('my-property', rule_tree, ['www.example.com'])

        assert rule_tree['children'][0]['children'] == [wildcard]
        assert pruned == []

    def test_single_value_match_is_kept(self, papi):
        matched = self._child('www.example.com', ['www.example.com'])
        rule_tree = self._rule_tree([matched])

        pruned = papi.prune_pmuser_origin_children('my-property', rule_tree, ['www.example.com'])

        assert rule_tree['children'][0]['children'] == [matched]
        assert pruned == []

    def test_single_value_no_match_is_pruned(self, papi):
        unmatched = self._child('old.example.com', ['old.example.com'])
        rule_tree = self._rule_tree([unmatched])

        pruned = papi.prune_pmuser_origin_children('my-property', rule_tree, ['www.example.com'])

        assert rule_tree['children'][0]['children'] == []
        assert pruned == ['old.example.com']

    def test_multi_value_all_match_is_kept(self, papi):
        matched = self._child('multi', ['a.example.com', 'b.example.com'])
        rule_tree = self._rule_tree([matched])

        pruned = papi.prune_pmuser_origin_children(
            'my-property', rule_tree, ['a.example.com', 'b.example.com'])

        assert rule_tree['children'][0]['children'] == [matched]
        assert pruned == []

    def test_multi_value_partial_match_is_left_untouched_and_warns(self, papi, caplog):
        partial = self._child('multi', ['a.example.com', 'b.example.com'])
        rule_tree = self._rule_tree([partial])

        with caplog.at_level(logging.WARNING, logger='utility_papi'):
            pruned = papi.prune_pmuser_origin_children('my-property', rule_tree, ['a.example.com'])

        assert rule_tree['children'][0]['children'] == [partial]
        assert pruned == []
        assert 'my-property' in caplog.text
        assert 'multi' in caplog.text
        # only the actually-mismatched value is named, not the whole criteria list
        assert 'b.example.com' in caplog.text
        assert 'a.example.com' not in caplog.text

    def test_match_is_case_insensitive(self, papi):
        matched = self._child('WWW.EXAMPLE.COM', ['WWW.EXAMPLE.COM'])
        rule_tree = self._rule_tree([matched])

        pruned = papi.prune_pmuser_origin_children('my-property', rule_tree, ['www.example.com'])

        assert rule_tree['children'][0]['children'] == [matched]
        assert pruned == []

    def test_child_with_no_hostname_criteria_is_pruned(self, papi):
        no_criteria_child = {
            'name': 'weird', 'children': [], 'behaviors': [], 'criteria': [], 'criteriaMustSatisfy': 'all',
        }
        rule_tree = self._rule_tree([no_criteria_child])

        pruned = papi.prune_pmuser_origin_children('my-property', rule_tree, ['www.example.com'])

        assert rule_tree['children'][0]['children'] == []
        assert pruned == []

    def test_all_children_pruned_warns_and_continues(self, papi, caplog):
        unmatched = self._child('old.example.com', ['old.example.com'])
        rule_tree = self._rule_tree([unmatched])

        with caplog.at_level(logging.WARNING, logger='utility_papi'):
            pruned = papi.prune_pmuser_origin_children('my-property', rule_tree, ['www.example.com'])

        assert rule_tree['children'][0]['children'] == []
        assert pruned == ['old.example.com']
        assert 'my-property' in caplog.text
        assert 'no PMUSER_ORIGIN children matched' in caplog.text

    def test_surviving_wildcard_does_not_suppress_empty_match_warning(self, papi, caplog):
        wildcard = self._child('*.example.com', ['*.example.com'])
        unmatched = self._child('old.example.com', ['old.example.com'])
        rule_tree = self._rule_tree([wildcard, unmatched])

        with caplog.at_level(logging.WARNING, logger='utility_papi'):
            pruned = papi.prune_pmuser_origin_children('my-property', rule_tree, ['www.example.com'])

        assert rule_tree['children'][0]['children'] == [wildcard]
        assert pruned == ['old.example.com']
        assert 'no PMUSER_ORIGIN children matched' in caplog.text

    def test_mixed_children_keep_prune_and_partial_together(self, papi, caplog):
        wildcard = self._child('*.example.com', ['*.example.com'])
        matched = self._child('www.example.com', ['www.example.com'])
        unmatched = self._child('old.example.com', ['old.example.com'])
        partial = self._child('multi', ['a.example.com', 'zzz.example.com'])
        rule_tree = self._rule_tree([wildcard, matched, unmatched, partial])

        with caplog.at_level(logging.WARNING, logger='utility_papi'):
            pruned = papi.prune_pmuser_origin_children(
                'my-property', rule_tree, ['www.example.com', 'a.example.com'])

        assert rule_tree['children'][0]['children'] == [wildcard, matched, partial]
        assert pruned == ['old.example.com']


class TestApplyUniqueCpcode:
    """convert()'s actual call-site glue: gates prune_pmuser_origin_children
    behind the --unique-cpcode flag value. This is what feeds
    property_dict[property]['prunedHostnames'] in bin/akamai-onboard.py.
    """

    def test_disabled_is_a_noop_and_never_touches_the_rule_tree(self, papi):
        rule_tree = {
            'name': 'default',
            'children': [{'name': 'PMUSER_ORIGIN', 'children': [
                {
                    'name': 'old.example.com', 'children': [],
                    'behaviors': [],
                    'criteria': [{'name': 'hostname', 'options': {'values': ['old.example.com']}}],
                    'criteriaMustSatisfy': 'all',
                },
            ]}],
        }
        before = copy.deepcopy(rule_tree)

        pruned = papi.apply_unique_cpcode('my-property', rule_tree, ['www.example.com'], enabled=False)

        assert pruned == []
        assert rule_tree == before

    def test_enabled_delegates_to_prune_pmuser_origin_children(self, papi):
        rule_tree = {
            'name': 'default',
            'children': [{'name': 'PMUSER_ORIGIN', 'children': [
                {
                    'name': 'old.example.com', 'children': [],
                    'behaviors': [],
                    'criteria': [{'name': 'hostname', 'options': {'values': ['old.example.com']}}],
                    'criteriaMustSatisfy': 'all',
                },
            ]}],
        }

        pruned = papi.apply_unique_cpcode('my-property', rule_tree, ['www.example.com'], enabled=True)

        assert pruned == ['old.example.com']
        assert rule_tree['children'][0]['children'] == []


def _onboard_object(click_args_factory, config_stub):
    import onboard_convert
    return onboard_convert.onboard(config_stub, click_args_factory())


class _RecordingCpcodeWrapper:
    """Fake PAPI wrapper for search/create cpcode calls, keyed by cpcode_name -
    lets one test drive several different PMUSER_ORIGIN hostnames through
    inject_unique_cpcodes and assert on each independently, without hitting a
    real API.
    """

    def __init__(self, search_responses=None, create_responses=None):
        self._search_responses = search_responses or {}
        self._create_responses = create_responses or {}
        self.search_calls = []
        self.create_calls = []

    def searchCpcode(self, contract_id, group_id, product_id, cpcode_name):
        self.search_calls.append(cpcode_name)
        return self._search_responses[cpcode_name]

    def createCpcode(self, contract_id, group_id, product_id, cpcode_name):
        self.create_calls.append(cpcode_name)
        return self._create_responses[cpcode_name]


def _not_found_response():
    return _FakeResponse(ok=True, status_code=200, json_body={'cpcodes': []})


def _found_response(cpcode_name, cpcode_id):
    return _FakeResponse(ok=True, status_code=200, json_body={
        'cpcodes': [{'cpcodeName': cpcode_name, 'cpcodeId': cpcode_id}],
    })


def _created_response(cpcode_id):
    return _FakeResponse(ok=True, status_code=201, json_body={'cpcodeLink': f'/papi/v1/cpcodes/cpc_{cpcode_id}?x'})


class TestInjectUniqueCpcodes:
    """Ticket 03: inject_unique_cpcodes(). Exercises the real inject_cpcode_behavior
    (and its cpCode.json template load), so CWD is pinned to the repo root rather
    than relying on ~/.akamai-cli being installed on the machine running the tests.
    """

    @pytest.fixture(autouse=True)
    def _repo_root_cwd(self, monkeypatch):
        monkeypatch.chdir(REPO_ROOT)

    _child = staticmethod(TestPruneCsvUnmatchedPmuserOriginChildren._child)
    _rule_tree = staticmethod(TestPruneCsvUnmatchedPmuserOriginChildren._rule_tree)

    def test_no_pmuser_origin_node_is_a_noop(self, papi, click_args_factory, config_stub):
        rule_tree = {'name': 'default', 'children': [{'name': 'Origin', 'children': []}]}
        onboard_object = _onboard_object(click_args_factory, config_stub)
        wrapper = _RecordingCpcodeWrapper()

        result = papi.inject_unique_cpcodes(onboard_object, wrapper, 'my-property', rule_tree,
                                            ['www.example.com'], 'ctr_1', 'grp_1', 'prd_1')

        assert result == {}
        assert wrapper.search_calls == []

    def test_wildcard_child_is_skipped(self, papi, click_args_factory, config_stub):
        wildcard = self._child('*.example.com', ['*.example.com'])
        rule_tree = self._rule_tree([wildcard])
        onboard_object = _onboard_object(click_args_factory, config_stub)
        wrapper = _RecordingCpcodeWrapper()

        result = papi.inject_unique_cpcodes(onboard_object, wrapper, 'my-property', rule_tree,
                                            ['www.example.com'], 'ctr_1', 'grp_1', 'prd_1')

        assert result == {}
        assert wrapper.search_calls == []
        assert all(behavior['name'] != 'cpCode' for behavior in wildcard['behaviors'])

    def test_partial_match_child_is_skipped(self, papi, click_args_factory, config_stub):
        partial = self._child('multi', ['a.example.com', 'b.example.com'])
        rule_tree = self._rule_tree([partial])
        onboard_object = _onboard_object(click_args_factory, config_stub)
        wrapper = _RecordingCpcodeWrapper()

        result = papi.inject_unique_cpcodes(onboard_object, wrapper, 'my-property', rule_tree,
                                            ['a.example.com'], 'ctr_1', 'grp_1', 'prd_1')

        assert result == {}
        assert wrapper.search_calls == []

    def test_no_match_child_is_skipped(self, papi, click_args_factory, config_stub):
        unmatched = self._child('old.example.com', ['old.example.com'])
        rule_tree = self._rule_tree([unmatched])
        onboard_object = _onboard_object(click_args_factory, config_stub)
        wrapper = _RecordingCpcodeWrapper()

        result = papi.inject_unique_cpcodes(onboard_object, wrapper, 'my-property', rule_tree,
                                            ['www.example.com'], 'ctr_1', 'grp_1', 'prd_1')

        assert result == {}
        assert wrapper.search_calls == []

    def test_multi_value_full_match_is_skipped_and_warns(self, papi, click_args_factory, config_stub, caplog):
        matched_multi = self._child('multi', ['a.example.com', 'b.example.com'])
        rule_tree = self._rule_tree([matched_multi])
        onboard_object = _onboard_object(click_args_factory, config_stub)
        wrapper = _RecordingCpcodeWrapper()

        with caplog.at_level(logging.WARNING, logger='utility_papi'):
            result = papi.inject_unique_cpcodes(onboard_object, wrapper, 'my-property', rule_tree,
                                                ['a.example.com', 'b.example.com'], 'ctr_1', 'grp_1', 'prd_1')

        assert result == {}
        assert wrapper.search_calls == []
        assert 'my-property' in caplog.text
        assert 'ambiguous' in caplog.text.lower()

    def test_single_value_full_match_reuses_existing_cpcode(self, papi, click_args_factory, config_stub):
        matched = self._child('www.example.com', ['www.example.com'])
        rule_tree = self._rule_tree([matched])
        onboard_object = _onboard_object(click_args_factory, config_stub)
        wrapper = _RecordingCpcodeWrapper(
            search_responses={'www.example.com': _found_response('www.example.com', 67890)},
        )

        result = papi.inject_unique_cpcodes(onboard_object, wrapper, 'my-property', rule_tree,
                                            ['www.example.com'], 'ctr_1', 'grp_1', 'prd_1')

        assert result == {'www.example.com': 67890}
        assert wrapper.search_calls == ['www.example.com']
        assert wrapper.create_calls == []
        assert {'name': 'cpCode', 'options': {'value': {'id': 67890}}} in matched['behaviors']

    def test_single_value_full_match_creates_cpcode_when_not_found(self, papi, click_args_factory, config_stub):
        matched = self._child('new.example.com', ['new.example.com'])
        rule_tree = self._rule_tree([matched])
        onboard_object = _onboard_object(click_args_factory, config_stub)
        wrapper = _RecordingCpcodeWrapper(
            search_responses={'new.example.com': _not_found_response()},
            create_responses={'new.example.com': _created_response(55555)},
        )

        result = papi.inject_unique_cpcodes(onboard_object, wrapper, 'my-property', rule_tree,
                                            ['new.example.com'], 'ctr_1', 'grp_1', 'prd_1')

        assert result == {'new.example.com': 55555}
        assert wrapper.search_calls == ['new.example.com']
        assert wrapper.create_calls == ['new.example.com']
        assert {'name': 'cpCode', 'options': {'value': {'id': 55555}}} in matched['behaviors']

    def test_multiple_single_value_children_each_get_independent_cpcodes(self, papi, click_args_factory, config_stub):
        first = self._child('a.example.com', ['a.example.com'])
        second = self._child('b.example.com', ['b.example.com'])
        rule_tree = self._rule_tree([first, second])
        onboard_object = _onboard_object(click_args_factory, config_stub)
        wrapper = _RecordingCpcodeWrapper(
            search_responses={
                'a.example.com': _found_response('a.example.com', 111),
                'b.example.com': _not_found_response(),
            },
            create_responses={'b.example.com': _created_response(222)},
        )

        result = papi.inject_unique_cpcodes(onboard_object, wrapper, 'my-property', rule_tree,
                                            ['a.example.com', 'b.example.com'], 'ctr_1', 'grp_1', 'prd_1')

        assert result == {'a.example.com': 111, 'b.example.com': 222}
        assert sorted(wrapper.search_calls) == ['a.example.com', 'b.example.com']
        assert wrapper.create_calls == ['b.example.com']


class TestApplyUniqueCpcodeInjection:
    """convert()'s actual injection call-site glue: gates inject_unique_cpcodes
    behind the --unique-cpcode flag value, mirroring TestApplyUniqueCpcode for
    the pruning half.
    """

    @pytest.fixture(autouse=True)
    def _repo_root_cwd(self, monkeypatch):
        monkeypatch.chdir(REPO_ROOT)

    _child = staticmethod(TestPruneCsvUnmatchedPmuserOriginChildren._child)
    _rule_tree = staticmethod(TestPruneCsvUnmatchedPmuserOriginChildren._rule_tree)

    def test_disabled_is_a_noop_and_never_touches_the_rule_tree(self, papi, click_args_factory, config_stub):
        matched = self._child('www.example.com', ['www.example.com'])
        rule_tree = self._rule_tree([matched])
        before = copy.deepcopy(rule_tree)
        onboard_object = _onboard_object(click_args_factory, config_stub)
        wrapper = _RecordingCpcodeWrapper()

        result = papi.apply_unique_cpcode_injection(onboard_object, wrapper, 'my-property', rule_tree,
                                                     ['www.example.com'], 'ctr_1', 'grp_1', 'prd_1', enabled=False)

        assert result == {}
        assert wrapper.search_calls == []
        assert rule_tree == before

    def test_enabled_delegates_to_inject_unique_cpcodes(self, papi, click_args_factory, config_stub):
        matched = self._child('www.example.com', ['www.example.com'])
        rule_tree = self._rule_tree([matched])
        onboard_object = _onboard_object(click_args_factory, config_stub)
        wrapper = _RecordingCpcodeWrapper(
            search_responses={'www.example.com': _found_response('www.example.com', 67890)},
        )

        result = papi.apply_unique_cpcode_injection(onboard_object, wrapper, 'my-property', rule_tree,
                                                     ['www.example.com'], 'ctr_1', 'grp_1', 'prd_1', enabled=True)

        assert result == {'www.example.com': 67890}
        assert wrapper.search_calls == ['www.example.com']
