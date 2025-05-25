# MVP 仕様書（Agents SDK + ローカル Markdown 保存版）

## 1. 目的

生成 AI 記事自動化パイプラインの最小実用プロトタイプを構築する。  
**note への自動投稿は行わず**、生成した記事をローカルに `.md` ファイルとして保存するところまでを対象とする。

---

## 2. スコープ

| 項目     | 内容                                                                 |
| -------- | -------------------------------------------------------------------- |
| 生成対象 | 9:00〜18:00 の各時間帯ごとに 1 本（最大 10 本）                      |
| 出力形式 | UTF-8 / Markdown ファイル (`articles/YYYY-MM-DD_HH-タイトルslug.md`) |
| 保存場所 | プロジェクト直下 `articles/` ディレクトリ                            |
| LLM      | OpenAI GPT-4o-mini（Title/Outline） + Gemini 2.5（Draft）            |
| DB       | MySQL (タイトル重複排除・メタ保存)                                   |
| 実行方式 | cron から `python run.py` を呼び出し、1 本生成・保存                 |
| 除外     | Playwright 投稿、自動 RAG、Guardrail 厳格検査                        |

---

## 3. ディレクトリ構成（完成形）

```

ai\_writer/
├─ agents/                 # Agents SDK 定義
│   ├─ coordinator.py
│   ├─ title\_planner.py
│   ├─ outline\_agent.py
│   └─ draft\_agent.py
├─ tools/                  # 共通ユーティリティ
│   ├─ db\_tools.py
│   └─ gemini\_tool.py
├─ articles/               # ← 本MVPで生成する .md ファイル置き場
├─ run.py                  # エントリポイント
├─ .env
└─ requirements.txt

```

---

## 4. .env サンプル（環境変数）

```dotenv
# OpenAI
OPENAI_API_KEY=sk-xxxxx
OPENAI_API_BASE=https://api.openai.com/v1

# Gemini
GEMINI_API_KEY=xyz-xxxxx

# MySQL
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=ai_writer
DB_PASSWORD=ai_writer_pwd
DB_NAME=ai_writer_db

```

---

## 5. requirements.txt

```
openai-agents-python==0.5.*
mysql-connector-python
python-dotenv
requests
```

---

## 6. MySQL スキーマ

```sql
CREATE TABLE articles (
  id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  title       VARCHAR(255) NOT NULL UNIQUE,
  slug        VARCHAR(255),
  posted_at   DATETIME,
  status      ENUM('saved','error') DEFAULT 'saved'
);
```

> **留意**: バズ記事テーブル・埋め込みストアは MVP では不要。

---

## 7. エージェント定義

| Agent                 | 役割                                                   | ツール                                                                           |
| --------------------- | ------------------------------------------------------ | -------------------------------------------------------------------------------- |
| **CoordinatorAgent**  | 全体制御。各子エージェントへの handoff とファイル保存  | `handoff()` (`TitlePlannerAgent`, `OutlineAgent`, `DraftAgent`), `save_markdown` |
| **TitlePlannerAgent** | 重複しない新規タイトル生成                             | `fetch_recent_titles`, `WebSearchTool`                                           |
| **OutlineAgent**      | 見出し・要点・参考リンクを Markdown アウトラインで生成 | `WebSearchTool`                                                                  |
| **DraftAgent**        | Gemini 2.5 を呼び出し本文を生成                        | `gemini_generate`                                                                |

### 7.1 ツール関数概要

| function_tool                     | 引数                      | 戻り値     | 説明                                      |
| --------------------------------- | ------------------------- | ---------- | ----------------------------------------- |
| `fetch_recent_titles(limit=50)`   | limit\:int                | List\[str] | 直近のタイトル一覧                        |
| `insert_article(title, slug)`     | title\:str, slug\:str     | なし       | DB へメタ登録                             |
| `gemini_generate(title, outline)` | title\:str, outline\:str  | str        | Gemini API 呼び出し                       |
| `save_markdown(title, markdown)`  | title\:str, markdown\:str | slug\:str  | ファイルを `articles/` に保存し slug 返却 |

