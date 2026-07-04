#!/usr/bin/env bash
# Every command run to set up and verify the GitHub Actions workflow
# (.github/workflows/build.yml) locally, using `act` + Podman instead of
# Docker Desktop. Run this yourself to reproduce the verification.
#
# This is a record of what was actually executed, including the two dead
# ends hit along the way — not a turnkey installer. Review before running,
# especially `podman machine start`, which starts a Podman VM.
set -euo pipefail

cd "$(dirname "$0")"

# --- 1. Confirm/install tooling ---------------------------------------------
# podman was already installed (brew list showed podman 5.8.2); act was not.
brew list --versions act podman || true
brew install act

# --- 2. Start the Podman VM (idempotent - no-op if already running) --------
podman machine list
podman machine start 2>&1 | grep -v 'already running' || true

# --- 3. Point the docker client / act at the Podman socket ------------------
# Ask podman directly instead of hardcoding the path - it can change between
# machine restarts.
export DOCKER_HOST="unix://$(podman machine inspect podman-machine-default \
  --format '{{.ConnectionInfo.PodmanSocket.Path}}')"
echo "DOCKER_HOST=$DOCKER_HOST"

# sanity check: podman responds on that socket like a docker daemon would
podman -D ps

# --- 4. Configure act's default runner image ---------------------------------
# (avoids an interactive "which image size" prompt on first run)
mkdir -p "$HOME/Library/Application Support/act"
cat > "$HOME/Library/Application Support/act/actrc" <<'EOF'
-P ubuntu-latest=catthehacker/ubuntu:act-latest
-P ubuntu-22.04=catthehacker/ubuntu:act-22.04
EOF
# NOTE: an earlier version of this file also had
#   --container-architecture linux/amd64
# forcing every job container to run under QEMU emulation (this Mac and the
# Podman VM are both arm64). That caused the "test" job's Install-uv step to
# crash with "exit code null" (a Rust/uv binary segfaulting under emulation)
# rather than any real workflow bug. Removed so containers run natively as
# arm64 instead. This means the local act run no longer perfectly matches
# GitHub's amd64 ubuntu-latest runners, but it's what let the actual
# workflow logic be verified instead of an emulation artifact.

# --- 5. List the jobs act discovers in the workflow --------------------------
act -l

# --- 6. Run the "test" job (uv sync + pytest), once per Python version ------
# --container-daemon-socket - : disables act's default behavior of bind-mounting
# the docker socket into the job container. Podman's VM-forwarded socket path
# is a macOS-host-only path (via gvproxy), not a real file inside the Podman
# VM's filesystem, so without this flag container creation fails with:
#   "mkdir .../podman-machine-default-api.sock: operation not supported"
#
# Only os:ubuntu-latest is exercised - act can only ever run Linux containers,
# so macos-latest/windows-latest legs can't be emulated locally at all (see
# notes at the bottom of this file).
#
# Run one Python version at a time, not all three via a single unfiltered
# `act` invocation. Running the matrix legs concurrently exposed two
# act-only/local issues that don't happen on real GitHub Actions runners
# (which give every matrix leg its own fully isolated VM):
#   - a race in act's shared local action-cache dir
#     (~/.cache/act/astral-sh-setup-uv@v5/) when multiple legs read/re-clone
#     it at the same time
#   - the local Podman VM's RAM being shared across all concurrently-running
#     containers, which starved out C-extension compiles
for py in 3.12 3.13 3.14; do
  echo "=== test job: python $py ==="
  act push -j test --matrix os:ubuntu-latest --matrix python-version:"$py" \
    --container-daemon-socket -
done

# --- 7. Run the "pip-install" job (pip install -r requirements.txt + --help) -
for py in 3.12 3.13 3.14; do
  echo "=== pip-install job: python $py ==="
  act push -j pip-install --matrix os:ubuntu-latest --matrix python-version:"$py" \
    --container-daemon-socket -
done

