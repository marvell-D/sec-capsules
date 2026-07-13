#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
mode=${1:-replay}
repeats=${2:-1}
model=${3:-}
output_dir="$repo_root/benchmark-reports/$mode"
scenario="$repo_root/benchmarks/scenarios/crapi-recon-replay.yml"
crapi_commit="73d309cc8f28bbdeed31dbb35f05dba8354de3c9"
lab_root="${TMPDIR:-/tmp}/sec-capsules-crapi-$crapi_commit"
source_dir="$lab_root/source"
compose_file="$source_dir/deploy/docker/docker-compose.yml"
minimal_file="$source_dir/deploy/docker/docker-compose.minimal.yml"
project_name="sec-capsules-agent-benchmark"

if [[ -z "${SILICONFLOW_API_KEY:-}" ]]; then
  echo "SILICONFLOW_API_KEY must be provided through the environment" >&2
  exit 2
fi
if [[ "$mode" != "replay" && "$mode" != "live" ]]; then
  echo "mode must be replay or live" >&2
  exit 2
fi

cleanup() {
  if [[ "$mode" == "live" && -f "$compose_file" ]]; then
    LISTEN_IP=127.0.0.1 docker compose \
      --project-name "$project_name" \
      -f "$compose_file" \
      -f "$minimal_file" \
      down --volumes --remove-orphans
  fi
}
trap cleanup EXIT

rm -rf "$output_dir"
mkdir -p "$output_dir"

if [[ "$mode" == "live" ]]; then
  command -v docker >/dev/null
  command -v nmap >/dev/null
  command -v ffuf >/dev/null
  mkdir -p "$lab_root"
  if [[ ! -d "$source_dir/.git" ]]; then
    git clone --filter=blob:none --no-checkout https://github.com/OWASP/crAPI.git "$source_dir"
  fi
  if ! git -C "$source_dir" cat-file -e "$crapi_commit^{commit}" 2>/dev/null; then
    git -C "$source_dir" fetch --depth 1 origin "$crapi_commit"
  fi
  git -C "$source_dir" checkout --detach "$crapi_commit"
  LISTEN_IP=127.0.0.1 docker compose \
    --project-name "$project_name" \
    -f "$compose_file" \
    -f "$minimal_file" \
    up -d --wait --wait-timeout 360
  curl -kfsS https://127.0.0.1:8443/health >/dev/null
fi

command=(
  python -m benchmarks.cli run
  --scenario "$scenario"
  --variant both
  --mode "$mode"
  --repeats "$repeats"
  --output-dir "$output_dir"
)
if [[ -n "$model" ]]; then
  command+=(--model "$model")
fi

cd "$repo_root"
"${command[@]}"
