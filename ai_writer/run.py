"""
AI記事生成システム - メイン実行ファイル

このファイルは OpenAI Agents SDK を使用したマルチエージェント記事生成システムの
メインエントリーポイントです。

主な機能:
- マルチエージェントワークフローの実行
- 詳細なトレーシング機能
- 記事ファイルの自動保存
- データベースへの記事情報登録
- 営業時間制御（9:00-18:00）

使用例:
    python run.py
"""

import datetime as dt
import os
import sys
import logging
import re
from dotenv import load_dotenv
from ai_agents.coordinator import coordinator_agent
from agents import Runner, trace
from tracing_config import get_run_config, log_trace_info, log_trace_completion

# 環境変数を読み込み
load_dotenv()

# ログ設定
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s %(levelname)s: %(message)s"
)

def save_markdown_direct(title: str, markdown: str) -> dict:
    """
    記事をMarkdownファイルとして保存します。
    
    この関数はエージェントツールを使用せず、直接ファイル操作を行います。
    重複ファイル名の回避とslug生成も自動的に処理されます。
    
    Args:
        title (str): 記事のタイトル
        markdown (str): 記事の本文（Markdown形式）
    
    Returns:
        dict: 保存結果の情報
            - file_path (str): 保存されたファイルのパス
            - slug (str): 生成されたslug
            - file_size (int): ファイルサイズ（バイト）
    """
    import pathlib
    import itertools
    
    def _slugify(text: str) -> str:
        """テキストをURL安全なslugに変換"""
        slug = re.sub(r"[^\w\-]+", "-", text.lower()).strip("-")
        slug = re.sub(r"-{2,}", "-", slug)
        return slug[:80] or "article"
    
    # 保存先ディレクトリの作成
    articles_root = pathlib.Path(__file__).resolve().parent / "articles"
    articles_root.mkdir(exist_ok=True)
    
    # ファイル名の生成
    now = dt.datetime.now()
    slug = _slugify(title)
    
    # 重複ファイル名の回避
    counter = itertools.count(1)
    original_slug = slug
    
    while True:
        fname = articles_root / f"{now.strftime('%Y-%m-%d_%H')}-{slug}.md"
        if not fname.exists():
            break
        slug = f"{original_slug}-{next(counter)}"
    
    # ファイルの保存
    fname.write_text(markdown, encoding="utf-8")
    file_size = fname.stat().st_size
    
    logging.info(f"記事を保存しました: {fname}")
    
    return {
        "file_path": str(fname),
        "slug": slug,
        "file_size": file_size
    }

def insert_article_direct(title: str, slug: str) -> dict:
    """
    記事情報をデータベースに登録します。
    
    この関数はエージェントツールを使用せず、直接データベース操作を行います。
    データベース接続エラーの場合は警告ログを出力して継続します。
    
    Args:
        title (str): 記事のタイトル
        slug (str): 記事のslug
    
    Returns:
        dict: 登録結果の情報
            - status (str): 'success' または 'error'
            - article_id (int): 登録されたレコードのID（成功時のみ）
            - error (str): エラーメッセージ（失敗時のみ）
    """
    try:
        import mysql.connector
        from mysql.connector import Error
        
        # データベース接続設定
        config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': int(os.getenv('DB_PORT', 3306)),
            'user': os.getenv('DB_USER'),
            'password': os.getenv('DB_PASSWORD'),
            'database': os.getenv('DB_NAME'),
            'charset': 'utf8mb4'
        }
        
        # 必要な設定が不足している場合はスキップ
        if not all([config['user'], config['password'], config['database']]):
            return {
                "status": "skipped",
                "message": "Database configuration not complete"
            }
        
        # データベース接続と挿入
        with mysql.connector.connect(**config) as connection:
            with connection.cursor() as cursor:
                query = """
                INSERT INTO articles (title, slug, created_at) 
                VALUES (%s, %s, NOW())
                """
                cursor.execute(query, (title, slug))
                connection.commit()
                article_id = cursor.lastrowid
                
                return {
                    "status": "success",
                    "article_id": article_id
                }
                
    except ImportError:
        return {
            "status": "error",
            "error": "mysql-connector-python not installed"
        }
    except Error as e:
        return {
            "status": "error",
            "error": f"Database error: {str(e)}"
        }
    except Exception as e:
        return {
            "status": "error",
            "error": f"Unexpected error: {str(e)}"
        }

