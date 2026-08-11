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


class TestClassifyHostnameScopedChild:

    @staticmethod
    def _hostname_child(values):
        return {'name': 'child', 'children': [], 'criteria': [{'name': 'hostname', 'options': {'values': values}}]}

    def test_no_qualifying_criteria_is_no_match(self, papi):
        child = {'name': 'weird', 'children': [], 'criteria': []}

        assert papi._classify_hostname_scoped_child(child, {'www.example.com'}) == 'no_match'

    def test_single_value_full_match(self, papi):
        child = self._hostname_child(['www.example.com'])

        assert papi._classify_hostname_scoped_child(child, {'www.example.com'}) == 'full_match'

    def test_single_value_no_match(self, papi):
        child = self._hostname_child(['old.example.com'])

        assert papi._classify_hostname_scoped_child(child, {'www.example.com'}) == 'no_match'

    def test_multi_value_all_match_is_full_match(self, papi):
        child = self._hostname_child(['a.example.com', 'b.example.com'])

        assert papi._classify_hostname_scoped_child(child, {'a.example.com', 'b.example.com'}) == 'full_match'

    def test_multi_value_some_match_is_partial_match(self, papi):
        child = self._hostname_child(['a.example.com', 'b.example.com'])

        assert papi._classify_hostname_scoped_child(child, {'a.example.com'}) == 'partial_match'

    def test_match_is_case_insensitive(self, papi):
        child = self._hostname_child(['WWW.EXAMPLE.COM'])

        assert papi._classify_hostname_scoped_child(child, {'www.example.com'}) == 'full_match'


