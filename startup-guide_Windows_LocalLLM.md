# Windows ネイティブ構築手順書
## Qwen3-Coder-Next (llama.cpp) + Claude Code VSCode拡張

| 対象環境 | |
|---|---|
| OS | Windows 10/11 |
| GPU | NVIDIA RTX 4070 12GB |
| RAM | 64GB以上推奨 |
| VSCode | 1.98.0以上 |

---

## 全体構成

```
[llama-server.exe]  ←→  [Claude Code VSCode拡張]
  ポート8080               settings.json で接続先指定
  CUDA + CPUオフロード      ログイン不要（ローカルキー認証）
```

| コンポーネント | 詳細 |
|---|---|
| 実行ファイル | llama-server.exe (CUDA + CPUオフロード) |
| ポート | 8080 (127.0.0.1) |
| クライアント | Claude Code VSCode拡張 |
| 認証 | ローカルキー認証 (`--api-key local-key`) |

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

以下から同じリリース番号・同じCUDAバージョンのWindows CUDA版zipを2つ取得：

```
https://github.com/ggml-org/llama.cpp/releases
```

ファイル名の例：

```
llama-b9536-bin-win-cuda-12.4-x64.zip
cudart-llama-bin-win-cuda-12.4-x64.zip  （CUDA 12.4 DLLsと表示）
```

`llama-b...zip` は llama.cpp 本体、`cudart-llama...zip` は CUDA ランタイム DLL。
両方を同じ `C:\localllm\llamacpp\` に展開する。

> **注意**：CUDA 12.4版を使う場合は、2つとも `cuda-12.4-x64` のものを選ぶこと。

### 2-2. 展開と配置

任意のフォルダ（例：`C:\localllm\llamacpp\`）に展開し、以下のファイルが存在することを確認：

```
C:\localllm\llamacpp\llama-server.exe
C:\localllm\llamacpp\cudart64_12.dll
C:\localllm\llamacpp\cublas64_12.dll
```

---

## STEP 3：モデルのダウンロード

以下のURLから `Qwen3-Coder-Next-UD-Q4_K_XL.gguf` を探してダウンロード：

```
https://huggingface.co/unsloth/Qwen3-Coder-Next-GGUF
```

（右あたりにある「UD-Q4_K_XL  49.6 GB」）

ダウンロード後、`C:\localllm\models\Qwen3-Coder-Next\` に保存。

| 項目 | 詳細 |
|---|---|
| 所要時間 | 約49.6GB、回線速度次第で数十分（100Mbpsで約1時間） |
| ストレージ | NVMe SSD推奨（HDDではモデルロードに10分以上かかる） |
| モデル特性 | Gated DeltaNetハイブリッドアーキテクチャ採用で、同サイズのTransformerよりVRAM消費が30〜40%少ない |

---

## STEP 4：llama-server 起動スクリプトの作成

`C:\localllm\scripts\start_server.ps1` として保存：

```powershell
$env:GGML_CUDA_GRAPH_OPT = "1"
$env:LLAMA_SET_ROWS = "1"

$MODEL = "C:\localllm\models\Qwen3-Coder-Next\Qwen3-Coder-Next-UD-Q4_K_XL.gguf"
$SERVER = "C:\localllm\llamacpp\llama-server.exe"

& $SERVER `
  -m $MODEL `
  --alias qwen3-coder-next `
  --host 127.0.0.1 `
  --port 8080 `
  --ctx-size 131072 `
  --fit on `
  --fit-ctx 131072 `
  --fit-target 128 `
  -ctk q8_0 `
  -ctv q8_0 `
  --parallel 1 `
  --flash-attn on `
  --jinja `
  -b 2048 -ub 512 `
  --no-mmap `
  --api-key local-key
