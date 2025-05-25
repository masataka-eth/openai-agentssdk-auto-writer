from typing import List
import mysql.connector
import os
from agents import function_tool, custom_span

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
    with custom_span("fetch_recent_titles_operation") as span:
        span.span_data.data["limit"] = limit
        
        try:
            with _conn() as con, con.cursor() as cur:
                cur.execute("SELECT title FROM articles ORDER BY posted_at DESC LIMIT %s", (limit,))
                titles = [r[0] for r in cur.fetchall()]
                
                span.span_data.data["titles_count"] = len(titles)
                span.span_data.data["status"] = "success"
                return titles
                
        except Exception as e:
            span.span_data.data["status"] = "error"
            span.span_data.data["error"] = str(e)
            raise

@function_tool
def insert_article(title: str, slug: str) -> bool:
    """Insert article record into database."""
    with custom_span("insert_article_operation") as span:
        span.span_data.data["title"] = title
        span.span_data.data["slug"] = slug
        
        try:
            with _conn() as con, con.cursor() as cur:
                cur.execute(
                    "INSERT INTO articles (title, slug, posted_at) VALUES (%s, %s, NOW())",
                    (title, slug)
                )
                con.commit()
                
                span.span_data.data["status"] = "success"
                span.span_data.data["rows_affected"] = cur.rowcount
                return True
                
        except Exception as e:
            span.span_data.data["status"] = "error"
            span.span_data.data["error"] = str(e)
            raise 