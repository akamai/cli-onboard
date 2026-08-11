from __future__ import annotations

import copy
import logging


class TestFullUrlHostname:

    def test_bare_url_with_scheme_resolves_to_netloc(self, papi):
        assert papi._full_url_hostname('https://account.mrcooper.com/path') == 'account.mrcooper.com'

    def test_trailing_wildcard_url_resolves_to_netloc(self, papi):
        value = 'https://account.mrcooper.com/ed04d0f3/oauth2/v2.0/authorize?p=B2C_1A_PasswordReset*'
        assert papi._full_url_hostname(value) == 'account.mrcooper.com'

    def test_leading_and_trailing_wildcard_with_no_scheme_resolves_to_bare_host(self, papi):
        assert papi._full_url_hostname('*homepoint.mrcooper.com*') == 'homepoint.mrcooper.com'

    def test_trailing_slash_wildcard_url_resolves_to_netloc(self, papi):
        assert papi._full_url_hostname('https://cooperclientconnect.mrcooper.com/*') == 'cooperclientconnect.mrcooper.com'

    def test_no_wildcard_no_scheme_value_is_returned_unchanged(self, papi):
        assert papi._full_url_hostname('www.example.com') == 'www.example.com'


class TestHostnameScopedChildValues:

    @staticmethod
    def _hostname_child(values):
        return {
            'name': 'child',
            'children': [],
            'criteria': [{'name': 'hostname', 'options': {'matchOperator': 'IS_ONE_OF', 'values': values}}],
        }

    @staticmethod
    def _full_url_child(values, extra_criteria=None):
        criteria = [{'name': 'matchVariable',
                     'options': {'variableName': 'PMUSER_FULL_URL', 'matchOperator': 'IS_ONE_OF',
                                 'variableValues': values}}]
        if extra_criteria:
            criteria.extend(extra_criteria)
        return {'name': 'child', 'children': [], 'criteria': criteria}

    def test_hostname_criterion_values_used_as_is(self, papi):
        child = self._hostname_child(['www.example.com'])

        assert papi._hostname_scoped_child_values(child) == ['www.example.com']

    def test_pmuser_full_url_values_are_resolved(self, papi):
        child = self._full_url_child(['*homepoint.mrcooper.com*'])

        assert papi._hostname_scoped_child_values(child) == ['homepoint.mrcooper.com']

    def test_unrelated_matchvariable_is_ignored(self, papi):
        child = self._full_url_child(
            ['https://account.mrcooper.com/path*'],
            extra_criteria=[{'name': 'matchVariable',
                              'options': {'variableName': 'PMUSER_QUERY', 'matchOperator': 'IS_NOT_ONE_OF',
                                          'variableValues': ['*connection=rkt*']}}],
        )

        assert papi._hostname_scoped_child_values(child) == ['account.mrcooper.com']

    def test_child_with_no_qualifying_criteria_returns_empty_list(self, papi):
        child = {'name': 'weird', 'children': [], 'criteria': []}

        assert papi._hostname_scoped_child_values(child) == []


