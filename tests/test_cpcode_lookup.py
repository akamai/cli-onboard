from __future__ import annotations

import logging

import pytest


class _FakeResponse:
    def __init__(self, *, ok, status_code, json_body=None, json_error=None, text=''):
        self.ok = ok
        self.status_code = status_code
        self._json_body = json_body
        self._json_error = json_error
        self.text = text

    def json(self):
        if self._json_error is not None:
            raise self._json_error
        return self._json_body


class _FakeWrapper:
    """Records the cpcode_name it was called with so tests can confirm
    sanitization happened before the (faked) PAPI call, without hitting a
    real API.
    """

    def __init__(self, response):
        self.response = response
        self.received_cpcode_name = None

    def createCpcode(self, contract_id, group_id, product_id, cpcode_name):
        self.received_cpcode_name = cpcode_name
        return self.response

    def searchCpcode(self, contract_id, group_id, product_id, cpcode_name):
        self.received_cpcode_name = cpcode_name
        return self.response


def _onboard_object(click_args_factory, config_stub):
    import onboard_convert
    return onboard_convert.onboard(config_stub, click_args_factory())


def test_create_new_cpcode_sanitizes_special_characters(papi, click_args_factory, config_stub):
    response = _FakeResponse(ok=True, status_code=201, json_body={'cpcodeLink': '/papi/v1/cpcodes/cpc_12345?x'})
    wrapper = _FakeWrapper(response)
    onboard_object = _onboard_object(click_args_factory, config_stub)

    new_cpcode = papi.create_new_cpcode(onboard_object, wrapper, 'Site "A", B\'s_#1%^\\', 'ctr_1', 'grp_1', 'prd_1')

    assert wrapper.received_cpcode_name == 'Site .A.. B.s..1...'
    assert new_cpcode == 12345
    assert onboard_object.onboard_default_cpcode == 12345


def test_create_new_cpcode_survives_non_json_response(papi, click_args_factory, config_stub):
    response = _FakeResponse(ok=False, status_code=500, json_error=ValueError('not json'), text='<html>error</html>')
    wrapper = _FakeWrapper(response)
    onboard_object = _onboard_object(click_args_factory, config_stub)

    with pytest.raises(SystemExit):
        papi.create_new_cpcode(onboard_object, wrapper, 'my-cpcode', 'ctr_1', 'grp_1', 'prd_1')


def test_search_for_cpcode_sanitizes_special_characters(papi, click_args_factory, config_stub):
    response = _FakeResponse(ok=True, status_code=200, json_body={
        'cpcodes': [{'cpcodeName': 'Site .A.. B.s..1...', 'cpcodeId': 67890}],
    })
    wrapper = _FakeWrapper(response)
    onboard_object = _onboard_object(click_args_factory, config_stub)

    existing_cpcode = papi.search_for_cpcode(onboard_object, wrapper, 'Site "A", B\'s_#1%^\\', 'ctr_1', 'grp_1', 'prd_1')

    assert wrapper.received_cpcode_name == 'Site .A.. B.s..1...'
    assert existing_cpcode == 67890
    assert onboard_object.onboard_default_cpcode == 67890


def test_search_for_cpcode_survives_non_json_response(papi, click_args_factory, config_stub):
    response = _FakeResponse(ok=False, status_code=500, json_error=ValueError('not json'), text='<html>error</html>')
    wrapper = _FakeWrapper(response)
    onboard_object = _onboard_object(click_args_factory, config_stub)

    with pytest.raises(SystemExit):
        papi.search_for_cpcode(onboard_object, wrapper, 'my-cpcode', 'ctr_1', 'grp_1', 'prd_1')


def test_create_new_cpcode_logs_path_when_given(papi, click_args_factory, config_stub, caplog):
    response = _FakeResponse(ok=True, status_code=201, json_body={'cpcodeLink': '/papi/v1/cpcodes/cpc_12345?x'})
    wrapper = _FakeWrapper(response)
    onboard_object = _onboard_object(click_args_factory, config_stub)

    with caplog.at_level(logging.INFO):
        papi.create_new_cpcode(onboard_object, wrapper, 'my-cpcode', 'ctr_1', 'grp_1', 'prd_1', path='/some/path')

    assert 'New cpcode: 12345' in caplog.text
    assert '/some/path' in caplog.text
    assert 'my-cpcode' not in caplog.text


def test_create_new_cpcode_logs_cpcode_name_when_no_path(papi, click_args_factory, config_stub, caplog):
    response = _FakeResponse(ok=True, status_code=200, json_body={'cpcodeLink': '/papi/v1/cpcodes/cpc_12345?x'})
    wrapper = _FakeWrapper(response)
    onboard_object = _onboard_object(click_args_factory, config_stub)

    with caplog.at_level(logging.INFO):
        papi.create_new_cpcode(onboard_object, wrapper, 'my-cpcode', 'ctr_1', 'grp_1', 'prd_1')

    assert 'Reused existing cpcode: 12345' in caplog.text
    assert 'my-cpcode' in caplog.text


def test_search_for_cpcode_logs_path_when_given(papi, click_args_factory, config_stub, caplog):
    response = _FakeResponse(ok=True, status_code=200, json_body={
        'cpcodes': [{'cpcodeName': 'my-cpcode', 'cpcodeId': 67890}],
    })
    wrapper = _FakeWrapper(response)
    onboard_object = _onboard_object(click_args_factory, config_stub)

    with caplog.at_level(logging.INFO):
        papi.search_for_cpcode(onboard_object, wrapper, 'my-cpcode', 'ctr_1', 'grp_1', 'prd_1', path='/some/path')

    assert 'Existing cpcode found: 67890 for path: /some/path' in caplog.text


def test_search_for_cpcode_logs_without_path(papi, click_args_factory, config_stub, caplog):
    response = _FakeResponse(ok=True, status_code=200, json_body={
        'cpcodes': [{'cpcodeName': 'my-cpcode', 'cpcodeId': 67890}],
    })
    wrapper = _FakeWrapper(response)
    onboard_object = _onboard_object(click_args_factory, config_stub)

    with caplog.at_level(logging.INFO):
        papi.search_for_cpcode(onboard_object, wrapper, 'my-cpcode', 'ctr_1', 'grp_1', 'prd_1')

    assert 'Existing cpcode found: 67890' in caplog.text
    assert 'for path' not in caplog.text
