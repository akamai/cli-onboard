from __future__ import annotations

import csv

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
