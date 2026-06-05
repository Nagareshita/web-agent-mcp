# Windows ネイティブ構築手順書
## Qwen3-Coder-Next (llama.cpp) + Claude Code VSCode拡張

**対象環境**
- OS: Windows 10/11 (WSL不要、ネイティブ)
- GPU: NVIDIA RTX 4070 12GB
- RAM: 64GB以上推奨
- VSCode 1.98.0以上

---

## 全体構成

```
[llama-server.exe]  ←→  [Claude Code VSCode拡張]
  ポート8080               settings.json で接続先指定
  CUDA + CPUオフロード      ログイン不要（ローカルキー認証）
```

---

## STEP 1：前提ソフトウェアのインストール

### 1-1. CUDA Toolkit

NVIDIA公式からCUDA Toolkit 12.4以上をインストール。

```
https://developer.nvidia.com/cuda-downloads
```

インストール確認：
```powershell
nvcc --version
nvidia-smi
```

### 1-2. Node.js (Claude Code CLIに必要)

Node.js LTS (v18以上) をインストール。

```
https://nodejs.org/
```

インストール確認：
```powershell
node -v
npm -v
```

---

## STEP 2：llama-server の準備（ビルド不要）

### 2-1. プレビルドバイナリのダウンロード

以下から最新リリースのWindows CUDA版zipを取得：

```
https://github.com/ggml-org/llama.cpp/releases
```

ファイル名の例：`llama-b9522-bin-win-cuda-12.4-x64.zip`

> **注意**：CUDA 12.4以上と一致するバージョンを選ぶこと。

### 2-2. 展開と配置

```powershell
# 例：C:\llama.cpp\ に展開
Expand-Archive llama-b9505-bin-win-cuda-12.4-x64.zip C:\llama.cpp\
```

展開後、`C:\llama.cpp\llama-server.exe` が存在することを確認。

---

## STEP 3：モデルのダウンロード

https://huggingface.co/unsloth/Qwen3-Coder-Next-GGUF
の中から、Qwen3-Coder-Next-UD-Q4_K_XL.gguf　を探し出して、ダウンロード。
（右あたりにある「UD-Q4_K_XL49.6 GB」）

> **所要時間**：約40〜50GB、回線速度次第で数十分。
> **ストレージ**：NVMe SSD推奨（モデルロード速度に影響）。

---

## STEP 4：llama-server 起動スクリプトの作成

`C:\llama.cpp\start_server.ps1` として保存：

```powershell
# Qwen3-Coder-Next 起動スクリプト (RTX 4070 12GB向け)
$env:GGML_CUDA_GRAPH_OPT = "1"

$MODEL = "C:\localllm\models\Qwen3-Coder-Next-UD-Q4_K_XL.gguf"
$SERVER = "C:\localllm\llamacpp\llama-server.exe"

& $SERVER `
  -m $MODEL `
  --host 127.0.0.1 `
  --port 8080 `
  --ctx-size 65536 `
  --fit on `
  --flash-attn on `
  --jinja `
  -b 2048 -ub 1024 `
  --no-mmap `
  --api-key local-key

**主要フラグの説明**

| フラグ | 説明 |
|--------|------|
| `--fit on` | 起動時にVRAMを自動プローブし、最適なGPU/CPUレイヤー配置を自動計算。手動 `-ngl` 調整不要 |
| `--flash-attn on` | Flash Attention有効化（`1` は旧構文。`on` が正しい） |
| `--ctx-size 65536` | Gated DeltaNetハイブリッドアーキテクチャのため、64KでもVRAM増加は最小限（通常モデルより大幅に軽い） |
| `--no-mmap` | 大型モデルで安定動作 |
| `--jinja` | Qwen3系チャットテンプレート用 |
| `--host 127.0.0.1` | ローカルのみ公開（セキュリティ） |

### 起動確認

```powershell
# スクリプト実行（初回は数十秒かかる）
powershell -ExecutionPolicy Bypass -File C:\llama.cpp\start_server.ps1
```

起動ログに以下が表示されれば成功：
```
llama server listening at http://127.0.0.1:8080
```

VRAMの使用状況を確認：
```powershell
nvidia-smi
```

---

## STEP 5：グローバル設定ファイルの作成

`%USERPROFILE%\.claude\settings.json` を作成（フォルダがなければ作成）：

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:8080",
    "ANTHROPIC_API_KEY": "local-key",
    "CLAUDE_CODE_ATTRIBUTION_HEADER": "0"
  }
}
```

