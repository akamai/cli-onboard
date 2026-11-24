"""Console-script shim for `uv tool install -e .` / `pip install -e .`.

akamai-cli finds this plugin by looking for a file literally named
`bin/akamai-onboard.py` (see akamai/cli's `findExec`), so that file can't be
renamed or turned into a dotted-importable module without breaking the
`akamai onboard` command for existing users. This wrapper runs it as
`__main__` unmodified, purely so packaging tools have something importable
to point a [project.scripts] entry at.
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main() -> None:
    bin_dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(bin_dir))
    runpy.run_path(str(bin_dir / 'akamai-onboard.py'), run_name='__main__')
