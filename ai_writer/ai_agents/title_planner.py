"""
TitlePlannerAgent - SEO最適化記事タイトル生成エージェント

このエージェントは技術記事のタイトルを企画・生成する専門エージェントです。
OpenAI Agents SDKを使用したマルチエージェントシステムの一部として動作します。

主な機能:
- 既存記事タイトルの重複チェック
- Web検索による最新トレンド調査
- SEO最適化されたタイトル生成
- OutlineAgentへの自動ハンドオフ
"""

from agents import Agent
from tools.db_tools import fetch_recent_titles
from tools.web_tools import web_search


def create_title_planner_agent() -> Agent:
    """
    TitlePlannerAgentのインスタンスを作成します。
    
    このエージェントは以下の手順でタイトルを生成します:
    1. データベースから既存タイトルを取得して重複を避ける
    2. Web検索で最新のトレンドを調査
    3. SEO最適化されたタイトルを1つ生成
    4. OutlineAgentにハンドオフしてアウトライン作成を依頼
    
    Returns:
        Agent: 設定済みのTitlePlannerAgentインスタンス
    """
    return Agent(
        name="TitlePlannerAgent",
        instructions=(
            "あなたはSEO最適化エディタです。技術系記事のタイトルを企画します。\n\n"
            
            "【実行手順】\n"
            "1. fetch_recent_titles(limit=50) で直近タイトルを取得\n"
            "   → 重複を避けるため、既存記事のタイトルを確認\n"
            "2. web_search で「生成AI コツ 初心者」「プログラミング 入門」「開発 効率化」などを検索\n"
            "   → 最新のトレンドや人気キーワードを調査\n"
            "3. 重複せずクリックを誘う日本語タイトルを **1行だけ** 生成\n"
            "   → SEO効果とユーザビリティを両立\n"
            "4. タイトル生成完了後、必ずOutlineAgentにハンドオフ\n"
            "   → 次のステップ（アウトライン作成）に進む\n\n"
            
            "【タイトル要件】\n"
            "- 「」や記号で囲わず生の文字列で出力\n"
            "- 初心者向けで親しみやすく、実用的な内容を示す\n"
            "- 30文字以内で簡潔に（検索結果での表示を考慮）\n"
            "- 数字や具体的な表現を含める（例：「5選」「完全ガイド」）\n\n"
            
            "【タイトル例】\n"
            "- 初心者でもできるPython自動化術5選\n"
            "- VSCodeを使いこなすための便利な拡張機能10選\n"
            "- Git初心者が知っておくべき基本コマンド完全ガイド\n"
            "- ChatGPTを活用したコーディング効率化テクニック\n\n"
            
            "【重要】タイトル生成が完了したら、必ずOutlineAgentにハンドオフしてアウトライン作成を依頼してください。"
        ),
        tools=[fetch_recent_titles, web_search],
        # handoffsは後でcoordinator.pyで設定されます（循環参照を避けるため）
    ) 