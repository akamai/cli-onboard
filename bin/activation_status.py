from __future__ import annotations

import csv
import logging
import time

from rich.live import Live
from rich.table import Table

logger = logging.getLogger(__name__)

DELIVERY_ACTIVE_STATUS = 'ACTIVE'
WAF_ACTIVE_STATUS = 'ACTIVATED'
DEFAULT_NETWORK = 'PRODUCTION'

# check_row_status's own synthetic failure statuses; wait_until_done treats
# either as terminal, same as ACTIVE/ACTIVATED -- retrying won't change them.
TERMINAL_ERROR_STATUSES = frozenset({'MISSING_CONTRACT_OR_GROUP', 'UNABLE_TO_GET_STATUS'})

# Shared cadence for the whole combined loop (a manifest can mix delivery and
# WAF rows). Matches poll.py's pollActivation, the closest precedent for one
# Live loop covering multiple rows.
DEFAULT_POLL_INTERVAL_SECONDS = 30


def load_manifest_rows(manifest_path: str) -> list[dict]:
    """Load a --no-wait manifest or minimal CSV; raises ValueError if activation_id column is missing."""
    with open(manifest_path, newline='') as f:
        reader = csv.DictReader(f)
        if 'activation_id' not in (reader.fieldnames or []):
            raise ValueError(f"{manifest_path}: missing required column 'activation_id'")
        return list(reader)


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


def _is_done(result: dict) -> bool:
    return result['is_active'] or result['status'] in TERMINAL_ERROR_STATUSES


def wait_until_done(wrapper_object, rows: list[dict], contract_id: str | None, group_id: str | None,
                     poll_interval_seconds: int = DEFAULT_POLL_INTERVAL_SECONDS) -> list[dict]:
    """
    Poll every row, refreshing a live table each cycle, until each is active
    or hits a terminal error (see TERMINAL_ERROR_STATUSES) -- mirrors
    poll.py's pollActivation loop shape, extended to one combined loop over a
    manifest that may mix delivery and WAF rows.
    """
    results = check_all(wrapper_object, rows, contract_id, group_id)
    with Live(build_status_table(results), refresh_per_second=1) as live:
        while not all(_is_done(r) for r in results):
            logger.info(f'Polling {poll_interval_seconds}s...')
            time.sleep(poll_interval_seconds)
            results = check_all(wrapper_object, rows, contract_id, group_id)
            live.update(build_status_table(results))
    return results


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
