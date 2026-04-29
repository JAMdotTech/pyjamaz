#!/bin/sh
set -eu

if [ -n "${JAM_FUZZ+x}" ]; then
    missing=""

    for var in JAM_FUZZ_SPEC JAM_FUZZ_DATA_PATH JAM_FUZZ_SOCK_PATH; do
        eval "value=\${$var:-}"
        if [ -z "$value" ]; then
            missing="${missing} ${var}"
        fi
    done

    if [ -n "$missing" ]; then
        echo "Missing required fuzz environment variable(s):${missing}" >&2
        exit 64
    fi

    case "${JAM_FUZZ_LOG_LEVEL:-}" in
        debug|trace)
            exec python pyjamaz/cli.pyc fuzzer target --socket-path "$JAM_FUZZ_SOCK_PATH" --verbose
            ;;
        *)
            exec python pyjamaz/cli.pyc fuzzer target --socket-path "$JAM_FUZZ_SOCK_PATH"
            ;;
    esac
fi

exec python pyjamaz/cli.pyc "$@"