```

### 主要フラグの説明

| フラグ | 説明 | 推奨値 | 備考 |
|---|---|---|---|
| `--fit on` | 起動時にVRAMを自動プローブし、最適なGPU/CPUレイヤー配置を自動計算。手動 `-ngl` 調整不要 | `on` | `off` の場合は手動で `-ngl 999` など指定必要 |
| `--fit-ctx 131072` | VRAMプローブ時のコンテキストサイズ基準。このサイズでVRAM使用量を推定 | `131072` | `--ctx-size` と一致させることが基本 |
| `--fit-target 128` | VRAMの安全マージン（MiB単位）。ここを下回るとオフロードが発生 | `128` | 少し余裕を持たせる（64以下は危険） |
| `--ctx-size 131072` | 最大コンテキスト長（トークン数）。64K/128Kが実用的 | `131072` | Qwen3-Coder-Nextは64Kでも軽いが、128Kも可能 |
| `--parallel 1` | 並列リクエスト数。Claude Code単体使用なら1で十分 | `1` | 複数クライアント同時利用時は2〜4に増やす |
| `-ctk q8_0` | KVキャッシュの量子化方式。VRAM削減+速度維持のバランス | `q8_0` | `q4_K_M` はVRAM削減効果大だが精度低下リスク |
| `-ctv q8_0` | KVキャッシュの量子化方式（Value部分）。`-ctk` と一致させる | `q8_0` | 量子化なし (`fp16`) はVRAM消費が2倍になる |
| `--flash-attn on` | Flash Attention v2有効化。推論速度20〜40%向上 | `on` | RTX 30系以降必須。`1` は旧構文 |
| `--jinja` | Jinja2テンプレートエンジンでチャットフォーマットを処理 | `on` | Qwen3/Claude系チャットモデルに必須 |
| `--no-mmap` | メモリマップドI/Oを無効化。モデルロード時に全量をRAMに読み込む | `on` | HDD/遅いSSDでは有効、NVMeなら省略可 |
| `-b 2048` | バッチサイズ（プロンプト処理単位）。推論速度に影響 | `2048` | VRAM許す限り大きく（4096〜8192） |
| `-ub 512` | ユニバーサルバッチサイズ（生成単位）。トークン生成速度に影響 | `512` | 通常256〜1024。大きくするほど生成が速い |
| `--host 127.0.0.1` | バインドアドレス。`0.0.0.0` にするとネットワーク経由でアクセス可能 | `127.0.0.1` | セキュリティのためローカルのみが推奨 |
| `--api-key local-key` | API認証用キーセット。空欄にすると認証なしになる | `local-key` | 同じキーをクライアント設定で必須 |
| `-m $MODEL` | モデルファイルパス（GGUF形式） | 必須 | 相対パス・絶対パスどちらでも可 |
| `--port 8080` | サーバー監視ポート | `8080` | 他のプロセスと競合しない任意のポート |
| `$env:LLAMA_SET_ROWS=1` | 環境変数。行ベース処理でVRAM効率を向上 | `1` | CUDA最適化用。0の場合は列ベース |
| `$env:GGML_CUDA_GRAPH_OPT=1` | 環境変数。CUDAグラフ最適化を有効化 | `1` | 推論速度向上（10〜15%） |

### 起動確認

```powershell
# スクリプト実行（初回は数十秒かかる）
powershell -ExecutionPolicy Bypass -File C:\localllm\scripts\start_server.ps1
```

---

## STEP 5：VSCode拡張のインストールと設定

### 5-1. Claude Code のインストール

VSCodeの拡張機能ビュー（`Ctrl+Shift+X`）→「Claude Code」を検索 → インストール。

### 5-2. .vscode/settings.json の作成と配置

`.vscode\settings.json` を作成（フォルダがなければ作成）：

```json
{
  "claudeCode.environmentVariables": [
    { "name": "ANTHROPIC_BASE_URL",                        "value": "http://127.0.0.1:8080" },
    { "name": "ANTHROPIC_AUTH_TOKEN",                      "value": "local-key" },
    { "name": "ANTHROPIC_MODEL",                           "value": "qwen3-coder-next" },
    { "name": "ANTHROPIC_CUSTOM_MODEL_OPTION",             "value": "qwen3-coder-next" },
    { "name": "ANTHROPIC_CUSTOM_MODEL_OPTION_NAME",        "value": "Qwen3 Coder Next Local" },
    { "name": "ANTHROPIC_CUSTOM_MODEL_OPTION_DESCRIPTION", "value": "Local llama.cpp Qwen3-Coder-Next GGUF" },
    { "name": "CLAUDE_CODE_ATTRIBUTION_HEADER",            "value": "0" }
  ],
  "claudeCode.disableLoginPrompt": true
}
```

> **⚠️ 重要：`CLAUDE_CODE_ATTRIBUTION_HEADER: "0"` について**
>
> Claude Codeは全リクエストにAttributionヘッダーを付与するが、これがllama.cppのKVキャッシュを無効化し、推論速度が最大90%低下する。環境変数での設定は無効で、必ずこのファイルに書くこと。

### .vscode/settings.json 設定項目一覧

| 設定項目 | 値 | 意味 |
|---|---|---|
| `claudeCode.environmentVariables` | 配列 | Claude Code VSCode拡張から起動されるプロセスへ渡す環境変数の一覧。ローカルLLM接続先、認証キー、モデル名などを指定する |
| `ANTHROPIC_BASE_URL` | `http://127.0.0.1:8080` | Claude Codeの接続先API。ローカルで起動している `llama-server` を指定する。`--host 127.0.0.1` と `--port 8080` に対応 |
| `ANTHROPIC_AUTH_TOKEN` | `local-key` | API認証用トークン。`llama-server` 起動時の `--api-key local-key` と一致させる |
| `ANTHROPIC_MODEL` | `qwen3-coder-next` | 実際に使用するモデルID。`llama-server` 側で `--alias qwen3-coder-next` を指定している場合、この値と一致させる |
| `ANTHROPIC_CUSTOM_MODEL_OPTION` | `qwen3-coder-next` | Claude Codeの `/model` 選択肢に追加するカスタムモデルID。通常は `ANTHROPIC_MODEL` と同じ値にする |
| `ANTHROPIC_CUSTOM_MODEL_OPTION_NAME` | `Qwen3 Coder Next Local` | `/model` に表示されるモデル名。人間が見て分かりやすい表示名を付ける |
| `ANTHROPIC_CUSTOM_MODEL_OPTION_DESCRIPTION` | `Local llama.cpp Qwen3-Coder-Next GGUF` | `/model` に表示される説明文。どのローカルモデル・実行環境なのかを補足する |
| `CLAUDE_CODE_ATTRIBUTION_HEADER` | `0` | Attributionヘッダーを抑制する設定。ローカル `llama.cpp` 利用時にKVキャッシュ無効化や速度低下を避ける目的で設定する |
| `claudeCode.disableLoginPrompt` | `true` | Claude Code VSCode拡張のログイン要求を抑制する設定。Anthropic公式APIではなく、ローカル互換APIへ接続する場合に使う |
| `claudeCode.selectedModel` | 使わない | 公式設定として確認できないため使わない。モデル指定には `ANTHROPIC_MODEL` を使う |

