#!/usr/bin/env bash
set -euo pipefail

manifest="${1:?manifest path required}"
out="${2:-artifacts/evals}"
mode="${3:---dry-run}"

if [ "$mode" != "--execute" ] && [ "$mode" != "--dry-run" ]; then
  echo "usage: $0 MANIFEST [OUT_DIR] [--dry-run|--execute]" >&2
  exit 2
fi

case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*)
    echo "Refusing to run Docker/AFL++ from a native Windows shell." >&2
    echo "Use --dry-run here, or run --execute from a Linux host/container runner." >&2
    exit 2
    ;;
esac

docker build -f docker/evals/Dockerfile -t guardian-evals .

if [ "$mode" = "--dry-run" ]; then
  docker run --rm \
    -v "$PWD:/workspace" \
    -w /workspace \
    guardian-evals \
    python -m guardian.evals run --manifest "$manifest" --out "$out" --dry-run
  echo ""
  echo "Dry run only. Re-run with --execute on a stable Linux host to start AFL++."
  exit 0
fi

docker run --rm \
  --cpus="2" \
  --memory="4g" \
  -v "$PWD:/workspace" \
  -w /workspace \
  guardian-evals \
  python -m guardian.evals run --manifest "$manifest" --out "$out"
