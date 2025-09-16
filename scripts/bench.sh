#!/bin/bash

# Exit if any command fails
set -e

# Check args
if [ $# -ne 2 ]; then
    echo "Usage: $0 <bench_number> <test_suite>"
    echo "Example: $0 0000 fallback"
    exit 1
fi

BENCH_NUM=$1
TEST_SUITE=$2

TRACE_DIR="/Users/matthijsblaas/dev/jam-test-vectors/traces/${TEST_SUITE}"

# Run hyperfine benchmark
docker run -t -v ${TRACE_DIR}:/traces jamdottech/pyjamaz:bench-${BENCH_NUM} traces /traces