> **slug**: 半角英数字+ハイフンで生成（例: `tips-for-vibe-coding`）

---

## 8. 処理シーケンス（1 本生成）

1. **TitlePlannerAgent**

   - `fetch_recent_titles` → `WebSearchTool` で技術系バズ検索
   - LLM により重複・クリック率重視タイトルを出力

2. **OutlineAgent**

   - 入力: タイトル
   - LLM が Markdown アウトラインを生成（H2/H3 + bullet + 外部リンク）

3. **DraftAgent**

   - `gemini_generate` を呼び、導入 300-500 字／本文 1.5-3k 字／まとめ 200-500 字

4. **CoordinatorAgent**

   - `save_markdown` で `articles/YYYY-MM-DD_HH-slug.md` へ保存
   - `insert_article` で DB 登録
   - 最終 slug を標準出力（cron ログに残す）

---

## 9. save_markdown 仕様

```python
# 保存パス
path = f"articles/{now:%Y-%m-%d_%H}-{slug}.md"

# ファイル先頭に YAML front-matter を挿入
---
title: "{{title}}"
created: "{{now.isoformat()}}"
---

{{markdown_body}}
```

- 同名ファイルが存在する場合は末尾に `_1`, `_2` … を付与し衝突回避。
- 書き込み後、`slug` を返す。

---

## 10. cron 設定例

```
0 9-18 * * * /usr/bin/python3 /path/to/ai_writer/run.py >> /var/log/ai_writer.log 2>&1
```

---

## 11. 受け入れ基準

- `articles/` に **1 時間につき 1 本**の `.md` ファイルが生成される
- Markdown 内の日本語文字数が 2,000〜4,000 字程度
- H2 (`##`) 見出しが最低 3 つ含まれる
- 外部リンクが 2 件以上含まれる
- `.env` 設定のみで他ファイルの修正なく動作
- 実行エラー時は例外を吐いて終了コード `1` を返す

---

## 12. 今後の拡張インターフェイス

- `PostingAgent` 追加 → note など外部サービス投稿
- Guardrail 実装 (`agents.Guardrail`) → 文字数・NG ワード検査
- タイトル生成アルゴリズムをベクトル類似度へ置換
- Tracing → Langfuse / OpenTelemetry

## 13. ファイル実装テンプレート

以下を **そのままコピー＆ペースト** すれば `ai_writer/` 直下に配置できる。  
（すでに存在しているファイルは上書きしてよい）

【重要!!!】以下のコードはあくまでもサンプルです。OpenAI などの公式 SDK リファレンスを参照に正確なコードを書いてください。

### 13.1 run.py

```python
import asyncio, datetime as dt, os, sys, logging
from dotenv import load_dotenv
from agents.coordinator import CoordinatorAgent
from openai_agents import Runner   # パッケージ名は openai-agents-python

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

async def main() -> None:
    now = dt.datetime.now()
    if 9 <= now.hour <= 18:
        result = await Runner.run(CoordinatorAgent(), "")
        logging.info("Markdown saved, slug=%s", result.final_output)
    else:
        logging.info("Outside posting window, skip")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        logging.exception("fatal error")
        sys.exit(1)
```

### 13.2 agents/\_\_init\_\_.py

```python
# 空でも可。パッケージ解決用
```

### 13.3 agents/coordinator.py

