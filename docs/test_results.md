# web-agent-mcp テスト結果レポート

実行日時: 2026-06-05  
MCP エンドポイント: `http://localhost:8103/mcp`  
サーバーバージョン: `web_agent_mcp 1.27.2`

---

## テスト共通プロンプト

```bash
mcp_call() {
  curl -s http://localhost:8103/mcp -X POST \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"$1\",\"arguments\":$2}}" \
    | grep '^data:' | head -1 | sed 's/^data: //'
}
```

---

## TEST 1 — ドキュメント検索

**目的**: `web_search` ツールで技術ドキュメントを検索できるか確認する。

### プロンプト

```bash
mcp_call "web_search" '{
  "params": {
    "query": "Python MCP SDK documentation",
    "max_results": 5
  }
}'
```

### 結果 ✅ PASS

```
query: Python MCP SDK documentation
provider: searxng
cache_hit: false

1. GitHub - modelcontextprotocol/python-sdk: The official Python SDK for Model Context Protocol servers and clients
   https://github.com/modelcontextprotocol/python-sdk  [github.com]
   For the upcoming v2 documentation (pre-alpha, in development on main), see README.v2.md.

2. MCP Python SDK
   https://pypi.org/project/mcp/  [pypi.org]
   We recommend using uv to manage your Python projects.

3. SDKs - Model Context Protocol
   https://modelcontextprotocol.io/docs/sdk  [modelcontextprotocol.io]
   Visit the SDK page for your chosen language to find installation instructions, documentation, and examples.

4. MCP Python SDK のドキュメント｜npaka - note
   https://note.com/npaka/n/nffa8b33fe7d3  [note.com]

5. Model context protocol (MCP) - OpenAI Agents SDK
   https://openai.github.io/openai-agents-python/mcp/  [openai.github.io]
```

---

## TEST 2 — 技術ブログ検索

**目的**: `web_search` で英語の技術ブログ記事を検索できるか確認する。

### プロンプト

```bash
mcp_call "web_search" '{
  "params": {
    "query": "FastMCP Streamable HTTP tutorial",
    "language": "en",
    "max_results": 5
  }
}'
```

### 結果 ✅ PASS

```
1. HTTP Deployment - FastMCP
   https://fastmcp.wiki/en/deployment/http  [fastmcp.wiki]
   By default, FastMCP's Streamable HTTP transport maintains server-side sessions.

2. Building Production-Ready MCP Server with Streamable-HTTP ...
   https://medium.com/@nsaikiranvarma/building-production-ready-mcp-server-with-streamable-http-transport-in-15-minutes  [medium.com]
   Why HTTP Streamable Transport is Revolutionary · Deploy Anywhere: Your MCP server becomes a standard web service.

3. Client Transports - FastMCP
   https://fastmcp.wiki/en/clients/transports  [fastmcp.wiki]
   SSE Transport Server-Sent Events transport is maintained for backward compatibility.

4. Running Your Server - FastMCP
   https://gofastmcp.com/deployment/running-server  [gofastmcp.com]
   HTTP Transport (Streamable) ... Your server is now accessible at http://localhost:8000/mcp.

5. Build StreamableHTTP MCP Servers - Production Guide | MCPcat
   https://mcpcat.io/guides/building-streamablehttp-mcp-server/  [mcpcat.io]
   Deploy scalable MCP servers using StreamableHTTP for cloud environments and remote access.
```

---

## TEST 3 — GitHub README 参照

**目的**: `web_read` ツールで GitHub の raw コンテンツ（Markdown）を取得・抽出できるか確認する。

### プロンプト

```bash
mcp_call "web_read" '{
  "params": {
    "url": "https://raw.githubusercontent.com/modelcontextprotocol/python-sdk/main/README.md",
    "return_links": false,
    "max_chars": 800
  }
}'
```

### 結果 ✅ PASS

```
input_url:         https://raw.githubusercontent.com/modelcontextprotocol/python-sdk/main/README.md
source_type:       html
extraction_method: trafilatura
status_code:       200
cache_hit:         true (2回目以降)

--- content preview ---
# MCP Python SDK
**Python implementation of the Model Context Protocol (MCP)**

> [!NOTE]
> **This README documents v1.x of the MCP Python SDK (the current stable release).**
> For the upcoming v2 documentation (pre-alpha, in development on `main`), see README.v2.md.

## Table of Contents
- [MCP Python SDK](#mcp-python-sdk)
- [Overview](#overview)
- [Installation](#installation)
...
```

---

## TEST 4 — GitHub コード例検索

