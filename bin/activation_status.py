from __future__ import annotations

import csv
import logging

from rich.table import Table

logger = logging.getLogger(__name__)

DELIVERY_ACTIVE_STATUS = 'ACTIVE'
WAF_ACTIVE_STATUS = 'ACTIVATED'
DEFAULT_NETWORK = 'PRODUCTION'


def load_manifest_rows(manifest_path: str) -> list[dict]:
    """Read a --no-wait manifest CSV (see activation_manifest.py) into row dicts."""
    with open(manifest_path, newline='') as f:
        return list(csv.DictReader(f))


def _result(name: str, activation_id: str, version, status: str, is_active: bool, network: str = DEFAULT_NETWORK) -> dict:
    return {'name': name, 'activation_id': activation_id, 'version': version,
            'network': network, 'status': status, 'is_active': is_active}


def check_row_status(wrapper_object, row: dict, contract_id: str | None, group_id: str | None) -> dict:
    """
    Query current status for one manifest row, exactly once (no polling).

    A row is a delivery activation if property_id is populated, a WAF
    activation otherwise -- matching how activation_manifest.append_activation
    writes rows. Returns a dict with the fields build_status_table and the
    caller's exit-code decision both need.
    """
    property_id = (row.get('property_id') or '').strip()
    activation_id = row['activation_id']
    version = row.get('version', '')
    name = row.get('property_name') or activation_id

    if property_id:
        if not contract_id or not group_id:
            logger.error(f'{name}: --contract and --group are required to check delivery activation {activation_id}')
            return _result(name, activation_id, version, 'MISSING_CONTRACT_OR_GROUP', False)

        response = wrapper_object.pollActivationStatus(contract_id, group_id, property_id, activation_id)
        if response.status_code != 200:
            logger.error(f'Unable to get activation status for {name} ({activation_id})')
            return _result(name, activation_id, version, 'UNABLE_TO_GET_STATUS', False)

        status = 'UNKNOWN'
        network = DEFAULT_NETWORK
        for item in response.json().get('activations', {}).get('items', []):
            if item.get('activationId') == activation_id:
                status = item.get('status', 'UNKNOWN')
                network = item.get('network', DEFAULT_NETWORK)
                break
        return _result(name, activation_id, version, status, status == DELIVERY_ACTIVE_STATUS, network)

    response = wrapper_object.pollWafActivationStatus(activation_id)
    if response.status_code != 200:
        logger.error(f'Unable to get WAF activation status for {name} ({activation_id})')
        return _result(name, activation_id, version, 'UNABLE_TO_GET_STATUS', False)

    body = response.json()
    status = body.get('status', 'UNKNOWN')
    network = body.get('network', DEFAULT_NETWORK)
    return _result(name, activation_id, version, status, status == WAF_ACTIVE_STATUS, network)


def check_all(wrapper_object, rows: list[dict], contract_id: str | None, group_id: str | None) -> list[dict]:
    """Check every row exactly once. No polling/sleep -- see check_row_status."""
    return [check_row_status(wrapper_object, row, contract_id, group_id) for row in rows]


def build_status_table(results: list[dict]) -> Table:
    table = Table()
    table.add_column('Name')
    table.add_column('Version')
    table.add_column('Activation Id')
    table.add_column('Network')
    table.add_column('Status')
    for r in results:
        style = 'green' if r['is_active'] else 'red'
        table.add_row(r['name'], str(r.get('version', '')), str(r['activation_id']), r['network'],
                      f"[{style}]{r['status']}[/{style}]")
    return table
