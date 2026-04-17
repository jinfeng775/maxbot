"""Web 搜索和抓取工具"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

from maxbot.tools._registry import registry


@registry.tool(name="web_search", description="搜索互联网（需要 BRAVE_API_KEY 或直接用 DuckDuckGo）")
def web_search(query: str, count: int = 5) -> str:
    # 优先用 Brave Search
    brave_key = os.getenv("BRAVE_API_KEY")
    if brave_key:
        return _brave_search(query, count, brave_key)
    # 回退到 DuckDuckGo Instant Answer
    return _ddg_search(query, count)


def _brave_search(query: str, count: int, api_key: str) -> str:
    url = f"https://api.search.brave.com/res/v1/web/search?q={urllib.parse.quote(query)}&count={count}"
    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "X-Subscription-Token": api_key,
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        results = []
        for r in data.get("web", {}).get("results", [])[:count]:
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "description": r.get("description", ""),
            })
        return json.dumps({"results": results}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def _ddg_search(query: str, count: int) -> str:
    """DuckDuckGo Instant Answer API（免费，无 key）"""
    url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json&no_html=1"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MaxBot/0.1"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        results = []
        if data.get("AbstractText"):
            results.append({"title": data.get("Heading", ""), "text": data["AbstractText"], "source": data.get("AbstractURL", "")})
        for r in data.get("RelatedTopics", [])[:count]:
            if isinstance(r, dict) and r.get("Text"):
                results.append({"title": r.get("Text", "")[:80], "url": r.get("FirstURL", "")})
        return json.dumps({"results": results[:count]}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@registry.tool(name="web_fetch", description="抓取网页内容")
def web_fetch(url: str, max_chars: int = 20000) -> str:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MaxBot/0.1"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read().decode("utf-8", errors="replace")
        # 简单去 HTML 标签
        import re
        text = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return json.dumps({
            "url": url,
            "content": text[:max_chars],
            "truncated": len(text) > max_chars,
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e), "url": url}, ensure_ascii=False)
