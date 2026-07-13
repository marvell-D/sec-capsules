#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
crapi_commit="73d309cc8f28bbdeed31dbb35f05dba8354de3c9"
lab_root="${TMPDIR:-/tmp}/sec-capsules-crapi-$crapi_commit"
source_dir="$lab_root/source"
compose_file="$source_dir/deploy/docker/docker-compose.yml"
minimal_file="$source_dir/deploy/docker/docker-compose.minimal.yml"
runs_dir="$repo_root/runs-crapi-e2e"
project_name="sec-capsules-crapi"

cleanup() {
  if [[ -f "$compose_file" ]]; then
    LISTEN_IP=127.0.0.1 docker compose \
      --project-name "$project_name" \
      -f "$compose_file" \
      -f "$minimal_file" \
      down --volumes --remove-orphans
  fi
}
trap cleanup EXIT

rm -rf "$runs_dir"
mkdir -p "$lab_root"
if [[ ! -d "$source_dir/.git" ]]; then
  git clone --filter=blob:none --no-checkout https://github.com/OWASP/crAPI.git "$source_dir"
fi
git -C "$source_dir" fetch --depth 1 origin "$crapi_commit"
git -C "$source_dir" checkout --detach "$crapi_commit"

LISTEN_IP=127.0.0.1 docker compose \
  --project-name "$project_name" \
  -f "$compose_file" \
  -f "$minimal_file" \
  up -d --wait --wait-timeout 360

curl -kfsS https://127.0.0.1:8443/health >/dev/null

cd "$repo_root"
sec-capsules --runs-dir "$runs_dir" doctor nmap --require
sec-capsules --runs-dir "$runs_dir" run nmap \
  --target 127.0.0.1 \
  --scope examples/crapi-local/scope.yml \
  --profile service \
  --arguments-json '{"ports":[5500,8025,8443,8888],"packets_per_second":20}' \
  --approval-file examples/crapi-local/approval.yml \
  --execute \
  --budget 800 \
  --timeout 180

python - "$runs_dir" <<'PY'
import json
import pathlib
import sys

runs = pathlib.Path(sys.argv[1])
run_dirs = sorted(path for path in runs.iterdir() if path.is_dir())
if len(run_dirs) != 1:
    raise SystemExit(f"expected one Nmap run, found {len(run_dirs)}")
structured = json.loads((run_dirs[0] / "structured.json").read_text(encoding="utf-8"))
ports = {service.get("port") for service in structured.get("services", [])}
expected = {5500, 8025, 8443, 8888}
if not expected.issubset(ports):
    raise SystemExit(f"missing expected crAPI ports: {sorted(expected - ports)}")
PY