**目的**: `web_search` の `site:` パラメータで GitHub リポジトリに絞り込んでコード例を検索できるか確認する。

### プロンプト

```bash
mcp_call "web_search" '{
  "params": {
    "query": "FastMCP streamable http server example",
    "max_results": 5,
    "site": "github.com"
  }
}'
```

### 結果 ✅ PASS

```
1. PrefectHQ/fastmcp: The fast, Pythonic way to build MCP servers and clients.
   https://github.com/PrefectHQ/fastmcp
   Built by the FastMCP team, Horizon packages the best practices...

2. how to manage multi streamable http server lifespan · Issue #713
   https://github.com/modelcontextprotocol/python-sdk/issues/713

3. [Question] How to set-up a https mcp-server? · PrefectHQ fastmcp
   https://github.com/PrefectHQ/fastmcp/discussions/1232

4. Confusion about "Streamable HTTP" in MCP
   https://github.com/PrefectHQ/fastmcp/issues/2050

5. oleksandrsirenko/mcp-simple-server - GitHub
   https://github.com/oleksandrsirenko/mcp-simple-server
   A minimal, reference implementation of a Model Context Protocol server with streamable HTTP transport.
```

---

## TEST 5 — PDF 発見・読み取り（URL）

**目的**: `web_read` でリモート PDF URL を自動検出し PyMuPDF で全ページ抽出できるか確認する。  
テスト対象: arXiv 論文「Attention Is All You Need」(1706.03762)

### プロンプト

```bash
mcp_call "web_read" '{
  "params": {
    "url": "https://arxiv.org/pdf/1706.03762",
    "return_links": false,
    "max_chars": 1200
  }
}'
```

### 結果 ✅ PASS

```
input_url:         https://arxiv.org/pdf/1706.03762
source_type:       pdf
extraction_method: pymupdf
pages extracted:   15 ページ (15 チャンク + 小ページ)
chunks:            40

--- content preview ---
[Page 1]
Provided proper attribution is provided, Google hereby grants permission to
reproduce the tables and figures in this paper solely for use in journalistic or
scholarly works.

Attention Is All You Need
Ashish Vaswani, Noam Shazeer, Niki Parmar, Jakob Uszkoreit, Llion Jones,
Aidan N. Gomez, Łukasz Kaiser, Illia Polosukhin
...
```

---

## TEST 6 — JavaScript ページ表示（MDN Web Docs）

**目的**: `web_read` で日本語の JavaScript 解説ページを Markdown として抽出できるか確認する。

### プロンプト

```bash
mcp_call "web_read" '{
  "params": {
    "url": "https://developer.mozilla.org/ja/docs/Web/JavaScript",
    "return_links": false,
    "max_chars": 1000
  }
}'
```

### 結果 ✅ PASS

```
title:             JavaScript
final_url:         https://developer.mozilla.org/ja/docs/Web/JavaScript
source_type:       html
extraction_method: trafilatura

--- content preview ---
# JavaScript

**JavaScript** (**JS**) は軽量でインタープリター型（あるいは実行時コンパイルされる）
第一級関数を備えたプログラミング言語です。ウェブページでよく使用されるスクリプト言語
として知られ、多くのブラウザー以外の環境、例えば Node.js や Apache CouchDB や Adobe
Acrobat などでも使用されています。

JavaScript はプロトタイプベースで、ガベージコレクションのある、動的な言語であり、
命令型、関数型、オブジェクト指向など、複数のパラダイムに対応しています。
...
```

---

## TEST 7 — 広範囲の最新 Web 調査（並列取得）

**目的**: `web_read_many` で複数 URL を並列フェッチして一度に調査できるか確認する。

### プロンプト

```bash
mcp_call "web_read_many" '{
  "params": {
    "urls": [
      "https://modelcontextprotocol.io/introduction",
      "https://docs.python.org/3/whatsnew/3.13.html",
      "https://github.com/modelcontextprotocol/python-sdk",
      "https://fastmcp.wiki/en/deployment/http"
    ],
    "max_concurrency": 4,
    "max_chars_per_url": 600
  }
}'
```

### 結果 ✅ PASS

```
取得成功: 4 件
エラー  : 0 件

[html] What is the Model Context Protocol (MCP)? - Model Context Protocol
  https://modelcontextprotocol.io/introduction
  preview: ## What can MCP enable? - Agents can access your Google Calendar and Notion...

[html] What's New In Python 3.13
  https://docs.python.org/3/whatsnew/3.13.html
  preview: # What's New In Python 3.13¶ - Editors: Adam Turner and Thomas Wouters...

[html] GitHub - modelcontextprotocol/python-sdk: The official Python SDK...
  https://github.com/modelcontextprotocol/python-sdk
  preview: This README documents v1.x of the MCP Python SDK (the current stable release)...

[html] HTTP Deployment - FastMCP
  https://fastmcp.wiki/en/deployment/http
  preview: FastMCP provides two ways to deploy your server as an HTTP service...
```