class TestFindHostnameScopedContainers:

    def test_finds_container_whose_children_carry_hostname_criteria(self, papi):
        rule_tree = {
            'name': 'default',
            'children': [
                {'name': 'Page Rules', 'children': [
                    {'name': 'www.example.com', 'children': [],
                     'criteria': [{'name': 'hostname', 'options': {'values': ['www.example.com']}}]},
                ]},
            ],
        }

        containers = papi.find_hostname_scoped_containers(rule_tree)

        assert len(containers) == 1
        assert containers[0]['name'] == 'Page Rules'

    def test_finds_container_whose_children_carry_pmuser_full_url_criteria(self, papi):
        rule_tree = {
            'name': 'default',
            'children': [
                {'name': 'Redirect Rules', 'children': [
                    {'name': 'redirect-1', 'children': [],
                     'criteria': [{'name': 'matchVariable',
                                   'options': {'variableName': 'PMUSER_FULL_URL',
                                               'variableValues': ['https://www.example.com/*']}}]},
                ]},
            ],
        }

        containers = papi.find_hostname_scoped_containers(rule_tree)

        assert len(containers) == 1
        assert containers[0]['name'] == 'Redirect Rules'

    def test_pmuser_origin_is_never_returned_even_though_its_children_qualify(self, papi):
        rule_tree = {
            'name': 'default',
            'children': [
                {'name': 'PMUSER_ORIGIN', 'children': [
                    {'name': 'www.example.com', 'children': [],
                     'criteria': [{'name': 'hostname', 'options': {'values': ['www.example.com']}}]},
                ]},
            ],
        }

        assert papi.find_hostname_scoped_containers(rule_tree) == []

    def test_pmuser_origin_subtree_is_not_recursed_into(self, papi):
        rule_tree = {
            'name': 'default',
            'children': [
                {'name': 'PMUSER_ORIGIN', 'children': [
                    {'name': 'Nested Page Rules', 'children': [
                        {'name': 'www.example.com', 'children': [],
                         'criteria': [{'name': 'hostname', 'options': {'values': ['www.example.com']}}]},
                    ]},
                ]},
            ],
        }

        assert papi.find_hostname_scoped_containers(rule_tree) == []

    def test_finds_container_nested_deeper_than_one_level(self, papi):
        rule_tree = {
            'name': 'default',
            'children': [
                {'name': 'Outer', 'children': [
                    {'name': 'Page Rules', 'children': [
                        {'name': 'www.example.com', 'children': [],
                         'criteria': [{'name': 'hostname', 'options': {'values': ['www.example.com']}}]},
                    ]},
                ]},
            ],
        }

        containers = papi.find_hostname_scoped_containers(rule_tree)

        assert len(containers) == 1
        assert containers[0]['name'] == 'Page Rules'

    def test_finds_multiple_independent_containers(self, papi):
        rule_tree = {
            'name': 'default',
            'children': [
                {'name': 'PMUSER_ORIGIN', 'children': [
                    {'name': 'www.example.com', 'children': [],
                     'criteria': [{'name': 'hostname', 'options': {'values': ['www.example.com']}}]},
                ]},
                {'name': 'Page Rules', 'children': [
                    {'name': 'www.example.com', 'children': [],
                     'criteria': [{'name': 'hostname', 'options': {'values': ['www.example.com']}}]},
                ]},
                {'name': 'Redirect Rules', 'children': [
                    {'name': 'redirect-1', 'children': [],
                     'criteria': [{'name': 'matchVariable',
                                   'options': {'variableName': 'PMUSER_FULL_URL',
                                               'variableValues': ['https://www.example.com/*']}}]},
                ]},
            ],
        }

        containers = papi.find_hostname_scoped_containers(rule_tree)

        assert sorted(container['name'] for container in containers) == ['Page Rules', 'Redirect Rules']

    def test_no_qualifying_containers_returns_empty_list(self, papi):
        rule_tree = {'name': 'default', 'children': [{'name': 'Shared Variables', 'children': []}]}

        assert papi.find_hostname_scoped_containers(rule_tree) == []

    def test_returns_empty_list_for_leaf_rule_with_no_children_key(self, papi):
        assert papi.find_hostname_scoped_containers({'name': 'default'}) == []


class TestLogHostnameRuleDetection:
    """Tests the --prune-hostname-rules on/off switch: for now it only detects and logs, it doesn't change anything yet."""

    def test_disabled_is_a_noop_and_never_touches_the_rule_tree(self, papi):
        rule_tree = {
            'name': 'default',
            'children': [
                {'name': 'Page Rules', 'children': [
                    {'name': 'www.example.com', 'children': [],
                     'criteria': [{'name': 'hostname', 'options': {'values': ['www.example.com']}}]},
                ]},
            ],
        }
        before = copy.deepcopy(rule_tree)

        papi.log_hostname_rule_detection('my-property', rule_tree, enabled=False)

        assert rule_tree == before

    def test_enabled_with_no_qualifying_containers_never_touches_the_rule_tree_and_logs(self, papi, caplog):
        rule_tree = {'name': 'default', 'children': [{'name': 'Shared Variables', 'children': []}]}
        before = copy.deepcopy(rule_tree)

        with caplog.at_level(logging.DEBUG, logger='utility_papi'):
            papi.log_hostname_rule_detection('my-property', rule_tree, enabled=True)

        assert rule_tree == before
        assert 'my-property' in caplog.text
        assert 'no qualifying containers' in caplog.text

    def test_enabled_with_qualifying_containers_never_touches_the_rule_tree_and_logs(self, papi, caplog):
        rule_tree = {
            'name': 'default',
            'children': [
                {'name': 'Page Rules', 'children': [
                    {'name': 'www.example.com', 'children': [],
                     'criteria': [{'name': 'hostname', 'options': {'values': ['www.example.com']}}]},
                    {'name': 'other.example.com', 'children': [],
                     'criteria': [{'name': 'hostname', 'options': {'values': ['other.example.com']}}]},
                ]},
            ],
        }
        before = copy.deepcopy(rule_tree)

        with caplog.at_level(logging.DEBUG, logger='utility_papi'):
            papi.log_hostname_rule_detection('my-property', rule_tree, enabled=True)

        assert rule_tree == before
        assert 'my-property' in caplog.text
        assert 'Page Rules' in caplog.text
        assert '2 hostname-scoped children' in caplog.text
