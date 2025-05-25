"""
Gemini Tool - Google Gemini API を使用した記事生成ツール

このツールは Google の Gemini API を使用して高品質な技術記事を生成します。
OpenAI Agents SDK の function_tool デコレータを使用してエージェントから呼び出し可能です。

主な機能:
- Gemini 2.5 Pro による高品質な記事生成
- Web Grounding 機能による最新情報の取得
- タイムアウト処理とフォールバック機能
- 詳細なトレーシング情報の記録

使用例:
    @function_tool
    def gemini_generate(title: str, outline: str) -> str:
        # エージェントから自動的に呼び出されます
"""

import os
import requests
import time
from agents import function_tool, custom_span

@function_tool
def gemini_generate(title: str, outline: str) -> str:
    """
    Google Gemini API を使用してMarkdown記事を生成します。
    
    この関数は以下の高度な機能を提供します:
    - Web Grounding: リアルタイムのWeb検索結果を活用
    - フォールバック機能: 複数のモデルを順次試行
    - タイムアウト処理: 長時間の処理を適切に管理
    - トレーシング: 詳細な実行情報を記録
    
    Args:
        title (str): 記事のタイトル
        outline (str): 記事のアウトライン（Markdown形式）
    
    Returns:
        str: 生成されたMarkdown記事の本文
    
    Raises:
        ValueError: API キーが設定されていない場合、または全てのモデルで失敗した場合
    """
    with custom_span("gemini_generate_operation") as span:
        span.span_data.data["title"] = title
        span.span_data.data["outline_length"] = len(outline)
        
        key = os.getenv("GEMINI_API_KEY")
        
        if not key:
            span.span_data.data["status"] = "error"
            span.span_data.data["error"] = "GEMINI_API_KEY not found"
            raise ValueError("GEMINI_API_KEY environment variable is required")
        
        # モデル設定（プライマリとフォールバック）
        models = [
            {
                "name": "gemini-2.5-pro-preview-05-06",
                "timeout": 300,  # 300秒に延長
                "max_tokens": 4000,
                "supports_grounding": True
            },
            {
                "name": "gemini-1.5-pro",  # フォールバックモデル
                "timeout": 120,
                "max_tokens": 4000,
                "supports_grounding": True
            }
        ]
        
        span.span_data.data["models_to_try"] = len(models)
        span.span_data.data["grounding_enabled"] = True
        
        for attempt, model_config in enumerate(models, 1):
            model_name = model_config["name"]
            timeout = model_config["timeout"]
            max_tokens = model_config["max_tokens"]
            supports_grounding = model_config.get("supports_grounding", False)
            
            endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
            
            span.span_data.data[f"attempt_{attempt}_model"] = model_name
            span.span_data.data[f"attempt_{attempt}_timeout"] = timeout
            span.span_data.data[f"attempt_{attempt}_grounding"] = supports_grounding
            span.span_data.data["api_endpoint"] = endpoint
            span.span_data.data["temperature"] = 0.7
            
            # ペイロード構築
            payload = {
                "contents": [
                    {"role": "user", "parts": [{"text": f"""
以下のタイトルとアウトラインに基づいて、技術記事をMarkdown形式で生成してください。

タイトル: {title}

アウトライン:
{outline}

要件:
- 2000-4000文字程度
- 初心者にもわかりやすく
- 実用的な内容
- 最新の情報を含める（Web検索結果を活用）
- コード例があれば含める
- 見出しはH2(##)以下を使用
- 導入、本文、まとめの構成
- 外部リンクや参考資料を含める
- 具体的な事例や最新のトレンドを反映

Web検索を活用して、最新の情報、統計データ、実際の事例、ツールの最新バージョン情報などを含めてください。
"""}]}
                ],
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": max_tokens,
                }
            }
            
            # Grounding設定を追加（対応モデルの場合）
            if supports_grounding:
                payload["tools"] = [
                    {
                        "googleSearchRetrieval": {
                            "dynamicRetrievalConfig": {
                                "mode": "MODE_DYNAMIC",
                                "dynamicThreshold": 0.7
                            }
                        }
                    }
                ]
                span.span_data.data[f"attempt_{attempt}_grounding_config"] = "google_search_retrieval_enabled"
            
            try:
                grounding_status = "有効" if supports_grounding else "無効"
                print(f"🤖 Gemini API 呼び出し中... (モデル: {model_name}, タイムアウト: {timeout}秒, Grounding: {grounding_status})")
                start_time = time.time()
                
                response = requests.post(
                    f"{endpoint}?key={key}",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=timeout
                )
                
                elapsed_time = time.time() - start_time
                span.span_data.data[f"attempt_{attempt}_elapsed_time"] = f"{elapsed_time:.2f}s"
                span.span_data.data["response_status_code"] = response.status_code
                
                if response.status_code == 200:
                    data = response.json()
                    if "candidates" in data and len(data["candidates"]) > 0:
                        candidate = data["candidates"][0]
                        generated_text = candidate["content"]["parts"][0]["text"]
                        
                        # Grounding情報の記録
                        if "groundingMetadata" in candidate:
                            grounding_metadata = candidate["groundingMetadata"]
                            span.span_data.data["grounding_metadata"] = {
                                "web_search_queries": grounding_metadata.get("webSearchQueries", []),
                                "grounding_chunks_count": len(grounding_metadata.get("groundingChunks", [])),
                                "search_entry_point": grounding_metadata.get("searchEntryPoint", {})
                            }
                            print(f"🔍 Web検索実行: {len(grounding_metadata.get('webSearchQueries', []))} クエリ")
                            print(f"📚 Grounding情報: {len(grounding_metadata.get('groundingChunks', []))} チャンク")
                        
                        span.span_data.data["status"] = "success"
                        span.span_data.data["successful_model"] = model_name
                        span.span_data.data["successful_attempt"] = attempt
                        span.span_data.data["generated_text_length"] = len(generated_text)
                        span.span_data.data["response_candidates_count"] = len(data["candidates"])
                        span.span_data.data["total_elapsed_time"] = f"{elapsed_time:.2f}s"
                        
                        print(f"✅ 記事生成成功 (モデル: {model_name}, 時間: {elapsed_time:.2f}秒)")
                        return generated_text
                    else:
                        error_msg = f"No candidates in response from {model_name}"
                        span.span_data.data[f"attempt_{attempt}_error"] = error_msg
                        print(f"⚠️ {error_msg}")
                        continue
                else:
                    error_msg = f"API request failed with status {response.status_code}: {response.text}"
                    span.span_data.data[f"attempt_{attempt}_error"] = error_msg
                    span.span_data.data[f"attempt_{attempt}_response_text"] = response.text
                    print(f"⚠️ {model_name} でエラー: {response.status_code}")
                    
                    # エラーレスポンスの詳細をログ出力
                    try:
                        error_data = response.json()
                        if "error" in error_data:
                            print(f"   エラー詳細: {error_data['error'].get('message', 'Unknown error')}")
                    except:
                        pass
                    continue
                    
            except requests.exceptions.Timeout:
                error_msg = f"Timeout after {timeout} seconds with {model_name}"
                span.span_data.data[f"attempt_{attempt}_error"] = error_msg
                print(f"⏰ {model_name} でタイムアウト ({timeout}秒)")
                continue
                
            except requests.exceptions.RequestException as e:
                error_msg = f"Request failed with {model_name}: {str(e)}"
                span.span_data.data[f"attempt_{attempt}_error"] = error_msg
                print(f"❌ {model_name} でリクエストエラー: {str(e)}")
                continue
        
        # すべてのモデルで失敗した場合
        final_error = "All Gemini models failed or timed out"
        span.span_data.data["status"] = "error"
        span.span_data.data["error"] = final_error
        span.span_data.data["total_attempts"] = len(models)
        raise ValueError(final_error) 