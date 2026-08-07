from __future__ import annotations

import copy
import logging


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