class TestPruneHostnameScopedChildren:

    @staticmethod
    def _hostname_child(name, values):
        return {
            'name': name, 'children': [],
            'criteria': [{'name': 'hostname', 'options': {'matchOperator': 'IS_ONE_OF', 'values': values}}],
        }

    @staticmethod
    def _full_url_child(name, values):
        return {
            'name': name, 'children': [],
            'criteria': [{'name': 'matchVariable',
                          'options': {'variableName': 'PMUSER_FULL_URL', 'matchOperator': 'IS_ONE_OF',
                                      'variableValues': values}}],
        }

    @staticmethod
    def _rule_tree(container_name, children):
        return {'name': 'default', 'children': [{'name': container_name, 'children': children}]}

    def test_no_qualifying_containers_is_a_noop(self, papi):
        rule_tree = {'name': 'default', 'children': [{'name': 'Shared Variables', 'children': []}]}
        before = copy.deepcopy(rule_tree)

        pruned = papi.prune_hostname_scoped_children('my-property', rule_tree, ['www.example.com'])

        assert pruned == []
        assert rule_tree == before

    def test_full_match_is_kept(self, papi):
        matched = self._hostname_child('www.example.com', ['www.example.com'])
        rule_tree = self._rule_tree('Page Rules', [matched])

        pruned = papi.prune_hostname_scoped_children('my-property', rule_tree, ['www.example.com'])

        assert rule_tree['children'][0]['children'] == [matched]
        assert pruned == []

    def test_no_match_is_pruned(self, papi):
        unmatched = self._hostname_child('old.example.com', ['old.example.com'])
        rule_tree = self._rule_tree('Page Rules', [unmatched])

        pruned = papi.prune_hostname_scoped_children('my-property', rule_tree, ['www.example.com'])

        assert rule_tree['children'][0]['children'] == []
        assert pruned == ['old.example.com']

    def test_all_children_pruned_warns_and_continues(self, papi, caplog):
        unmatched = self._hostname_child('old.example.com', ['old.example.com'])
        rule_tree = self._rule_tree('Page Rules', [unmatched])

        with caplog.at_level(logging.WARNING, logger='utility_papi'):
            pruned = papi.prune_hostname_scoped_children('my-property', rule_tree, ['www.example.com'])

        assert rule_tree['children'][0]['children'] == []
        assert pruned == ['old.example.com']
        assert 'my-property' in caplog.text
        assert "'Page Rules'" in caplog.text
        assert 'no children' in caplog.text

    def test_child_with_no_hostname_criteria_is_pruned(self, papi):
        # A container is only found when at least one child has qualifying criteria
        # (see find_hostname_scoped_containers) - pair the no-criteria child with a
        # matched sibling so the container is detected in the first place.
        matched = self._hostname_child('www.example.com', ['www.example.com'])
        no_criteria_child = {'name': 'weird', 'children': [], 'criteria': []}
        rule_tree = self._rule_tree('Page Rules', [matched, no_criteria_child])

        pruned = papi.prune_hostname_scoped_children('my-property', rule_tree, ['www.example.com'])

        assert rule_tree['children'][0]['children'] == [matched]
        assert pruned == []

    def test_partial_match_is_left_untouched_and_warns(self, papi, caplog):
        partial = self._hostname_child('multi', ['a.example.com', 'b.example.com'])
        rule_tree = self._rule_tree('Page Rules', [partial])

        with caplog.at_level(logging.WARNING, logger='utility_papi'):
            pruned = papi.prune_hostname_scoped_children('my-property', rule_tree, ['a.example.com'])

        assert rule_tree['children'][0]['children'] == [partial]
        assert pruned == []
        assert 'my-property' in caplog.text
        assert 'multi' in caplog.text
        # only the actually-mismatched value is named, not the whole criteria list
        assert 'b.example.com' in caplog.text
        assert 'a.example.com' not in caplog.text

    def test_match_is_case_insensitive(self, papi):
        matched = self._hostname_child('WWW.EXAMPLE.COM', ['WWW.EXAMPLE.COM'])
        rule_tree = self._rule_tree('Page Rules', [matched])

        pruned = papi.prune_hostname_scoped_children('my-property', rule_tree, ['www.example.com'])

        assert rule_tree['children'][0]['children'] == [matched]
        assert pruned == []

    def test_pmuser_origin_is_never_pruned_even_when_it_would_otherwise_qualify(self, papi):
        unmatched = self._hostname_child('old.example.com', ['old.example.com'])
        rule_tree = self._rule_tree('PMUSER_ORIGIN', [unmatched])
        before = copy.deepcopy(rule_tree)

        pruned = papi.prune_hostname_scoped_children('my-property', rule_tree, ['www.example.com'])

        assert pruned == []
        assert rule_tree == before

    def test_mixed_children_keep_prune_and_partial_together(self, papi):
        matched = self._hostname_child('www.example.com', ['www.example.com'])
        unmatched = self._hostname_child('old.example.com', ['old.example.com'])
        partial = self._hostname_child('multi', ['a.example.com', 'zzz.example.com'])
        rule_tree = self._rule_tree('Page Rules', [matched, unmatched, partial])

        pruned = papi.prune_hostname_scoped_children(
            'my-property', rule_tree, ['www.example.com', 'a.example.com'])

        assert rule_tree['children'][0]['children'] == [matched, partial]
        assert pruned == ['old.example.com']

    def test_pmuser_full_url_child_is_matched_via_extracted_hostname(self, papi):
        matched = self._full_url_child('redirect-1', ['https://www.example.com/path*'])
        rule_tree = self._rule_tree('Redirect Rules', [matched])

        pruned = papi.prune_hostname_scoped_children('my-property', rule_tree, ['www.example.com'])

        assert rule_tree['children'][0]['children'] == [matched]
        assert pruned == []

    def test_multiple_containers_are_each_pruned_independently(self, papi, caplog):
        page_rules_matched = self._hostname_child('www.example.com', ['www.example.com'])
        page_rules_unmatched = self._hostname_child('old.example.com', ['old.example.com'])
        redirect_unmatched = self._full_url_child('redirect-1', ['https://other.example.com/*'])
        rule_tree = {
            'name': 'default',
            'children': [
                {'name': 'Page Rules', 'children': [page_rules_matched, page_rules_unmatched]},
                {'name': 'Redirect Rules', 'children': [redirect_unmatched]},
            ],
        }

        with caplog.at_level(logging.WARNING, logger='utility_papi'):
            pruned = papi.prune_hostname_scoped_children('my-property', rule_tree, ['www.example.com'])

        assert rule_tree['children'][0]['children'] == [page_rules_matched]
        assert rule_tree['children'][1]['children'] == []
        assert sorted(pruned) == ['old.example.com', 'other.example.com']
        # the emptied-out container is named in the warning, the surviving one is not
        assert "'Redirect Rules'" in caplog.text
        assert "'Page Rules'" not in caplog.text


