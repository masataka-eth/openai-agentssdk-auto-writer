"""
Coordinator - マルチエージェント記事生成システムの統括エージェント

このファイルは OpenAI Agents SDK を使用したマルチエージェントシステムの
中核となるコーディネーターエージェントを定義します。

システム構成:
1. Coordinator: 全体の流れを管理
2. TitlePlannerAgent: SEO最適化タイトル生成
3. OutlineAgent: 記事構造設計
4. DraftAgent: 本文生成（Gemini API + Grounding）

ワークフロー:
Coordinator → TitlePlanner → Outline → Draft → 完了
"""

from agents import Agent
from tools.file_tools import save_markdown
from tools.db_tools import insert_article, fetch_recent_titles
from tools.web_tools import web_search
from tools.gemini_tool import gemini_generate
from .title_planner import create_title_planner_agent
from .outline_agent import create_outline_agent
from .draft_agent import create_draft_agent

def create_article_generation_agents():
    """
    記事生成システムの全エージェントを作成し、ハンドオフ関係を設定します。
    
    このシステムは以下の流れで動作します:
    1. Coordinator が TitlePlannerAgent にハンドオフ
    2. TitlePlannerAgent が OutlineAgent にハンドオフ
    3. OutlineAgent が DraftAgent にハンドオフ
    4. DraftAgent が記事本文を生成して完了
    
    Returns:
        tuple: (coordinator_agent, title_planner_agent, outline_agent, draft_agent)
    """
    
    # 各エージェントのインスタンスを作成
    # 注意: handoffsは循環参照を避けるため、後で設定します
    title_planner_agent = create_title_planner_agent()
    outline_agent = create_outline_agent()
    draft_agent = create_draft_agent()
    
    # CoordinatorAgent: システム全体の流れを管理
    coordinator_agent = Agent(
        name="Coordinator",
        instructions=(
            "あなたは記事生成ワークフローの統括役です。\n\n"
            
            "【重要】以下の手順を必ず順番に実行してください：\n\n"
            "1. TitlePlannerAgent にハンドオフしてタイトルを生成\n"
            "   → SEO最適化されたタイトルを1つ生成\n"
            "2. タイトルが生成されたら、OutlineAgent にハンドオフしてアウトライン作成\n"
            "   → 構造化された記事の骨組みを作成\n"
            "3. アウトラインが作成されたら、DraftAgent にハンドオフして記事本文生成\n"
            "   → Gemini APIで高品質な記事本文を生成\n"
            "4. DraftAgentから記事本文を受け取ったら、その内容をそのまま返す\n"
            "   → 生成された記事コンテンツを出力\n\n"
            
            "【絶対に守ること】\n"
            "- 各ステップは1回ずつのみ実行してください\n"
            "  → 無限ループを避けるため\n"
            "- DraftAgentから記事本文を受け取ったら、その内容をそのまま出力してください\n"
            "  → 追加の編集や処理は不要\n"
            "- ファイル保存やデータベース操作は行いません\n"
            "  → これらは外部システムが担当\n"
            "- 記事コンテンツの生成のみに専念してください\n"
            "  → 役割分担を明確に\n\n"
            
            "まず TitlePlannerAgent にハンドオフしてください。"
        ),
        handoffs=[title_planner_agent, outline_agent, draft_agent],
        tool_use_behavior="run_llm_again",  # ツール実行後にLLMを再実行
    )
    
    # ハンドオフ関係を設定（循環参照を避けるため、ここで設定）
    title_planner_agent.handoffs = [outline_agent]
    outline_agent.handoffs = [draft_agent]
    # draft_agentは最終段階なのでhandoffsは設定しません
    
    return coordinator_agent, title_planner_agent, outline_agent, draft_agent


# システムのエントリーポイント
# 他のモジュールからインポートして使用します
coordinator_agent, title_planner_agent, outline_agent, draft_agent = create_article_generation_agents() 