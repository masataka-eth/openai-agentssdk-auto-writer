import os
import re
import datetime as dt
import itertools
import pathlib
from agents import function_tool, custom_span

_articles_root = pathlib.Path(__file__).resolve().parent.parent / "articles"
_articles_root.mkdir(exist_ok=True)

def _slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    # 日本語文字を削除し、英数字とハイフンのみに
    slug = re.sub(r"[^\w\-]+", "-", text.lower()).strip("-")
    # 連続するハイフンを1つに
    slug = re.sub(r"-{2,}", "-", slug)
    # 長すぎる場合は切り詰め
    return slug[:80] or "article"

@function_tool
def save_markdown(title: str, markdown: str) -> str:
    """Save markdown to articles/ and return slug"""
    with custom_span("save_markdown_operation") as span:
        # OpenAI Agents SDKの正しい属性設定方法
        span.span_data.data["title"] = title
        span.span_data.data["markdown_length"] = len(markdown)
        
        now = dt.datetime.now()
        slug = _slugify(title)
        
        # 重複を避けるためのカウンター
        counter = itertools.count(1)
        original_slug = slug
        
        while True:
            fname = _articles_root / f"{now.strftime('%Y-%m-%d_%H')}-{slug}.md"
            if not fname.exists():
                break
            slug = f"{original_slug}-{next(counter)}"
        
        # YAML front-matterを含むMarkdownを作成
        content = f"""---
title: "{title}"
created: "{now.isoformat()}"
---

{markdown}
"""
        
        try:
            fname.write_text(content, encoding="utf-8")
            file_size = fname.stat().st_size
            
            # 成功時の属性を追加
            span.span_data.data["slug"] = slug
            span.span_data.data["file_path"] = str(fname)
            span.span_data.data["file_size"] = file_size
            span.span_data.data["status"] = "success"
            
            return slug
            
        except Exception as e:
            # エラー時の属性を追加
            span.span_data.data["status"] = "error"
            span.span_data.data["error"] = str(e)
            raise 