> **⚠️ 重要 `CLAUDE_CODE_ATTRIBUTION_HEADER: "0"` について**
> Claude Codeは全リクエストにAttributionヘッダーを付与するが、これがllama.cppのKVキャッシュを
> 無効化し、推論速度が最大90%低下する。環境変数での設定は無効で、必ずこのファイルに書くこと。

---

## STEP 6：VSCode拡張のインストールと設定

### 6-1. 拡張のインストール

VSCodeの拡張機能ビューを開く（`Ctrl+Shift+X`）→ `Claude Code` を検索 → インストール。

### 6-2. VSCode設定ファイルの編集

> **⚠️ 重要**：VSCodeの拡張はシェルの環境変数を継承しない。
> `settings.json` に直接書く必要がある。

**ユーザーレベル設定**（全プロジェクト共通にする場合）

`Ctrl+Shift+P` → `Preferences: Open User Settings (JSON)` を開き、以下を追記：

```json
{
  "claudeCode.environmentVariables": [
    {
      "name": "ANTHROPIC_BASE_URL",
      "value": "http://127.0.0.1:8080"
    },
    {
      "name": "ANTHROPIC_AUTH_TOKEN",
      "value": "local-key"
    },
    {
      "name": "CLAUDE_CODE_ATTRIBUTION_HEADER",
      "value": "0"
    }
  ],
  "claudeCode.disableLoginPrompt": true
}
```

**プロジェクトレベル設定**（プロジェクト毎に切り替える場合）

`.vscode/settings.json` に同じ内容を記載。
> **⚠️** APIキーをgitにコミットしないよう `.gitignore` に `.vscode/settings.json` を追加すること。

### 6-3. モデル名の確認

llama-serverに設定した `--alias` またはモデルファイル名がそのままモデル名になる。
必要に応じて以下を追加：

```json
{
  "claudeCode.selectedModel": "Qwen3-Coder-Next-UD-Q4_K_XL"
}
```

---

## STEP 7：動作確認

1. `start_server.ps1` を実行（llama-server起動）
2. VSCodeでプロジェクトを開く
3. エディタツールバー右上のSparkアイコン（⚡）をクリック
4. サインイン画面が出ない / ローカルサーバーに接続されることを確認
5. 簡単なプロンプトで動作テスト

---

## トラブルシューティング

| 症状 | 原因 | 対処 |
|------|------|------|
| サーバー起動時にVRAM不足エラー | `--fit on` でもVRAM超過 | `--ctx-size 32768` に下げる |
| 推論が極端に遅い（10tok/s以下） | KVキャッシュ無効化 | `CLAUDE_CODE_ATTRIBUTION_HEADER: "0"` を settings.json に書いたか確認 |
| VSCodeでサインイン画面が出る | 環境変数が未反映 | `claudeCode.disableLoginPrompt: true` を追加、VSCode完全再起動 |
| `claude` コマンドがDesktop Appを起動 | PATHの競合 | `where claude` で確認、npmパスを優先に |
| モデルのロードが遅い | HDDからの読み込み | NVMe SSDに移動、`--no-mmap` は維持 |
| ツールコールが壊れる | llama.cppバージョンが古い | 最新リリースに更新（Feb 4以降のバグ修正版） |

---

## 毎回の起動手順（定常運用）

```
1. start_server.ps1 を実行（またはタスクスケジューラに登録）
2. VSCode を開く
```

---

## 参考：ハードウェアスペック要件まとめ

| 項目 | 最低 | 推奨 |
|------|------|------|
| VRAM | 12GB (RTX 4070) | 16GB以上 |
| システムRAM | 64GB | 96GB以上 |
| CPU | 8コア以上 | 16コア以上（CPUオフロード高速化） |
| ストレージ | 60GB空き | NVMe SSD必須 |

## 参考：webサーチのMCPサーバ

ClaudeCodeの標準webサーチツールが使えなくなるので、
MCPサーバを使う。プロジェクトフォルダに.mcp.jsonを作成し、以下を記載。
　
{
  "mcpServers": {
    "web-agent": {
      "type": "http",
      "url": "http://localhost:8103/mcp"
    }
  }
}

同梱のCLAUDE.md　も置いておくとよい。