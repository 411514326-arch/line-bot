"""
websearch.py — 網頁搜尋（使用 DuckDuckGo HTML 介面，無需 API 金鑰）

讓 LINE Bot 具備即時網頁搜尋能力，可用於查詢新聞、人物、學術資訊等。
"""

import logging
import re
import time
from typing import Dict, List
from urllib.parse import parse_qs, unquote, urlencode, urlparse

import requests

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}


def web_search(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """使用 DuckDuckGo HTML 介面搜尋，回傳 [{title, url}]。最多重試 2 次。"""
    max_retries = 2
    last_error: Exception = Exception("未知錯誤")
    for attempt in range(max_retries + 1):
        try:
            url = "https://html.duckduckgo.com/html/?" + urlencode({"q": query})
            res = requests.get(url, headers=_HEADERS, timeout=15)
            res.raise_for_status()
            html = res.text

            pattern = re.compile(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>')
            results: List[Dict[str, str]] = []
            for href, title in pattern.findall(html):
                title = re.sub(r"<[^>]+>", "", title).strip()
                # DuckDuckGo 使用導向連結，從 uddg 參數還原真實網址
                qs = parse_qs(urlparse(href).query)
                real_url = unquote(qs["uddg"][0]) if qs.get("uddg") else href
                if title and real_url:
                    results.append({"title": title, "url": real_url})
                if len(results) >= max_results:
                    break
            return results
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                logger.warning(f"網頁搜尋失敗（第 {attempt + 1} 次），1 秒後重試: {e}")
                time.sleep(1)
    logger.warning(f"網頁搜尋最終失敗: {last_error}")
    return []


def format_results(query: str, results: List[Dict[str, str]]) -> str:
    """將搜尋結果格式化為 LINE 訊息文字。"""
    if not results:
        return f"🔍 找不到「{query}」的搜尋結果，可能是網路或搜尋服務暫時異常。"
    lines = [f"🔍「{query}」的搜尋結果：", ""]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['title']}")
        lines.append(f"   {r['url']}")
    return "\n".join(lines)
