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


class TestLogPmuserOriginDetection:
    """The `convert()` call site for this ticket: flag-gated detection + logging
    only, no rule tree mutation. Proves the no-op fallback promised in the ticket
    ("convert --unique-cpcode against a ruletree with no PMUSER_ORIGIN node
    produces an identical generated rule tree ... to convert without the flag")
    by asserting the rule tree is byte-for-byte unchanged, rather than relying on
    the call site never happening to touch it.
    """

    def test_noop_when_unique_cpcode_disabled(self, papi):
        rule_tree = {'name': 'default', 'children': [{'name': 'PMUSER_ORIGIN', 'children': []}]}
        before = copy.deepcopy(rule_tree)

        papi.log_pmuser_origin_detection('my-property', rule_tree, unique_cpcode_enabled=False)

        assert rule_tree == before

    def test_noop_when_pmuser_origin_absent(self, papi):
        rule_tree = {'name': 'default', 'children': [{'name': 'Origin', 'children': []}]}
        before = copy.deepcopy(rule_tree)

        papi.log_pmuser_origin_detection('my-property', rule_tree, unique_cpcode_enabled=True)

        assert rule_tree == before

    def test_noop_when_pmuser_origin_present(self, papi):
        rule_tree = {
            'name': 'default',
            'children': [{'name': 'PMUSER_ORIGIN', 'children': [
                {'name': 'www.example.com', 'children': []},
            ]}],
        }
        before = copy.deepcopy(rule_tree)

        papi.log_pmuser_origin_detection('my-property', rule_tree, unique_cpcode_enabled=True)

        assert rule_tree == before

    def test_logs_debug_message_when_node_found(self, papi, caplog):
        rule_tree = {
            'name': 'default',
            'children': [{'name': 'PMUSER_ORIGIN', 'children': [
                {'name': 'www.example.com', 'children': []},
            ]}],
        }

        with caplog.at_level(logging.DEBUG, logger='utility_papi'):
            papi.log_pmuser_origin_detection('my-property', rule_tree, unique_cpcode_enabled=True)

        assert 'my-property' in caplog.text
        assert 'PMUSER_ORIGIN' in caplog.text

    def test_logs_debug_message_when_node_absent(self, papi, caplog):
        rule_tree = {'name': 'default', 'children': []}

        with caplog.at_level(logging.DEBUG, logger='utility_papi'):
            papi.log_pmuser_origin_detection('my-property', rule_tree, unique_cpcode_enabled=True)

        assert 'my-property' in caplog.text
        assert 'no PMUSER_ORIGIN' in caplog.text

    def test_silent_when_unique_cpcode_disabled(self, papi, caplog):
        rule_tree = {'name': 'default', 'children': []}

        with caplog.at_level(logging.DEBUG, logger='utility_papi'):
            papi.log_pmuser_origin_detection('my-property', rule_tree, unique_cpcode_enabled=False)

        assert caplog.text == ''
