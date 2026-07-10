#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
compose_file="$repo_root/examples/juice-shop-local/compose.yml"
runs_dir="$repo_root/runs-e2e"

cleanup() {
  docker compose -f "$compose_file" down --remove-orphans
}
trap cleanup EXIT

rm -rf "$runs_dir"
docker compose -f "$compose_file" up -d

for _ in $(seq 1 45); do
  if curl -fsS http://127.0.0.1:3000/ >/dev/null; then
    break
  fi
  sleep 2
done
curl -fsS http://127.0.0.1:3000/ >/dev/null

cd "$repo_root"
sec-capsules --runs-dir "$runs_dir" doctor --require
sec-capsules --runs-dir "$runs_dir" recipe run web-recon-local-lab \
  --target http://127.0.0.1:3000 \
  --scope examples/juice-shop-local/scope.yml \
  --execute \
  --budget 800 \
  --timeout 180