---

## TEST 8 — ローカル PDF 読み取り

**目的**: `web_read` の `local_path` パラメータで `/app/docs` 以下のローカル PDF を読み取れるか確認する。  
テスト対象: `おすすめ株15選_2026年4月.pdf`（Nikkei225 スクリーニングレポート）

### プロンプト

```bash
mcp_call "web_read" '{
  "params": {
    "local_path": "/app/docs/おすすめ株15選_2026年4月.pdf",
    "max_chars": 2000
  }
}'
```

### 結果 ✅ PASS

```
local_path:        /app/docs/おすすめ株15選_2026年4月.pdf
source_type:       pdf
extraction_method: pymupdf
pages extracted:   19 ページ
chunks:            21

--- content preview ---
[Page 1]
日本株スクリーニング
推奨15選
2026年4月24日実行 | Nikkei225 212銘柄分析 | ROE≥12% × 売上CAGR≥8%
S グレード最優先 7銘柄 / A グレード優先 5銘柄 / B グレードウォッチ 3銘柄

スクリーニング条件: ROE≥12% / 売上CAGR(3年)≥8% / D/EBITDA≤3.0x / FCFマージン≥5% / PER≤40x

[Page 2]
15銘柄スクリーニング結果一覧
S  3092.T  ZOZO, Inc.           Consumer Cyclical  時価総額:9,352億円  ROE:50.3%  score:155.6  買い
S  7013.T  IHI Corporation      Industrials        時価総額:31,752億円 ROE:23.6%  score:137.4  買い
S  9202.T  ANA Holdings Inc.    Industrials        時価総額:12,220億円 ROE:12.3%  score:135.5  買い
...
```

---

## TEST 9 — ローカルドキュメント全文検索（FTS5）

**目的**: `local_document_search` ツールで既読文書を SQLite FTS5 で再検索できるか確認する。

### プロンプト

```bash
mcp_call "local_document_search" '{
  "params": {
    "query": "ZOZO",
    "max_results": 5
  }
}'
```

### 結果 ✅ PASS

```
query: ZOZO
hits: 3

[pdf] page:3  score:-3.502
  snippet: S #1 <b>ZOZO</b> 3092.T 155.6pt 消費財 | 時価総額:9,352億円 | 現在株価:1,057.5円
           ROE 50.3% 自己資本利益率 ...

[pdf] page:19 score:-1.755
  snippet: ...EPS成長法 × PEG=1.5/2.0 × アナリストコンセンサス 複合
           ティッカー 銘柄名 現在株価(円) 第1利確 ...

[pdf] page:2  score:-1.504
  snippet: ...S 3092.T <b>ZOZO</b>, Inc. Consumer Cyclical 9,352 50.3 8.6 0.00 25.3 ...
```

---

## TEST 10 — キャッシュ状態確認

**目的**: `cache_status` ツールでキャッシュ・インデックスの統計を確認できるか確認する。

### プロンプト

```bash
mcp_call "cache_status" '{"params": {}}'
```

### 結果 ✅ PASS

```
document_count:     2
search_cache_count: 4
size_bytes:         458,428
cache_dir:          /app/cache
index_dir:          /app/index
```

---

## テスト結果サマリー

| # | テスト項目 | ツール | 結果 |
|---|-----------|--------|------|
| 1 | ドキュメント検索 | `web_search` | ✅ PASS |
| 2 | 技術ブログ検索 | `web_search` | ✅ PASS |
| 3 | GitHub README 参照 | `web_read` (HTML) | ✅ PASS |
| 4 | GitHub コード例検索 | `web_search` (site:) | ✅ PASS |
| 5 | PDF 発見・読み取り (URL) | `web_read` (PDF) | ✅ PASS |
| 6 | JavaScript ページ表示 | `web_read` (HTML/日本語) | ✅ PASS |
| 7 | 広範囲の最新 Web 調査 | `web_read_many` (並列) | ✅ PASS |
| 8 | ローカル PDF 読み取り | `web_read` (local_path) | ✅ PASS |
| 9 | FTS5 ドキュメント検索 | `local_document_search` | ✅ PASS |
| 10 | キャッシュ状態確認 | `cache_status` | ✅ PASS |

**全 10 テスト PASS**
