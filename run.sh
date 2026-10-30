#!/usr/bin/env bash
# GigRadar one-click runner. No install, no dependencies — just Python 3.11+.
#
#   ./run.sh              # fetch + score + store new postings
#   ./run.sh list -m 60   # show ranked postings scoring >= 60
#
# Any arguments are passed straight through to the CLI. With no args it runs
# the default "run" command.
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3.11+ is required but 'python3' was not found." >&2
    exit 1
fi

if [ "$#" -eq 0 ]; then
    exec python3 -m gigradar run
else
    exec python3 -m gigradar "$@"
fi
