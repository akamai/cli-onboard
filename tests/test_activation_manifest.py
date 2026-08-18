from __future__ import annotations

import csv
from pathlib import Path

import activation_manifest


class TestNewManifestPath:
    def test_path_is_under_account_output_and_named_activation_status_csv(self):
        path = activation_manifest.new_manifest_path('output/some-account')

        assert path.startswith('output/some-account/')
        assert path.endswith('_activation-status.csv')


class TestAppendActivation:
    def test_first_write_creates_file_with_header_and_row(self, tmp_path):
        manifest_path = str(tmp_path / 'run' / 'activation-status.csv')

        activation_manifest.append_activation(manifest_path, 'example-prop', 'prp_123', 1, 'atv_456')

        with open(manifest_path, newline='') as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1
        row = rows[0]
        assert row['property_name'] == 'example-prop'
        assert row['property_id'] == 'prp_123'
        assert row['version'] == '1'
        assert row['activation_id'] == 'atv_456'
        assert row['activation_started']

    def test_second_write_appends_without_duplicating_header(self, tmp_path):
        manifest_path = str(tmp_path / 'activation-status.csv')

        activation_manifest.append_activation(manifest_path, 'example-prop', 'prp_123', 1, 'atv_456')
        activation_manifest.append_activation(manifest_path, 'WAF Security File', '', 3, 'act_789')

        with open(manifest_path, newline='') as f:
            lines = f.readlines()
            f.seek(0)
            rows = list(csv.DictReader(f))
        assert lines[0].strip() == ','.join(activation_manifest.MANIFEST_FIELDS)
        assert len(rows) == 2

    def test_waf_only_row_leaves_property_id_blank(self, tmp_path):
        manifest_path = str(tmp_path / 'activation-status.csv')

        activation_manifest.append_activation(manifest_path, 'WAF Security File', '', 3, 'act_789')

        with open(manifest_path, newline='') as f:
            row = next(csv.DictReader(f))
        assert row['property_id'] == ''
        assert row['property_name'] == 'WAF Security File'
        assert row['version'] == '3'
        assert row['activation_id'] == 'act_789'

    def test_none_property_id_also_left_blank(self, tmp_path):
        manifest_path = str(tmp_path / 'activation-status.csv')

        activation_manifest.append_activation(manifest_path, 'WAF Security File', None, 3, 'act_789')

        with open(manifest_path, newline='') as f:
            row = next(csv.DictReader(f))
        assert row['property_id'] == ''

    def test_creates_parent_directory_if_missing(self, tmp_path):
        manifest_path = str(tmp_path / 'nested' / 'dir' / 'activation-status.csv')

        activation_manifest.append_activation(manifest_path, 'example-prop', 'prp_123', 1, 'atv_456')

        assert (tmp_path / 'nested' / 'dir' / 'activation-status.csv').exists()


class TestAppendBatch:
    """Checks that a batch run logs one row per property that was successfully submitted, skipping any that failed."""

    def test_writes_one_row_per_property(self, tmp_path):
        manifest_path = str(tmp_path / 'activation-status.csv')
        activation_dicts = [
            {'propertyName': 'prop-a', 'propertyId': 'prp_1', 'activationId': 'atv_1'},
            {'propertyName': 'prop-b', 'propertyId': 'prp_2', 'activationId': 'atv_2'},
        ]

        activation_manifest.append_batch(manifest_path, activation_dicts, version=1)

        with open(manifest_path, newline='') as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 2
        assert rows[0] == {'property_name': 'prop-a', 'property_id': 'prp_1', 'version': '1',
                            'activation_id': 'atv_1', 'activation_started': rows[0]['activation_started']}
        assert rows[1]['property_name'] == 'prop-b'
        assert rows[1]['property_id'] == 'prp_2'

    def test_skips_properties_whose_submission_failed(self, tmp_path, caplog):
        manifest_path = str(tmp_path / 'activation-status.csv')
        activation_dicts = [
            {'propertyName': 'prop-a', 'propertyId': 'prp_1', 'activationId': 'atv_1'},
            {'propertyName': 'prop-failed', 'propertyId': 'prp_2', 'activationId': 0},
        ]

        activation_manifest.append_batch(manifest_path, activation_dicts, version=1)

        with open(manifest_path, newline='') as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1
        assert rows[0]['property_name'] == 'prop-a'
        assert 'prop-failed' in caplog.text

    def test_all_submissions_failed_writes_no_manifest_file(self, tmp_path):
        manifest_path = str(tmp_path / 'activation-status.csv')
        activation_dicts = [{'propertyName': 'prop-a', 'propertyId': 'prp_1', 'activationId': 0}]

        activation_manifest.append_batch(manifest_path, activation_dicts, version=1)

        assert not Path(manifest_path).exists()

    def test_mixed_waf_and_non_waf_rows_across_two_batches(self, tmp_path):
        """Checks that regular property rows and a later WAF row can both be appended to the same log file."""
        manifest_path = str(tmp_path / 'activation-status.csv')
        delivery_batch = [
            {'propertyName': 'prop-a', 'propertyId': 'prp_1', 'activationId': 'atv_1'},
            {'propertyName': 'prop-b', 'propertyId': 'prp_2', 'activationId': 'atv_2'},
        ]

        activation_manifest.append_batch(manifest_path, delivery_batch, version=1)
        activation_manifest.append_activation(manifest_path, 'WAF Security File', '', 3, 'act_1')

        with open(manifest_path, newline='') as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 3
        assert [r['property_id'] for r in rows] == ['prp_1', 'prp_2', '']


class TestStampBatchReportStatus:
    """Checks that properties run without waiting still get a clear status label instead of a blank one."""

    def test_submitted_property_gets_submitted_status(self):
        activation_dicts = [{'propertyName': 'prop-a', 'propertyId': 'prp_1', 'activationId': 'atv_1'}]

        activation_manifest.stamp_batch_report_status(activation_dicts)

        assert activation_dicts[0]['activationStatus'] == {'STAGING': '', 'PRODUCTION': 'SUBMITTED'}

    def test_failed_submission_gets_activation_error_status(self):
        activation_dicts = [{'propertyName': 'prop-a', 'propertyId': 'prp_1', 'activationId': 0}]

        activation_manifest.stamp_batch_report_status(activation_dicts)

        assert activation_dicts[0]['activationStatus'] == {'STAGING': '', 'PRODUCTION': 'ACTIVATION_ERROR'}

    def test_mixed_batch_stamps_each_independently(self):
        activation_dicts = [
            {'propertyName': 'prop-a', 'propertyId': 'prp_1', 'activationId': 'atv_1'},
            {'propertyName': 'prop-b', 'propertyId': 'prp_2', 'activationId': 0},
        ]

        activation_manifest.stamp_batch_report_status(activation_dicts)

        assert activation_dicts[0]['activationStatus']['PRODUCTION'] == 'SUBMITTED'
        assert activation_dicts[1]['activationStatus']['PRODUCTION'] == 'ACTIVATION_ERROR'

    def test_status_shape_matches_pollactivation_dict_shape(self):
        """Checks that the status has both a staging and production value, matching what other reports expect."""
        activation_dicts = [{'propertyName': 'prop-a', 'propertyId': 'prp_1', 'activationId': 'atv_1'}]

        activation_manifest.stamp_batch_report_status(activation_dicts)

        assert set(activation_dicts[0]['activationStatus'].keys()) == {'STAGING', 'PRODUCTION'}

    def test_empty_batch_is_a_no_op(self):
        activation_manifest.stamp_batch_report_status([])  # must not raise