```python
from openai_agents import Agent, handoff
from tools.file_tools import save_markdown
from tools.db_tools import insert_article
from .title_planner import TitlePlannerAgent
from .outline_agent import OutlineAgent
from .draft_agent import DraftAgent

class CoordinatorAgent(Agent):
    name = "Coordinator"
    instructions = "記事生成ワークフローの統括役。子エージェントを順に呼び、最終 slug を返せ。"
    handoffs = [
        handoff(TitlePlannerAgent()),
        handoff(OutlineAgent()),
        handoff(DraftAgent()),
    ]
    tools = [save_markdown, insert_article]

    async def run(self, _input: str = "") -> str:
        title = await self.tools.transfer_to_title_planner()
        outline = await self.tools.transfer_to_outline_agent(title=title)
        md = await self.tools.transfer_to_draft_agent(title=title, outline=outline)

        slug = await save_markdown(title, md)
        await insert_article(title, slug)
        return slug
```

### 13.4 agents/title_planner.py

```python
from openai_agents import Agent
from tools.db_tools import fetch_recent_titles
from tools.web_tools import web_search

class TitlePlannerAgent(Agent):
    name = "TitlePlannerAgent"
    tools = [fetch_recent_titles, web_search]
    instructions = (
        "あなたはSEO最適化エディタ。"
        "【ルール】\n"
        "1. fetch_recent_titles(limit=50) で直近タイトルを取得。\n"
        "2. web_search で “生成AI コツ 初心者” などを検索。\n"
        "3. 重複せずクリックを誘う日本語タイトルを **1行だけ** 出力。\n"
        "4. 「」や記号で囲わず生の文字列で返答。"
    )
```

### 13.5 agents/outline_agent.py

```python
from openai_agents import Agent
from tools.web_tools import web_search

class OutlineAgent(Agent):
    name = "OutlineAgent"
    tools = [web_search]
    instructions = (
        "あなたは技術ブログライター。\n"
        "与えられたタイトルに対し Markdown アウトラインを作る。\n\n"
        "【アウトライン仕様】\n"
        "- 冒頭に ## 導入\n"
        "- その後 ## 見出し を3~5個\n"
        "  - 各H2の下に bullet で要点3行以内\n"
        "- 最後に ## まとめ\n"
        "- 外部リンクは `[テキスト](URL)` 形式で bullet 内に含める\n"
        "- コードを紹介したい場合は `### コード例` として囲むが、本文生成側に任せても可\n"
        "- 全体で 120 行を超えない\n"
    )
```

### 13.6 agents/draft_agent.py

```python
from openai_agents import Agent
from tools.gemini_tool import gemini_generate

class DraftAgent(Agent):
    name = "DraftAgent"
    tools = [gemini_generate]
    instructions = (
        "あなたはプロのテクライター。gemini_generate を呼び出し、"
        "300~500字導入・1,500~3,000字本文・200~500字まとめのMarkdown記事を生成し返せ。"
        "## ライターとしてのパーソナリティ"
        "- あなたは25歳の女子エンジニアです。マイクロソフトの千代田まどかさんの様なインフルエンサーです"
        "- 初心者目線で、優しい言葉と改行やわかりやすい絵文字を使用します"
    )
```

### 13.7 tools/db_tools.py

```python
from typing import List
import mysql.connector, os
from openai_agents import function_tool

def _conn():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
    )

@function_tool
def fetch_recent_titles(limit: int = 50) -> List[str]:
    """Return recent article titles newest first."""
    with _conn() as con, con.cursor() as cur:
        cur.execute("SELECT title FROM articles ORDER BY posted_at DESC LIMIT %s", (limit,))
        return [r[0] for r in cur.fetchall()]

@function_tool
def insert_article(title: str, slug: str):
    with _conn() as con, con.cursor() as cur:
        cur.execute(
            "INSERT INTO articles(title, slug, posted_at, status) VALUES(%s,%s,NOW(),'saved')",
            (title, slug),
        )
        con.commit()
```

### 13.8 tools/web_tools.py

```python
from openai_agents.tools import WebSearchTool
web_search = WebSearchTool()
```

### 13.9 tools/gemini_tool.py

```python
import os, requests, uuid
from openai_agents import function_tool