def extract_title_from_content(content: str) -> str:
    """
    記事コンテンツからタイトルを抽出します。
    
    この関数は生成された記事の内容から適切なタイトルを抽出し、
    ファイル名やデータベース登録に使用します。
    
    Args:
        content (str): 記事の本文コンテンツ
    
    Returns:
        str: 抽出されたタイトル、または推測されたタイトル
    """
    lines = content.strip().split('\n')
    
    # 最初のH1またはH2見出しを探す
    for line in lines[:15]:  # 最初の15行以内で探す
        line = line.strip()
        if line.startswith('# '):
            title = line[2:].strip()
            if len(title) > 5:  # 意味のあるタイトルかチェック
                return title
        elif line.startswith('## ') and not line.startswith('## 導入'):
            title = line[3:].strip()
            if len(title) > 5 and title not in ['導入', 'まとめ', '概要']:
                return title
    
    # アウトラインの場合は、内容から推測
    if '生成AI' in content and '初心者' in content:
        return "初心者向け生成AI活用ガイド"
    elif 'Python' in content and '自動化' in content:
        return "Python自動化入門ガイド"
    elif 'プログラミング' in content:
        return "プログラミング入門ガイド"
    else:
        return "技術記事"

def main() -> None:
    """
    メイン処理: 記事を1本生成してローカルに保存
    
    この関数は以下の処理を順次実行します:
    1. 営業時間チェック（9:00-18:00）
    2. マルチエージェントワークフローの実行
    3. 生成された記事の保存
    4. データベースへの記事情報登録
    5. トレーシング情報の出力
    """
    now = dt.datetime.now()
    
    # 営業時間内（9:00-18:00）のチェック
    # if 9 <= now.hour <= 18:
    if True:    # 本運用ではcronから呼び出して時間確認する
        try:
            logging.info("記事生成を開始します...")
            
            # トレーシング設定を取得
            run_config = get_run_config()
            
            # トレーシングを使用してエージェントワークフローを追跡
            with trace(
                "AI Article Generation Workflow",
                metadata={
                    "workflow_type": "article_generation",
                    "execution_time": now.strftime("%Y-%m-%d %H:%M:%S"),
                    "business_hours": "true" if 9 <= now.hour <= 18 else "false"
                }
            ) as workflow_trace:
                
                log_trace_info(workflow_trace.trace_id, "記事生成ワークフロー開始")
                
                # OpenAI Agents SDK の Runner.run_sync() を使用
                # 複数エージェントが連携して記事を生成
                result = Runner.run_sync(
                    coordinator_agent,
                    "簡単な技術記事を1本生成してください。",
                    run_config=run_config
                )
                
                # 生成された記事コンテンツを取得
                article_content = result.final_output
                
                # 記事が正常に生成されたかチェック
                if article_content and len(article_content.strip()) > 100:
                    # タイトルを抽出
                    title = extract_title_from_content(article_content)
                    
                    # ファイル保存
                    file_info = save_markdown_direct(title, article_content)
                    logging.info(f"記事を保存しました: {file_info['file_path']}")
                    
                    # データベース登録
                    db_result = insert_article_direct(title, file_info['slug'])
                    if db_result['status'] == 'success':
                        logging.info(f"データベースに登録しました: ID {db_result['article_id']}")
                    else:
                        logging.warning(f"データベース登録に失敗: {db_result.get('error', 'Unknown error')}")
                    
                    log_trace_completion(
                        workflow_trace.trace_id, 
                        f"記事生成完了: {title}",
                        {
                            "title": title,
                            "file_path": file_info['file_path'],
                            "file_size": file_info['file_size'],
                            "content_length": len(article_content)
                        }
                    )
                    
                    logging.info(f"✅ 記事生成が完了しました: {title}")
                    
                else:
                    error_msg = "記事の生成に失敗しました（内容が不十分）"
                    logging.error(error_msg)
                    log_trace_completion(workflow_trace.trace_id, error_msg, {"error": "insufficient_content"})
                    sys.exit(1)
                    
        except Exception as e:
            error_msg = f"記事生成中にエラーが発生しました: {str(e)}"
            logging.error(error_msg)
            sys.exit(1)
            
    else:
        logging.info(f"営業時間外です（現在時刻: {now.hour}時）。記事生成をスキップします。")

if __name__ == "__main__":
    main() 