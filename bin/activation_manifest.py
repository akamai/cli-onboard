from __future__ import annotations

import csv
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

MANIFEST_FIELDS = ['property_name', 'property_id', 'version', 'activation_id', 'activation_started']

NO_WAIT_SUBMITTED_STATUS = 'SUBMITTED'
ACTIVATION_ERROR_STATUS = 'ACTIVATION_ERROR'


def new_manifest_path(account_output: str) -> str:
    """
    Build a fresh, timestamped manifest file path for one CLI invocation.
    Call once per run and reuse the same path for every append_activation
    call in that run.
    """
    dt_string = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f'{account_output}/{dt_string}_activation-status.csv'


def append_activation(manifest_path: str, property_name: str, property_id: str | int | None,
                       version: str | int, activation_id: str) -> None:
    """
    Append one --no-wait activation record to the manifest CSV, writing the
    header row on first write. property_id must be left blank ('' or None)
    for WAF-only activations -- check-activation tells delivery rows from
    WAF rows apart by whether property_id is populated.
    """
    path = Path(manifest_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists()
    with path.open('a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow({
            'property_name': property_name,
            'property_id': property_id or '',
            'version': version,
            'activation_id': activation_id,
            'activation_started': datetime.now().isoformat(timespec='seconds'),
        })
    logger.info(f'Recorded activation {activation_id} for {property_name} in {manifest_path}')


def append_batch(manifest_path: str, activation_dicts: list[dict], version: str | int) -> None:
    """
    Append one manifest row per successfully-submitted property from a
    --no-wait batch_activate_and_poll()/pollActivation() result (each dict
    has propertyName/propertyId/activationId keys -- see poll.py). A property
    whose submission failed is logged and skipped, matching
    batch_activate_and_poll's existing "activationId == 0 means failed"
    convention.
    """
    for property_activation in activation_dicts:
        activation_id = property_activation['activationId']
        property_name = property_activation['propertyName']
        if activation_id == 0:
            logger.error(f'Unable to submit property {property_name} activation to production network')
            continue
        logger.info(f'Property {property_name} production activation submitted, activation id: {activation_id}')
        append_activation(manifest_path, property_name, property_activation['propertyId'], version, activation_id)


def stamp_batch_report_status(activation_dicts: list[dict]) -> None:
    """Mark --no-wait batch rows SUBMITTED/ACTIVATION_ERROR, matching pollActivation's {'STAGING','PRODUCTION'} shape."""
    for activation in activation_dicts:
        status = NO_WAIT_SUBMITTED_STATUS if activation['activationId'] != 0 else ACTIVATION_ERROR_STATUS
        activation['activationStatus'] = {'STAGING': '', 'PRODUCTION': status}
