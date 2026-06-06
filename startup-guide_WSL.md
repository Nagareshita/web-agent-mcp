# startup-guide — web-agent-mcp セットアップ手順

## 前提

Windows 11 (または 10) + 管理者権限

---

## 1. WSL2 のインストール（管理者 PowerShell）

```powershell
wsl --install
```

PC を再起動 → Ubuntu が起動したらユーザー名・パスワードを設定。

---

## 2. リポジトリのクローン（Ubuntu ターミナル）

```bash
cd ~
git clone https://github.com/YOUR_USERNAME/web-agent-mcp.git
cd web-agent-mcp
```

---

## 3. セットアップ（Docker・uv・サービス起動を一括実行）

```bash
chmod +x setup.sh
./setup.sh
```

途中でプロキシ設定を聞かれます。不要なら Enter でスキップ。

完了後、**WSL を再起動**して docker グループを反映します：

```powershell
# Windows PowerShell で実行
wsl --shutdown
wsl
```

---

## 4. 起動確認

```bash
cd ~/web-agent-mcp
docker compose ps
```

`web-agent-mcp` と `web-agent-searxng` が `Up` になっていれば OK。

---

## 5. VS Code の MCP 設定

`Ctrl+Shift+P` → `Preferences: Open User Settings (JSON)` に追記：

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

`Ctrl+Shift+P` → `MCP: List Tools` で以下の 5 ツールが表示されれば完了：

- `web_search`
- `web_read`
- `web_read_many`
- `local_document_search`
- `cache_status`

---

## 日常操作

```bash
cd ~/web-agent-mcp

docker compose up -d        # 起動
docker compose down         # 停止
docker compose logs -f      # ログ確認
docker compose up -d --build  # コード変更後の再ビルド
```
