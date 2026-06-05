#!/usr/bin/env bash
# =============================================================================
# web-agent-mcp セットアップスクリプト
# 使い方:
#   chmod +x setup.sh
#   ./setup.sh                 # Docker + 依存一式インストール
#   ./setup.sh --proxy-only    # プロキシ設定のみ更新
#   ./setup.sh --start         # サービス起動のみ
# =============================================================================
set -euo pipefail

# ──────────────────────────────────────────────────────────────────────────────
# カラー出力
# ──────────────────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ──────────────────────────────────────────────────────────────────────────────
# 引数解析
# ──────────────────────────────────────────────────────────────────────────────
MODE="install"
case "${1:-}" in
  --proxy-only) MODE="proxy" ;;
  --start)      MODE="start" ;;
  --help|-h)
    echo "Usage: $0 [--proxy-only | --start | --help]"
    exit 0 ;;
esac

# ──────────────────────────────────────────────────────────────────────────────
# 0. 動作環境確認
# ──────────────────────────────────────────────────────────────────────────────
check_wsl() {
  if ! grep -qi microsoft /proc/version 2>/dev/null; then
    warn "WSL2 ではない環境で実行しています（Linux 直接インストールも可能です）"
  fi
}

# ──────────────────────────────────────────────────────────────────────────────
# 1. プロキシ設定の収集と適用
# ──────────────────────────────────────────────────────────────────────────────
setup_proxy() {
  info "プロキシ設定を確認します"

  # 環境変数から既存のプロキシを検出
  DETECTED_PROXY="${http_proxy:-${HTTP_PROXY:-}}"
  if [ -n "$DETECTED_PROXY" ]; then
    info "検出されたプロキシ: $DETECTED_PROXY"
    read -r -p "このプロキシを使用しますか？ [Y/n]: " use_detected
    if [[ "${use_detected:-Y}" =~ ^[Yy]$ ]]; then
      PROXY_URL="$DETECTED_PROXY"
    else
      PROXY_URL=""
    fi
  else
    read -r -p "プロキシサーバーを使用しますか？ [y/N]: " use_proxy
    if [[ "${use_proxy:-N}" =~ ^[Yy]$ ]]; then
      read -r -p "プロキシURL (例: http://proxy.example.com:8080): " PROXY_URL
    else
      PROXY_URL=""
    fi
  fi

  NO_PROXY_DEFAULT="localhost,127.0.0.1,::1,searxng,web-agent-mcp,172.16.0.0/12,10.0.0.0/8,192.168.0.0/16"

  # .env ファイルを生成（既存があれば上書き確認）
  ENV_FILE="$SCRIPT_DIR/.env"
  if [ -f "$ENV_FILE" ]; then
    read -r -p ".env が既に存在します。上書きしますか？ [y/N]: " overwrite
    [[ "${overwrite:-N}" =~ ^[Yy]$ ]] || { info ".env はそのまま保持します"; return; }
  fi

  cat > "$ENV_FILE" << EOF
# web-agent-mcp 環境設定
# 生成日時: $(date '+%Y-%m-%d %H:%M:%S')

HTTP_PROXY=${PROXY_URL:-}
HTTPS_PROXY=${PROXY_URL:-}
NO_PROXY=${NO_PROXY_DEFAULT}

WEB_AGENT_PORT=8103
WEB_AGENT_MCP_PATH=/mcp/
WEB_AGENT_SEARXNG_BASE_URL=http://searxng:8080
WEB_AGENT_CACHE_DIR=/app/cache
WEB_AGENT_INDEX_DIR=/app/index
WEB_AGENT_ALLOWED_LOCAL_ROOTS=/app/docs
WEB_AGENT_ALLOW_PRIVATE_NETWORK=false
EOF

  info ".env を生成しました"

  # ~/.bashrc へのプロキシ永続化（プロキシがある場合のみ）
  if [ -n "$PROXY_URL" ]; then
    if ! grep -q "web-agent-mcp proxy" ~/.bashrc 2>/dev/null; then
      cat >> ~/.bashrc << EOF

# ===== web-agent-mcp proxy (added by setup.sh) =====
export HTTP_PROXY=${PROXY_URL}
export HTTPS_PROXY=${PROXY_URL}
export http_proxy=${PROXY_URL}
export https_proxy=${PROXY_URL}
export NO_PROXY=${NO_PROXY_DEFAULT}
export no_proxy=${NO_PROXY_DEFAULT}
EOF
      info "~/.bashrc にプロキシ設定を追加しました（次回ログイン時から有効）"
    fi

    # apt プロキシ設定
    PROXY_HOST=$(echo "$PROXY_URL" | sed 's|http://||;s|/.*||')
    if [ -n "$PROXY_HOST" ]; then
      sudo tee /etc/apt/apt.conf.d/99proxy > /dev/null << EOF
Acquire::http::Proxy "${PROXY_URL}";
Acquire::https::Proxy "${PROXY_URL}";
EOF
      info "apt プロキシを設定しました"
    fi

    # Docker デーモンのプロキシ設定（Docker インストール後に呼ぶ）
    setup_docker_proxy() {
      sudo mkdir -p /etc/systemd/system/docker.service.d
      sudo tee /etc/systemd/system/docker.service.d/proxy.conf > /dev/null << EOF
[Service]
Environment="HTTP_PROXY=${PROXY_URL}"
Environment="HTTPS_PROXY=${PROXY_URL}"
Environment="NO_PROXY=${NO_PROXY_DEFAULT}"
EOF
      sudo systemctl daemon-reload
      sudo systemctl restart docker 2>/dev/null || true
      info "Docker デーモンにプロキシを設定しました"
    }
  else
    setup_docker_proxy() { :; }
  fi
}