class TestPruneHostnameScopedChildrenAgainstRealRedirectRulesShape:
    """Grounded against account.mrcooper.com.json's actual Redirect Rules node
    (19 children under rules.children[6], all matchVariable/PMUSER_FULL_URL) -
    reproduced here as a literal fixture rather than read from that file, since
    it lives in a separate, unrelated repo outside cli-onboard.
    """

    @staticmethod
    def _full_url_child(name, values, extra_criteria=None):
        criteria = [{'name': 'matchVariable',
                     'options': {'variableName': 'PMUSER_FULL_URL', 'matchOperator': 'IS_ONE_OF',
                                 'variableValues': values}}]
        if extra_criteria:
            criteria.extend(extra_criteria)
        return {'name': name, 'children': [], 'criteriaMustSatisfy': 'all', 'criteria': criteria}

    def _real_redirect_rules_children(self):
        query_exclusion = {'name': 'matchVariable',
                            'options': {'variableName': 'PMUSER_QUERY', 'matchOperator': 'IS_NOT_ONE_OF',
                                        'variableValues': ['*connection=rkt*']}}
        return [
            self._full_url_child('careers-jobalert', ['https://careers.mrcooper.com/us/en/jobalert']),
            self._full_url_child('careers-careers', ['https://careers.mrcooper.com/us/en/']),
            self._full_url_child('careers-home', ['https://careers.mrcooper.com/us/en/home']),
            self._full_url_child('careers-xome-team', ['https://careers.mrcooper.com/us/en/xome-team']),
            self._full_url_child('careers-india-team', ['https://careers.mrcooper.com/us/en/india-team']),
            self._full_url_child('careers-search-results', ['https://careers.mrcooper.com/us/en/search-results']),
            self._full_url_child('careers-students-grads',
                                  ['https://careers.mrcooper.com/us/en/india-students-grads']),
            self._full_url_child('careers-jointalentcommunity',
                                  ['https://careers.mrcooper.com/us/en/jointalentcommunity']),
            self._full_url_child('careers-csr',
                                  ['https://careers.mrcooper.com/us/en/india-corporate-social-responsibility']),
            self._full_url_child('careers-benefits', ['https://careers.mrcooper.com/us/en/benefits']),
            self._full_url_child('connect-page', ['https://connect.mrcooper.com/']),
            self._full_url_child('www-correspondent', ['https://www.mrcooper.com/correspondent']),
            self._full_url_child('cooperclientconnect-uat', ['https://cooperclientconnect-uat.mrcooper.com/*']),
            self._full_url_child('cooperclientconnect', ['https://cooperclientconnect.mrcooper.com/*']),
            self._full_url_child(
                'account-forgot-password-prod',
                ['https://account.mrcooper.com/ed04d0f3-eba1-467f-91e7-52505132554c/oauth2/v2.0/'
                 'authorize?p=B2C_1A_PasswordReset*'],
                extra_criteria=[query_exclusion],
            ),
            self._full_url_child(
                'account-signin-prod',
                ['https://account.mrcooper.com/ed04d0f3-eba1-467f-91e7-52505132554c/oauth2/v2.0/'
                 'authorize?p=B2C_1A_SignUpOrSignIn*'],
            ),
            self._full_url_child(
                'accountuat-signin',
                ['https://accountuat.mrcooper.com/827b537c-bd22-4ffd-bd5b-f818e069de44/oauth2/v2.0/'
                 'authorize?p=B2C_1A_SignUpOrSignIn*'],
            ),
            self._full_url_child(
                'accountuat-forgot-password',
                ['https://accountuat.mrcooper.com/827b537c-bd22-4ffd-bd5b-f818e069de44/oauth2/v2.0/'
                 'authorize?p=B2C_1A_PasswordReset*'],
                extra_criteria=[query_exclusion],
            ),
            self._full_url_child('homepoint-redirect', ['*homepoint.mrcooper.com*']),
        ]

    def test_only_account_and_accountuat_children_survive(self, papi):
        children = self._real_redirect_rules_children()
        assert len(children) == 19
        rule_tree = {'name': 'default', 'children': [{'name': 'Redirect Rules', 'children': children}]}
        csv_hostnames = ['account.mrcooper.com', 'accountuat.mrcooper.com']

        pruned = papi.prune_hostname_scoped_children('account.mrcooper.com', rule_tree, csv_hostnames)

        survivors = rule_tree['children'][0]['children']
        assert [child['name'] for child in survivors] == [
            'account-forgot-password-prod', 'account-signin-prod',
            'accountuat-signin', 'accountuat-forgot-password',
        ]
        assert len(pruned) == 15
