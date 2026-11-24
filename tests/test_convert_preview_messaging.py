"""Checks that preview runs show a clear warning banner and label their report file so it's never mistaken for a real run."""
from __future__ import annotations

import logging

import utility


class TestConversionReportFilename:

    def test_preview_true_adds_prefix(self):
        path = utility.conversion_report_filename('output/acme', '20260810_1200_', preview=True)

        assert path == 'output/acme/PREVIEW_20260810_1200_conversion-result.xlsx'

    def test_preview_false_is_byte_for_byte_unchanged(self):
        path = utility.conversion_report_filename('output/acme', '20260810_1200_', preview=False)

        assert path == 'output/acme/20260810_1200_conversion-result.xlsx'


class TestLogPreviewBanner:

    def test_preview_true_logs_the_banner(self, caplog):
        with caplog.at_level(logging.WARNING, logger='utility'):
            utility.log_preview_banner(True)

        assert '--preview: nothing was created on Akamai' in caplog.text
        assert 'rerun without --preview to actually onboard' in caplog.text

    def test_preview_false_logs_nothing(self, caplog):
        with caplog.at_level(logging.WARNING, logger='utility'):
            utility.log_preview_banner(False)

        assert caplog.text == ''
