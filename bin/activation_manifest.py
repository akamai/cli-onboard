from __future__ import annotations

import csv
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

MANIFEST_FIELDS = ['property_name', 'property_id', 'version', 'activation_id', 'activation_started']


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