@function_tool
def gemini_generate(title: str, outline: str) -> str:
    """Generate markdown article via Gemini 2.5."""
    endpoint = "https://generativelanguage.googleapis.com/v1beta/models/generateContent"
    key = os.getenv("GEMINI_API_KEY")
    payload = {
        "model": "gemini-2.5-pro-preview-05-06",
        "contents": [
            {"role": "user", "parts": [
                f"タイトル: {title}\n\nアウトライン:\n{outline}\n\n"
                "導入:300-500字 本文:1500-3000字 まとめ:200-500字 のMarkdown記事を書け。"
            ]}
        ]
    }
    r = requests.post(f"{endpoint}?key={key}", json=payload, timeout=60)
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]
```

### 13.10 tools/file_tools.py

```python
import os, re, datetime as dt, itertools, pathlib
from openai_agents import function_tool

_articles_root = pathlib.Path(__file__).resolve().parent.parent / "articles"
_articles_root.mkdir(exist_ok=True)

def _slugify(text: str) -> str:
    slug = re.sub(r"[^\w\-]+", "-", text.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug[:80] or "article"

@function_tool
def save_markdown(title: str, markdown: str) -> str:
    """Save markdown to articles/ and return slug"""
    now = dt.datetime.now()
    slug_base = _slugify(title)
    for i in itertools.count():
        slug = slug_base if i == 0 else f"{slug_base}_{i}"
        fname = _articles_root / f"{now:%Y-%m-%d_%H}-{slug}.md"
        if not fname.exists():
            front = f"---\ntitle: \"{title}\"\ncreated: \"{now.isoformat()}\"\n---\n\n"
            with open(fname, "w", encoding="utf-8") as f:
                f.write(front + markdown.lstrip())
            return slug
    raise RuntimeError("Failed to create unique filename")
```

---

## 14. セットアップ手順

1. **リポジトリ配置**

   ```bash
   git clone <this-project> ai_writer
   cd ai_writer
   ```

2. **Python 環境**

   ```bash
   pyenv install 3.11.9        # 任意
   pyenv local 3.11.9
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **.env 設定**
   `.env.example` をコピーしキー・DB パラメータを記入。

4. **MySQL テーブル作成**

   ```bash
   mysql -u root < schema.sql
   ```

5. **初回テスト**

   ```bash
   python run.py   # 1本生成 → articles/ に MD 出力
   ```

6. **cron 登録**

   ```bash
   (crontab -l; echo "0 9-18 * * * /path/to/.venv/bin/python /path/to/ai_writer/run.py") | crontab -
   ```

---

## 15. 単体テスト例（pytest）

```python
def test_slug():
    from tools.file_tools import _slugify
    assert _slugify("Hello World!") == "hello-world"
    assert _slugify("日本語タイトル") != ""
```

---

## 16. 運用・監視 Tips

- **ログローテート**: `/var/log/ai_writer.log` を `logrotate` 週次で圧縮。
- **失敗検知**: cron で `MAILTO=you@example.com` を設定しエラー時に通知。
- **DB バックアップ**: `mysqldump --single-transaction ai_writer_db > backup.sql`.

---

## 17. よくあるトラブルシューティング

| 症状                                            | 原因                  | 対処                        |
| ----------------------------------------------- | --------------------- | --------------------------- |
| `mysql.connector.errors.ProgrammingError: 1146` | テーブル未作成        | `schema.sql` を適用         |
| `openai.error.AuthenticationError`              | OPENAI_API_KEY 未設定 | `.env` を見直し             |
| Gemini 403                                      | 日次上限超過          | 翌日まで待つか API キー確認 |
| `SSL: CERTIFICATE_VERIFY_FAILED`                | 古い OpenSSL          | python を 3.11+ に更新      |

---

## 18. ロードマップ

1. **v0.2** – Guardrail 導入（文字数・リンク検査）
2. **v0.3** – Playwright PostingAgent 追加 → note 自動公開
3. **v0.4** – Langfuse Tracing + Prometheus メトリクス
4. **v1.0** – CLI でジャンル指定投稿／並列生成モード

以上
