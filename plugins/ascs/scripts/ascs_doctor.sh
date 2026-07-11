#!/usr/bin/env bash
# Minimal, read-only launcher. -I ignores PYTHONPATH and user site packages so
# project-controlled Python startup hooks cannot affect the diagnostic.
set -u

SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P) || exit 2
exec python3 -I "${SCRIPT_DIR}/ascs_doctor.py"