### 5-3. webfetch および websearch ツールの停止

ローカルLLMをClaudeCodeで使用するとwebfetch および websearchツールが使えない（Claudeのサーバにアクセスできないため）。
このツールを停止し、自作のwebfetch/searchのMCPサーバを使用する。
Workflowもweb検索するためにループし、エラーとなるため使わない設定とする。

`.claude\settings.json` を作成（フォルダがなければ作成）：

```json
{
  "permissions": {
    "allow": [
      "mcp__web-agent",
      "mcp__web-agent__*"
    ],
    "deny": [
      "WebFetch",
      "WebSearch"
    ]
  },
  "disableWorkflows": true
}
```

### 5-4. MCP サーバの有効化

`.mcp.json` をプロジェクトルートに作成し、WSLでMCPサーバ `web-agent` を有効化する：

```json
{
  "mcpServers": {
    "web-agent": {
      "type": "http",
      "url": "http://localhost:8103/mcp"
    }
  }
}
```

---

## STEP 6：動作確認

1. `start_server.ps1` を実行（llama-server起動）
2. VSCodeでプロジェクトを開く
3. エディタツールバー右上のSparkアイコン（⚡）をクリック
4. サインイン画面が出ない / ローカルサーバーに接続されることを確認
5. 簡単なプロンプトで動作テスト

---

## トラブルシューティング

| 症状 | 原因 | 対処 |
|---|---|---|
| サーバー起動時にVRAM不足エラー | `--fit on` でもVRAM超過 | `--ctx-size 32768` に下げる |
| 推論が極端に遅い（10tok/s以下） | KVキャッシュ無効化 | `CLAUDE_CODE_ATTRIBUTION_HEADER: "0"` を settings.json に書いたか確認 |
| VSCodeでサインイン画面が出る | 環境変数が未反映 | `claudeCode.disableLoginPrompt: true` を追加、VSCode完全再起動 |
| `claude` コマンドがDesktop Appを起動 | PATHの競合 | `where claude` で確認、npmパスを優先に |
| モデルのロードが遅い | HDDからの読み込み | NVMe SSDに移動、`--no-mmap` は維持 |
| ツールコールが壊れる | llama.cppバージョンが古い | 最新リリースに更新（Feb 4以降のバグ修正版） |

---

## 毎回の起動手順（定常運用）

1. `start_server.ps1` を実行（またはタスクスケジューラに登録）
2. VSCode を開く

---

## 参考：ハードウェアスペック要件

| 項目 | 最低 | 推奨 |
|---|---|---|
| VRAM | 12GB (RTX 4070) | 16GB以上 |
| システムRAM | 64GB | 96GB以上 |
| CPU | 8コア以上 | 16コア以上（CPUオフロード高速化） |
| ストレージ | 60GB空き | NVMe SSD必須 |
