# web-agent-mcp

WSL2 + Docker 上で動作する **Web 調査用 MCP サーバー**。  
SearXNG による全文 Web 検索・HTML/PDF 本文抽出・SQLite FTS5 全文インデックスを  
**Streamable HTTP MCP**（MCP 仕様 2025-06-18 準拠）として提供します。

```
Windows MCP Client (VS Code / Claude / Codex)
  → http://localhost:8103/mcp   ← Streamable HTTP (POST only, stateless)
  → WSL2 Docker: web-agent-mcp コンテナ
  → Docker 内部ネットワーク
  → searxng コンテナ:8080 → インターネット
```

### トランスポートの仕様

| 項目 | 内容 |
|------|------|
| プロトコル | Streamable HTTP（MCP 2025-06-18 仕様） |
| エンドポイント | `POST http://localhost:8103/mcp` |
| レスポンス形式 | `application/json`（stateless モード） |
| Accept ヘッダー | `application/json` のみで接続可能 |
| GET `/mcp` | `405 Method Not Allowed`（stateless のため SSE 通知ストリームなし） |
| セッション | なし（stateless）— リクエストごとに独立処理 |

## 提供ツール一覧

| ツール名 | 説明 |
|---------|------|
| `web_search` | SearXNG で Web 検索。`site:` 絞り込み対応 |
| `web_read` | URL または `/app/docs` 配下のローカル PDF を読んで Markdown 抽出。JS テンプレート変数 (`${...}`) を検知すると Playwright で自動再取得。`page` / `page_size` で大容量コンテンツをページ分割取得可能 |
| `web_read_many` | 複数 URL を並列フェッチ |
| `local_document_search` | 既読文書を SQLite FTS5 で全文検索 |
| `cache_status` | キャッシュ・インデックスの統計情報 |

### `web_read` の主要パラメータ

| パラメータ | 型 | デフォルト | 説明 |
|-----------|-----|-----------|------|
| `url` | string | — | 取得する URL |
| `use_browser` | bool | `false` | `true` にすると Playwright Chromium で JS をレンダリングしてから抽出。JS テンプレート変数 (`${...}`) が検出された場合は自動的に `true` へ昇格 |
| `page` | int | `0` | ページ番号（0 始まり）。コンテンツが 12000 字超の場合は自動でページネーション |
| `page_size` | int | `null` | 1 ページあたりの文字数（未指定時: 12000 字超で自動適用）。`metadata.total_pages` / `metadata.total_chars` で全体サイズを確認できる |
| `force_refresh` | bool | `false` | キャッシュを無視して再取得 |
| `return_chunks` | bool | `false` | チャンク配列を含める（デフォルト除外でレスポンスを軽量化） |
| `return_links` | bool | `false` | リンク一覧を含める（デフォルト除外） |

---

## インストール手順

### ① WSL2 の作成（Windows 側・管理者 PowerShell）

```powershell
# WSL2 と Ubuntu をインストール
wsl --install

# インストール後 PC を再起動し、Ubuntu を起動してユーザー名・パスワードを設定
```

> Ubuntu が開いたらウィンドウをそのまま使って以下の手順を続けてください。

---

### ② リポジトリのクローン

WSL2（Ubuntu）のターミナルで実行します。

```bash
# ホームディレクトリに移動
cd ~

# リポジトリをクローン
git clone https://github.com/YOUR_USERNAME/web-agent-mcp.git
cd web-agent-mcp
```

> `YOUR_USERNAME` は実際の GitHub ユーザー名に置き換えてください。

---

### ③ セットアップスクリプトの実行（ワンクリックインストール）

```bash
chmod +x setup.sh
./setup.sh
```

スクリプトが対話式で以下を自動実行します：

1. **プロキシ設定** — 既存環境変数を自動検出し `.env` を生成
2. **Docker CE インストール** — 公式リポジトリから最新版
3. **uv インストール** — Python パッケージ管理ツール
4. **データディレクトリ作成** — `data/cache`, `data/index`, `data/docs`
5. **Docker イメージビルド & サービス起動**
6. **疎通確認** — `http://localhost:8103/mcp` への接続テスト

#### スクリプトのオプション

```bash
./setup.sh               # フルインストール（初回）
./setup.sh --proxy-only  # .env のプロキシ設定のみ更新
./setup.sh --start       # サービス起動のみ（インストール済みの場合）
```

---

### ④ WSL の再起動（docker グループ反映）

Docker インストール後、`docker` コマンドを `sudo` なしで使えるようにするため  
一度 WSL を再起動します。

```powershell
# Windows PowerShell で実行
wsl --shutdown
wsl
```

WSL が再起動したら以下で確認します：

```bash
docker run hello-world
# "Hello from Docker!" が表示されれば OK
```

---

### ⑤ サービスの起動確認

