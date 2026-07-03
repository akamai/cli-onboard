"""TC-C: `json_input_file_validator` (Local).

Correction vs. the original plan draft: template files are matched by *propertyName*
(falling back to hostname when no propertyName is given), one JSON file per CSV row —
not one JSON file per product as originally assumed. `csv_2_property_dict_convert`
sets each row's `templateName` from `propertyName`; `json_input_file_validator` then
looks for `<templateName>.json` in --directory.
"""
from __future__ import annotations


class FakeOnboardObject:
    """Minimal stand-in carrying only what json_input_file_validator reads/writes."""

    def __init__(self, csv_dict, source_directory):
        self.csv_dict = csv_dict
        self.source_directory = source_directory
        self.all_template_json_exists = True


def test_directory_has_all_required_templates_passes(util, template_dir_factory):
    directory = template_dir_factory(['example-prop', 'other-prop'])
    onboard_object = FakeOnboardObject(
        csv_dict=[
            {'hostname': 'www.example.com', 'templateName': 'example-prop'},
            {'hostname': 'www.other.com', 'templateName': 'other-prop'},
        ],
        source_directory=directory,
    )
    result = util.json_input_file_validator(onboard_object, prefix=None)
    assert result is True
    assert onboard_object.all_template_json_exists is True


def test_directory_missing_a_template_errors(util, template_dir_factory):
    directory = template_dir_factory(['example-prop'])  # 'other-prop' intentionally absent
    onboard_object = FakeOnboardObject(
        csv_dict=[
            {'hostname': 'www.example.com', 'templateName': 'example-prop'},
            {'hostname': 'www.other.com', 'templateName': 'other-prop'},
        ],
        source_directory=directory,
    )
    result = util.json_input_file_validator(onboard_object, prefix=None)
    assert result is False
    assert onboard_object.all_template_json_exists is False


def test_directory_path_not_found_errors(util, tmp_path):
    missing_dir = tmp_path / 'does-not-exist'
    onboard_object = FakeOnboardObject(
        csv_dict=[{'hostname': 'www.example.com', 'templateName': 'example-prop'}],
        source_directory=str(missing_dir),
    )
    result = util.json_input_file_validator(onboard_object, prefix=None)
    assert result is False


def test_falls_back_to_hostname_when_no_template_name(util, template_dir_factory):
    """Not in the original plan, but load_csv_input never sets `templateName` for a row
    with no propertyName until csv_2_property_dict_convert runs — json_input_file_validator
    has an explicit KeyError fallback to `hostname` for that case, worth covering directly.
    """
    directory = template_dir_factory(['www.example.com'])
    onboard_object = FakeOnboardObject(
        csv_dict=[{'hostname': 'www.example.com'}],  # no templateName key at all
        source_directory=directory,
    )
    result = util.json_input_file_validator(onboard_object, prefix=None)
    assert result is True
