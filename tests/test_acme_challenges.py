from __future__ import annotations

from types import SimpleNamespace

import pytest
import utility_papi
import wrapper_api


class _FakeResponse:
    def __init__(self, status_code, body=None, text=''):
        self.status_code = status_code
        self._body = body
        self.text = text

    def json(self):
        return self._body


class _FakeSession:
    def __init__(self, response):
        self.response = response

    def post(self, url, data=None, headers=None):
        return self.response


class _FakeWrapper:
    def __init__(self, result):
        self.result = result

    def get_acme_tokens(self, chunk):
        return self.result


def _wrapper(response):
    return wrapper_api.apiCallsWrapper(_FakeSession(response), 'example.akamaiapis.net', None)


def _precheck(hostnames):
    return SimpleNamespace(unique_hostnames=hostnames, acme_challenges=[])


class TestGetAcmeTokens:
    def test_api_error_returns_none(self):
        resp = _FakeResponse(400, text='account-not-registered-for-certificate')
        assert _wrapper(resp).get_acme_tokens(['a.example.com']) is None

    def test_empty_items_returns_empty_list(self):
        resp = _FakeResponse(200, {'hostnames': {'items': []}})
        assert _wrapper(resp).get_acme_tokens(['a.example.com']) == []

    def test_items_returned(self):
        items = [{'cnameFrom': 'a.example.com'}]
        resp = _FakeResponse(200, {'hostnames': {'items': items}})
        assert _wrapper(resp).get_acme_tokens(['a.example.com']) == items


class TestGetAcmeChallenges:
    def test_api_error_exits_instead_of_typeerror(self):
        precheck = _precheck(['a.example.com'])
        with pytest.raises(SystemExit):
            utility_papi.papiFunctions().get_acme_challenges(None, precheck, _FakeWrapper(None))

    def test_empty_result_does_not_crash(self):
        precheck = _precheck(['a.example.com'])
        utility_papi.papiFunctions().get_acme_challenges(None, precheck, _FakeWrapper([]))
        assert precheck.acme_challenges == []

    def test_tokens_collected_across_chunks(self):
        precheck = _precheck([f'h{i}.example.com' for i in range(1500)])
        token = [{'cnameFrom': 'x'}]
        utility_papi.papiFunctions().get_acme_challenges(None, precheck, _FakeWrapper(token))
        assert len(precheck.acme_challenges) == 2