```bash
cd ~/web-agent-mcp
docker compose ps
```

```
NAME                STATUS
web-agent-mcp       Up
web-agent-searxng   Up
```

両コンテナが `Up` であることを確認してください。

---

### ⑥ ローカル PDF の配置（任意）

`data/docs/` に PDF を配置すると `web_read` の `local_path` パラメータで読み込めます。

```bash
cp /path/to/your.pdf ~/web-agent-mcp/data/docs/
```

コンテナ内では `/app/docs/your.pdf` としてアクセスできます。

---

## VS Code での MCP サーバー設定

### settings.json に追記

```json
{
  "mcp": {
    "servers": {
      "web-agent": {
        "type": "http",
        "url": "http://localhost:8103/mcp"
      }
    }
  }
}
```

> **`"type": "http"`** が Streamable HTTP トランスポートを指定します。  


**設定場所**: `Ctrl+Shift+P` → `Preferences: Open User Settings (JSON)`

### 動作確認

VS Code のコマンドパレット（`Ctrl+Shift+P`）で `MCP: List Tools` を実行し、  
以下の 5 ツールが表示されれば設定完了です：

- `web_search`
- `web_read`
- `web_read_many`
- `local_document_search`
- `cache_status`

---

## ネットワーク設定（社内プロキシ・複雑な環境向け）

### 基本構成の思想

```
社内プロキシ環境
  │
  ├─ Windows 側: .env に HTTP_PROXY を設定
  │
  ├─ WSL2 シェル: ~/.bashrc に export HTTP_PROXY=... を追記
  │
  ├─ apt: /etc/apt/apt.conf.d/99proxy に設定（sudo は環境変数をリセットするため必須）
  │
  ├─ Docker デーモン: /etc/systemd/system/docker.service.d/proxy.conf
  │    → setup.sh が自動生成
  │
  └─ Docker コンテナ: docker-compose.yml の build.args + environment
       → ${HTTP_PROXY:-} パターンで未設定時は空文字（プロキシなし環境でも動作）
```

### .env でのプロキシ制御

`docker compose` は同ディレクトリの `.env` を自動読み込みします。

```bash
# .env（.gitignore に含まれているため GitHub にはアップロードされません）
HTTP_PROXY=http://proxy.example.com:8080
HTTPS_PROXY=http://proxy.example.com:8080
NO_PROXY=localhost,127.0.0.1,::1,searxng,web-agent-mcp,172.16.0.0/12,10.0.0.0/8,192.168.0.0/16
```

### Docker 内部通信のプロキシ回避（重要）

コンテナ同士の通信（`web-agent-mcp → searxng:8080`）がプロキシ経由になると失敗します。  
`NO_PROXY` / `no_proxy` にコンテナ名を必ず列挙してください。

`docker-compose.yml` には以下のパターンで設定済みです：

```yaml
environment:
  - NO_PROXY=localhost,127.0.0.1,::1,searxng,web-agent-mcp
  - no_proxy=localhost,127.0.0.1,::1,searxng,web-agent-mcp
```

> **ポイント**: `${NO_PROXY:-}` のようにホスト変数を使うと、ホスト側の `NO_PROXY` が  
> 短い場合に不足します。コンテナ名は `docker-compose.yml` に直書きすることを推奨します。

### MTU 設定（WSL2 必須）

WSL2 の Hyper-V 仮想スイッチは MTU が 1350 前後になることがあります。  
設定しないと大きなパケットが断片化し、通信エラーが発生します。

```yaml
# docker-compose.yml に設定済み
networks:
  default:
    driver_opts:
      com.docker.network.driver.mtu: "1350"
```

### LAN の別 PC からアクセスする場合（任意）

通常は不要です。チームメンバーが別 PC から使う場合のみ設定します。

#### 1. WSL2 の IP を確認

```bash
hostname -I | awk '{print $1}'
# 例: 172.23.144.1
```

#### 2. Windows の LAN IP を確認

```powershell
Get-NetIPAddress -AddressFamily IPv4 | Format-Table -AutoSize IPAddress,InterfaceAlias
# 192.168.x.x のものが LAN IP
```

#### 3. portproxy と Firewall を設定（管理者 PowerShell）

```powershell
$wsl_ip = (wsl hostname -I).Trim().Split(' ')[0]

# WSL2 → Windows LAN に転送
netsh interface portproxy add v4tov4 `
  listenaddress=0.0.0.0 listenport=8103 `
  connectaddress=$wsl_ip connectport=8103

# Firewall でポートを開く
netsh advfirewall firewall add rule `
  name="web-agent-mcp-8103" dir=in action=allow `
  enable=yes profile=any protocol=TCP localport=8103
```

#### 4. 別 PC の MCP 設定

