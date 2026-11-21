#!/usr/bin/env bash
# Starts node_exporter, Alertmanager, Prometheus, Grafana in the background and the Streamlit app in the foreground.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

for f in bin/node_exporter/node_exporter bin/alertmanager/alertmanager bin/prometheus/prometheus .venv/bin/activate; do
  [ -e "$f" ] || { echo "missing $f -> run scripts/setup.sh first"; exit 1; }
done
command -v grafana >/dev/null || { echo "grafana not installed -> run scripts/setup.sh first"; exit 1; }

mkdir -p logs data
export A4_ROOT="$ROOT"
trap 'kill $(jobs -p) 2>/dev/null' EXIT

bin/node_exporter/node_exporter > logs/node_exporter.log 2>&1 &
bin/alertmanager/alertmanager --config.file=prometheus/alertmanager.yml \
  --storage.path=data/alertmanager --cluster.listen-address= > logs/alertmanager.log 2>&1 &
bin/prometheus/prometheus --config.file=prometheus/prometheus.yml \
  --storage.tsdb.path=data/prometheus > logs/prometheus.log 2>&1 &
GF_PATHS_PROVISIONING="$ROOT/grafana/provisioning" GF_PATHS_DATA="$ROOT/data/grafana" \
GF_PATHS_LOGS="$ROOT/logs" GF_PATHS_PLUGINS="$ROOT/data/grafana/plugins" \
  grafana server --homepath /usr/share/grafana > logs/grafana.log 2>&1 &

echo "node_exporter :9100 | prometheus :9090 | alertmanager :9093 | grafana :3000 (admin/admin) | metrics :18000"
echo "logs in ./logs"
source .venv/bin/activate
cd app && streamlit run ai_app.py --server.headless true