# ──────────────────────────────────────────────────────────────────────────────
# 2. Docker インストール（公式スクリプト経由）
# ──────────────────────────────────────────────────────────────────────────────
install_docker() {
  if command -v docker &> /dev/null; then
    info "Docker は既にインストールされています: $(docker --version)"
    return
  fi

  info "Docker をインストールします..."
  sudo apt-get update -qq
  sudo apt-get install -y -qq ca-certificates curl gnupg lsb-release

  # Docker 公式 GPG キーの追加
  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  sudo chmod a+r /etc/apt/keyrings/docker.gpg

  # リポジトリの追加
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
    https://download.docker.com/linux/ubuntu \
    $(lsb_release -cs) stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

  sudo apt-get update -qq
  sudo apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

  # docker グループへの追加
  sudo usermod -aG docker "$USER"
  info "Docker をインストールしました。グループ反映のため WSL を再起動してください:"
  info "  PowerShell: wsl --shutdown && wsl"

  # Docker デーモン起動
  sudo service docker start 2>/dev/null || sudo systemctl start docker 2>/dev/null || true
}

# ──────────────────────────────────────────────────────────────────────────────
# 3. uv インストール
# ──────────────────────────────────────────────────────────────────────────────
install_uv() {
  if command -v uv &> /dev/null; then
    info "uv は既にインストールされています: $(uv --version)"
    return
  fi
  info "uv をインストールします..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
  info "uv をインストールしました"
}

# ──────────────────────────────────────────────────────────────────────────────
# 4. データディレクトリ作成
# ──────────────────────────────────────────────────────────────────────────────
create_dirs() {
  info "データディレクトリを作成します..."
  mkdir -p "$SCRIPT_DIR/data/cache" \
           "$SCRIPT_DIR/data/index" \
           "$SCRIPT_DIR/data/docs"
  info "data/cache, data/index, data/docs を作成しました"
  info "ローカル PDF を読み込む場合は data/docs/ に配置してください"
}

# ──────────────────────────────────────────────────────────────────────────────
# 5. Docker イメージビルドとサービス起動
# ──────────────────────────────────────────────────────────────────────────────
start_services() {
  info "Docker イメージをビルドして起動します..."
  cd "$SCRIPT_DIR"

  docker compose build
  docker compose up -d

  info "起動完了。疎通確認中..."
  sleep 8

  # MCP endpoint の確認
  if curl -sf http://localhost:8103/mcp -X POST \
       -H "Content-Type: application/json" \
       -H "Accept: application/json, text/event-stream" \
       -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"test","version":"1"}}}' \
       | grep -q '"serverInfo"'; then
    info "✅ MCP エンドポイント疎通確認 OK: http://localhost:8103/mcp"
  else
    warn "MCP エンドポイントへの接続を確認できませんでした"
    warn "ログを確認: docker compose logs web-agent-mcp"
  fi
}

# ──────────────────────────────────────────────────────────────────────────────
# メイン処理
# ──────────────────────────────────────────────────────────────────────────────
main() {
  echo "======================================================"
  echo " web-agent-mcp セットアップ"
  echo "======================================================"
  echo ""

  check_wsl

  case "$MODE" in
    install)
      setup_proxy
      install_docker
      # Docker インストール後にプロキシを適用
      type setup_docker_proxy &>/dev/null && setup_docker_proxy
      install_uv
      create_dirs
      start_services
      ;;
    proxy)
      setup_proxy
      ;;
    start)
      create_dirs
      start_services
      ;;
  esac

  echo ""
  echo "======================================================"
  info "セットアップ完了！"
  echo ""
  echo "MCP エンドポイント: http://localhost:8103/mcp"
  echo ""
  echo "VS Code MCP 設定 (settings.json):"
  echo '  "mcp": {'
  echo '    "servers": {'
  echo '      "web-agent": {'
  echo '        "type": "http",'
  echo '        "url": "http://localhost:8103/mcp"'
  echo '      }'
  echo '    }'
  echo '  }'
  echo "======================================================"
}

main
