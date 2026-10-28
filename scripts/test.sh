#!/usr/bin/env bash
# Runs the unit tests inside the same OS and packages as the Lambda.
#   scripts/test.sh            unit tests (fake market data, offline)
#   scripts/test.sh -m live    tests that call the real Yahoo Finance API
set -euo pipefail
cd "$(dirname "$0")/.."

docker build --quiet --target test -t stock-eda:test image >/dev/null
# With no arguments the image's default runs: -m "not live"
docker run --rm stock-eda:test "$@"