```json
{
  "mcp": {
    "servers": {
      "web-agent": {
        "type": "http",
        "url": "http://<ホストPCのLAN IP>:8103/mcp"
      }
    }
  }
}
```

> WSL2 再起動で IP が変わった場合は portproxy を作り直してください。

---

## 日常的な操作

```bash
# 起動
cd ~/web-agent-mcp && docker compose up -d

# 停止
docker compose down

# ログ確認
docker compose logs -f web-agent-mcp

# 再ビルド（コード変更後）
docker compose build web-agent-mcp
docker compose up -d --force-recreate web-agent-mcp

# コンテナの状態確認
docker compose ps
```

---

## トラブルシューティング

### `"Client must accept text/event-stream"` エラーが出る

旧バージョンの問題です。現バージョンでは以下の変更により解決しています：

| 変更点 | 旧動作 | 新動作 |
|--------|--------|--------|
| GET `/mcp` | `406 Not Acceptable` | `405 Method Not Allowed`（仕様準拠） |
| POST の Accept 要件 | `application/json` + `text/event-stream` 両方必須 | `application/json` のみで OK |
| レスポンス形式 | SSE ストリーム（`text/event-stream`） | JSON（`application/json`） |

```bash
# 動作確認（Accept: application/json のみで 200 が返ることを確認）
curl -s -X POST http://localhost:8103/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' \
  | python3 -m json.tool
```

まだ発生する場合は Docker イメージを再ビルドしてください：
```bash
docker compose up -d --build
```

### MCP に繋がらない

```bash
# WSL2 側で確認
docker compose ps
docker compose logs web-agent-mcp

# Windows PowerShell 側で確認
curl.exe --noproxy "*" http://localhost:8103/mcp
```

確認ポイント：
- `web-agent-mcp` コンテナが `Up` になっているか
- `ports: "8103:8103"` が設定されているか
- Windows 側のプロキシが `localhost` をバイパスしているか

### MCP → SearXNG に繋がらない

```bash
docker exec -it web-agent-mcp sh
curl "http://searxng:8080/search?q=test&format=json"
```

確認ポイント：
- サービス名が `searxng` になっているか
- 同じ Docker ネットワーク (`web-agent-network`) にいるか
- `NO_PROXY` に `searxng` が含まれているか

### SearXNG が検索できない（外部への接続失敗）

```bash
docker compose logs searxng
```

確認ポイント：
- SearXNG コンテナの `HTTP_PROXY` / `HTTPS_PROXY` が正しいか
- `searxng/settings.yml` の `formats` に `json` が含まれているか

---

## ディレクトリ構成

```
web-agent-mcp/
  setup.sh                ← ワンクリックセットアップスクリプト
  docker-compose.yml
  .env.example            ← .env のテンプレート（.git に含まれる）
  .env                    ← 実際の設定（.gitignore で除外）
  pyproject.toml
  uv.lock

  docker/
    web-agent-mcp/
      Dockerfile

  searxng/
    settings.yml          ← SearXNG の設定（JSON API 有効化済み）

  src/
    web_agent_mcp/
      server.py           ← MCP サーバーエントリーポイント
      config.py
      models.py
      tools/              ← 5 ツールの実装
      search/             ← SearXNG クライアント
      fetch/              ← HTTP フェッチ + SSRF 防御 + Playwright ブラウザフェッチ
      extract/            ← HTML/PDF 抽出（重複ブロック除去含む）
      storage/            ← diskcache + SQLite FTS5

  data/
    cache/                ← HTTP レスポンスキャッシュ（.gitignore）
    index/                ← SQLite FTS5 インデックス（.gitignore）
    docs/                 ← ローカル PDF 配置ディレクトリ（.gitignore）

  docs/
    test_results.md       ← テスト結果レポート
```

---

## テスト結果

詳細は [docs/test_results.md](docs/test_results.md) を参照してください。

全 10 テスト PASS ✅

---

## GitHub へのプッシュ（初回）

```bash
# GitHub でリポジトリを作成後（https://github.com/new）
cd ~/web-agent-mcp
git remote add origin https://github.com/YOUR_USERNAME/web-agent-mcp.git
git branch -M main
git push -u origin main
```

> `.env`（プロキシ設定・パスワード）と `data/` 以下のキャッシュ・PDF は  
> `.gitignore` により GitHub には **アップロードされません**。

---

## 別の PC での再インストール（クローンから起動まで）

```bash
# WSL2 Ubuntu で実行
git clone https://github.com/YOUR_USERNAME/web-agent-mcp.git
cd web-agent-mcp
chmod +x setup.sh
./setup.sh        # ← これだけで完了
```

`setup.sh` が以下をすべて自動で行います：
1. プロキシ設定（対話式）
2. Docker CE インストール
3. uv インストール
4. データディレクトリ作成
5. Docker イメージビルド & サービス起動
6. 疎通確認
