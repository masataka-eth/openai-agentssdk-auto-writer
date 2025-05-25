"""
OpenAI Agents SDK トレーシング設定
"""
import os
import logging
from agents import RunConfig, set_tracing_export_api_key, enable_verbose_stdout_logging

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

def setup_tracing():
    """
    トレーシングの初期設定を行う
    """
    # OpenAI API キーの確認
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        logging.warning("⚠️ OPENAI_API_KEY が設定されていません")
        return False
    
    # トレーシング用のAPI キーを明示的に設定
    set_tracing_export_api_key(openai_api_key)
    logging.info(f"🔑 トレーシング用API キー設定完了: {openai_api_key[:10]}...")
    
    # 詳細ログを有効化
    enable_verbose_stdout_logging()
    logging.info("📝 詳細ログを有効化しました")
    
    return True

def get_run_config() -> RunConfig:
    """
    トレーシング設定を含むRunConfigを取得
    """
    # トレーシングの初期設定
    if not setup_tracing():
        logging.error("❌ トレーシング設定に失敗しました")
    
    # 環境変数でトレーシングを無効化できる
    tracing_disabled = os.getenv("OPENAI_AGENTS_DISABLE_TRACING", "0") == "1"
    
    # センシティブデータの記録を制御
    include_sensitive_data = os.getenv("TRACE_INCLUDE_SENSITIVE_DATA", "1") == "1"
    
    config = RunConfig(
        tracing_disabled=tracing_disabled,
        trace_include_sensitive_data=include_sensitive_data,
    )
    
    if not tracing_disabled:
        logging.info("🔍 トレーシングが有効です")
        logging.info(f"📊 センシティブデータ記録: {'有効' if include_sensitive_data else '無効'}")
    else:
        logging.info("🚫 トレーシングが無効化されています")
    
    return config

def log_trace_info(trace_id: str, workflow_name: str = "AI Article Generation"):
    """
    トレース情報をログに出力
    """
    logging.info(f"🔍 トレース開始: {workflow_name}")
    logging.info(f"📋 Trace ID: {trace_id}")
    logging.info(f"🌐 OpenAI Platform URL: https://platform.openai.com/traces/{trace_id}")
    
def log_trace_completion(trace_id: str, success: bool = True):
    """
    トレース完了情報をログに出力
    """
    status = "✅ 成功" if success else "❌ 失敗"
    logging.info(f"🔍 トレース完了: {status}")
    logging.info(f"📋 Trace ID: {trace_id}")
    logging.info(f"🌐 詳細確認: https://platform.openai.com/traces/{trace_id}") 