# --- Real bug found and fixed via this process -------------------------------
# The FIRST real run of the "test" job (after fixing the emulation issue in
# step 4) failed for real, on real workflow logic:
#
#   tests/conftest.py:26: in <module>
#       import utility
#   bin/utility.py:32: in <module>
#       logger = setup_logger()
#   bin/exceptions.py:47: in setup_logger
#       with open(origin_config) as f:
#   FileNotFoundError: [Errno 2] No such file or directory: 'config/logging.json'
#
# Root cause: tests/conftest.py deliberately os.chdir()s into a scratch temp
# dir before importing bin/utility.py, so setup_logger()'s side-effect
# folders (logs/, config/) don't get created in the repo root during test
# runs. setup_logger() (bin/exceptions.py) resolves its config file by
# checking, in order: /cli/..., ~/.akamai-cli/src/cli-onboard/config/..., and
# finally a plain relative 'config/logging.json'. On a real developer laptop
# that has previously run `akamai install`, ~/.akamai-cli/src/cli-onboard/
# already contains a real config, so that branch silently succeeds and masks
# the fact that the final relative-path fallback is broken in a scratch dir
# with no config/ subfolder at all. A genuinely clean machine — which is
# every fresh GitHub Actions runner — has no ~/.akamai-cli, so it falls
# through to the broken relative-path branch and fails exactly like this
# container did.
#
# This means the "test" job as originally written would have failed on
# real GitHub Actions the first time it ran, not just under act. It happened
# to pass every time it was run directly on this Mac only because of
# pre-existing ~/.akamai-cli state from earlier real `akamai install` runs.
#
# Fix applied in tests/conftest.py: after the chdir into the scratch dir but
# before importing utility, copy the repo's real config/logging.json into the
# scratch dir's config/ subfolder, so the relative-path fallback always finds
# a file regardless of the machine's install history.
#
# Reproduced with a disposable copy of the repo run through a raw podman
# container + uv (no act) to confirm the fix, independent of act/Podman
# quirks:
#   cp -r cli-onboard /tmp-or-elsewhere/repro-cli-onboard  # scratch copy
#   rm -rf repro-cli-onboard/.venv
#   podman run --rm -v repro-cli-onboard:/workspace catthehacker/ubuntu:act-latest bash -c '
#     cd /workspace
#     curl -LsSf https://astral.sh/uv/install.sh | sh
#     export PATH="$HOME/.local/bin:$PATH"
#     uv sync --all-groups
#     uv run pytest -v
#   '
# Before the conftest.py fix: FileNotFoundError as above.
# After the conftest.py fix: 42 passed, 1 skipped.
# Then re-ran the real `act push -j test ...` (step 6 above) against the
# actual repo and confirmed it now also passes end to end.

# --- Second finding: pandas had no Python 3.14 wheel -------------------------
# Running all 3 Python versions concurrently (an earlier, since-reverted
# version of this script did `act push -j test --matrix os:ubuntu-latest`
# with no python-version filter, launching all three at once) surfaced a
# second, real issue on the 3.14 leg specifically:
#   cc: fatal error: Killed signal terminated program cc1
#   ninja: build stopped: subcommand failed.
#   hint: `pandas` (v2.2.3) was included because `cli-onboard` (v2.5.2) depends on `pandas`
# pandas==2.2.3 (the pin at the time) predates Python 3.14's release, so it
# has no prebuilt wheel for cp314 and `uv sync`/`pip install` must compile it
# from source - a memory-heavy Cython/C build. Re-ran the 3.14 leg alone
# (not concurrently) and it still failed the same way even with the full
# Podman VM to itself, so this wasn't purely the concurrency issue above.
# Bumped the VM to 8GB (`podman machine set --memory 8192`) and the same leg
# passed, confirming it was a memory ceiling, not a hard incompatibility.
# Checked PyPI: pandas==2.3.3 is the first release with cp314 wheels.
# Bumped the pin to pandas==2.3.3 in pyproject.toml/requirements.txt/uv.lock,
# reverted the VM back to its original 2GB, and re-ran both jobs' 3.14 legs -
# both now install pandas from a wheel (no compile) and pass.

# --- Notes / limitations -----------------------------------------------------
# - act only emulates Linux (ubuntu-latest) runners. It cannot run the
#   macos-latest or windows-latest legs of the matrix locally — those still
#   need a real push/PR to GitHub Actions to verify.
# - Separately (not via act/Docker), the same commands the workflow runs were
#   also verified directly on this Mac (macOS/arm64) across Python 3.12, 3.13,
#   and 3.14 using `uv` and plain `venv`+`pip`:
#     uv sync --all-groups --python <3.12|3.13|3.14>
#     uv run --python <ver> pytest -q
#     python<ver> -m venv /tmp/pipcheck-<ver>
#     /tmp/pipcheck-<ver>/bin/pip install -r requirements.txt
#     /tmp/pipcheck-<ver>/bin/python bin/akamai-onboard.py --help
#   These runs pre-date the conftest.py fix and passed only because of this
#   Mac's pre-existing ~/.akamai-cli state — they did not by themselves prove
#   the workflow would pass on a clean CI runner. The act runs above (which
#   use a container with no ~/.akamai-cli) are what actually validate that.
