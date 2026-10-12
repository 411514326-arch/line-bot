"""
websearch.py — 網頁搜尋（多引擎容錯，免 API 金鑰）

依序嘗試多個免費搜尋來源，回傳第一個有結果的引擎：
1. DuckDuckGo HTML（html.duckduckgo.com）
2. Bing RSS（format=rss，純 XML 易解析）
3. SearXNG 公開實例（JSON）

在 LINUX/家用網路環境下通常第一個引擎即可成功；
若某引擎被反爬蟲機制攔截，會自動 fallback 到下一個。
"""

import logging
import re
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

_TIMEOUT = 15

SEARX_INSTANCES = [
    "https://searx.be",
    "https://priv.au",
    "https://searx.tiekoetter.com",
    "https://opnxng.com",
]


# ================= 引擎一：DuckDuckGo HTML =================

def _ddg_search(query: str, max_results: int) -> List[Dict[str, str]]:
    url = "https://html.duckduckgo.com/html/?" + urlencode({"q": query})
    res = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
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


# ================= 引擎二：Bing RSS =================

def _bing_rss_search(query: str, max_results: int) -> List[Dict[str, str]]:
    url = "https://www.bing.com/search?" + urlencode(
        {"q": query, "format": "rss"}
    )
    res = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
    res.raise_for_status()
    xml = res.text

    results: List[Dict[str, str]] = []
    for item in re.findall(r"<item>(.*?)</item>", xml, re.DOTALL):
        title_m = re.search(r"<title>(.*?)</title>", item, re.DOTALL)
        link_m = re.search(r"<link>(.*?)</link>", item, re.DOTALL)
        if title_m and link_m:
            title = re.sub(r"<[^>]+>", "", title_m.group(1)).strip()
            link = re.sub(r"<[^>]+>", "", link_m.group(1)).strip()
            if title and link.startswith("http"):
                results.append({"title": title, "url": link})
        if len(results) >= max_results:
            break
    return results


# ================= 引擎三：SearXNG 公開實例 =================

def _searx_search(query: str, max_results: int) -> List[Dict[str, str]]:
    for base in SEARX_INSTANCES:
        try:
            url = base + "/search?" + urlencode({"q": query, "format": "json"})
            res = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
            if res.status_code != 200:
                continue
            data = res.json()
            results: List[Dict[str, str]] = []
            for item in data.get("results", []):
                title = (item.get("title") or "").strip()
                url_ = (item.get("url") or "").strip()
                if title and url_:
                    results.append({"title": title, "url": url_})
                if len(results) >= max_results:
                    break
            if results:
                return results
        except Exception as e:
            logger.debug(f"SearXNG 實例 {base} 失敗: {e}")
            continue
    return []


# ================= 統一入口 =================

_ENGINES = (_ddg_search, _bing_rss_search, _searx_search)


def web_search(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """依序嘗試各搜尋引擎，回傳第一個有結果的（無結果回傳空列表）。"""
    for engine in _ENGINES:
        try:
            results = engine(query, max_results)
        except Exception as e:
            logger.warning(f"搜尋引擎 {engine.__name__} 失敗: {e}")
            continue
        if results:
            logger.info(f"搜尋引擎 {engine.__name__} 回傳 {len(results)} 筆結果")
            return results
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
