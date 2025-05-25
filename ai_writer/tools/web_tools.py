"""
Web Tools - Web検索機能ツール

このモジュールは OpenAI Agents SDK の function_tool として使用される
Web検索機能を提供します。

主な機能:
- DuckDuckGo を使用した安全なWeb検索
- 検索結果の要約とフィルタリング
- トレーシング情報の詳細記録

使用例:
    @function_tool
    def web_search(query: str) -> str:
        # エージェントから自動的に呼び出されます
"""

import requests
from agents import function_tool, custom_span


@function_tool
def web_search(query: str) -> str:
    """
    DuckDuckGo を使用してWeb検索を実行します。
    
    この関数は安全で匿名性の高いDuckDuckGo検索エンジンを使用して
    Web検索を実行し、結果を要約して返します。
    
    Args:
        query (str): 検索クエリ
    
    Returns:
        str: 検索結果の要約（最大500文字程度）
    
    Note:
        - プライバシーを重視したDuckDuckGo APIを使用
        - 検索結果は自動的にフィルタリングされます
        - トレーシング情報が詳細に記録されます
    """
    # OpenAI Agents SDK のカスタムスパンでトレーシング開始
    with custom_span("web_search_operation") as span:
        # トレーシング情報の記録
        span.span_data.data["query"] = query
        
        try:
            # DuckDuckGo Instant Answer API を使用
            # 安全で匿名性の高い検索を実現
            url = "https://api.duckduckgo.com/"
            params = {
                "q": query,
                "format": "json",
                "no_html": "1",
                "skip_disambig": "1"
            }
            
            # API リクエストの実行
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # 検索結果の処理
            results = []
            
            # Abstract（要約）の取得
            if data.get("Abstract"):
                results.append(f"概要: {data['Abstract']}")
            
            # Related Topics（関連トピック）の取得
            if data.get("RelatedTopics"):
                topics = []
                for topic in data["RelatedTopics"][:3]:  # 最大3件
                    if isinstance(topic, dict) and topic.get("Text"):
                        topics.append(topic["Text"])
                if topics:
                    results.append(f"関連情報: {'; '.join(topics)}")
            
            # Answer（直接回答）の取得
            if data.get("Answer"):
                results.append(f"回答: {data['Answer']}")
            
            # 結果の統合
            if results:
                search_result = " | ".join(results)
                # 長すぎる場合は切り詰める
                if len(search_result) > 500:
                    search_result = search_result[:500] + "..."
            else:
                search_result = f"'{query}' に関する具体的な情報は見つかりませんでしたが、一般的な技術情報として参考になる内容を含めることをお勧めします。"
            
            # 成功時のトレーシング情報
            span.span_data.data["status"] = "success"
            span.span_data.data["result_length"] = len(search_result)
            span.span_data.data["has_abstract"] = bool(data.get("Abstract"))
            span.span_data.data["related_topics_count"] = len(data.get("RelatedTopics", []))
            
            return search_result
            
        except requests.exceptions.RequestException as e:
            # ネットワークエラーの処理
            error_msg = f"Web検索でネットワークエラーが発生しました: {str(e)}"
            span.span_data.data["status"] = "error"
            span.span_data.data["error"] = error_msg
            
            # エラー時はフォールバック応答を返す
            return f"'{query}' の検索中にエラーが発生しました。一般的な技術情報を参考にしてください。"
            
        except Exception as e:
            # その他のエラーの処理
            error_msg = f"Web検索で予期しないエラーが発生しました: {str(e)}"
            span.span_data.data["status"] = "error"
            span.span_data.data["error"] = error_msg
            
            # エラー時はフォールバック応答を返す
            return f"'{query}' の検索中にエラーが発生しました。一般的な技術情報を参考にしてください。" 