#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
crapi_commit="73d309cc8f28bbdeed31dbb35f05dba8354de3c9"
lab_root="${TMPDIR:-/tmp}/sec-capsules-crapi-$crapi_commit"
source_dir="$lab_root/source"
compose_file="$source_dir/deploy/docker/docker-compose.yml"
minimal_file="$source_dir/deploy/docker/docker-compose.minimal.yml"
runs_dir="$repo_root/runs-crapi-ffuf-e2e"
project_name="sec-capsules-crapi-ffuf"

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

cd "$repo_root"
sec-capsules --runs-dir "$runs_dir" doctor ffuf --require
sec-capsules --runs-dir "$runs_dir" run ffuf \
  --target http://127.0.0.1:8888 \
  --scope benchmarks/scenarios/crapi-scope.yml \
  --profile safe \
  --arguments-json '{"match_status":[200,204,301,302,307,401,403,405],"requests_per_second":10}' \
  --approval-file benchmarks/scenarios/crapi-approval.yml \
  --execute \
  --budget 800 \
  --timeout 120

python - "$runs_dir" <<'PY'
import json
import pathlib
import sys

runs = pathlib.Path(sys.argv[1])
run_dirs = sorted(path for path in runs.iterdir() if path.is_dir())
if len(run_dirs) != 1:
    raise SystemExit(f"expected one FFUF run, found {len(run_dirs)}")
run = json.loads((run_dirs[0] / "run.json").read_text(encoding="utf-8"))
structured = json.loads((run_dirs[0] / "structured.json").read_text(encoding="utf-8"))
artifact = run_dirs[0] / "artifacts" / "ffuf.jsonl"
if run.get("status") != "succeeded":
    raise SystemExit(f"FFUF run did not succeed: {run.get('status')}")
if not artifact.is_file() or artifact.stat().st_size == 0:
    raise SystemExit("FFUF did not preserve a non-empty raw artifact")
diagnostics = structured.get("parse_diagnostics", {})
if diagnostics.get("input_records", 0) < 1:
    raise SystemExit("FFUF parser produced no input diagnostics")
if diagnostics.get("emitted_records") != len(structured.get("endpoints", [])):
    raise SystemExit("FFUF parser diagnostics do not match emitted endpoints")
PY
