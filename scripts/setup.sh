#!/usr/bin/env bash
# One-time setup (Ubuntu, amd64 or arm64): Prometheus, Alertmanager, node_exporter -> ./bin,
# Grafana via apt, Python deps -> ./.venv
set -euo pipefail
trap 'echo "!! setup failed at line $LINENO: $BASH_COMMAND"' ERR
cd "$(dirname "$0")/.."

case "$(uname -m)" in
  x86_64) ARCH=amd64 ;;
  aarch64|arm64) ARCH=arm64 ;;
  *) echo "unsupported arch $(uname -m)"; exit 1 ;;
esac
echo "== arch: $ARCH"

command -v curl >/dev/null || sudo apt-get install -y curl

fetch() {  # $1 = repo, $2 = fallback version
  local v d
  v=$(curl -fsSL "https://api.github.com/repos/prometheus/$1/releases/latest" 2>/dev/null \
      | grep -m1 '"tag_name"' | cut -d'"' -f4 || true)
  v=${v:-$2}
  d="$1-${v#v}.linux-$ARCH"
  echo "== downloading $d"
  curl -fL --progress-bar -o "bin/$d.tar.gz" "https://github.com/prometheus/$1/releases/download/$v/$d.tar.gz"
  tar xzf "bin/$d.tar.gz" -C bin && rm "bin/$d.tar.gz"
  ln -sfn "$d" "bin/$1"
}

mkdir -p bin
[ -x bin/prometheus/prometheus ]       || fetch prometheus v3.5.0
[ -x bin/alertmanager/alertmanager ]   || fetch alertmanager v0.28.1
[ -x bin/node_exporter/node_exporter ] || fetch node_exporter v1.9.1

if ! command -v grafana >/dev/null; then
  echo "== installing grafana (apt)"
  sudo apt-get update && sudo apt-get install -y apt-transport-https wget gpg
  sudo mkdir -p /etc/apt/keyrings
  wget -q -O - https://apt.grafana.com/gpg.key | gpg --dearmor | sudo tee /etc/apt/keyrings/grafana.gpg >/dev/null
  echo "deb [signed-by=/etc/apt/keyrings/grafana.gpg] https://apt.grafana.com stable main" | sudo tee /etc/apt/sources.list.d/grafana.list
  sudo apt-get update && sudo apt-get install -y grafana
fi

echo "== python venv"
[ -d .venv ] || /usr/bin/python3 -m venv .venv || { sudo apt-get install -y python3-venv && /usr/bin/python3 -m venv .venv; }
source .venv/bin/activate
pip install --upgrade pip
pip install torch --index-url https://download.pytorch.org/whl/cpu   # CPU-only wheel
pip install -r requirements.txt
echo "== setup done. Run: scripts/start.sh"
