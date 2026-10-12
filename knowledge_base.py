"""
knowledge_base.py — 本地知識庫（離線可查詢）

內建常見問題的標準答案。當使用者的問題命中知識庫時，
機器人可以直接回答，不依賴任何外部 AI API。

資料來源：國立東華大學官方網站
  - 通識教育中心：https://genedu.ndhu.edu.tw/
  - 東華大學首頁：https://www.ndhu.edu.tw/
"""

from typing import Dict, List

ENTRIES: List[Dict] = [
    {
        "id": "chen-wensheng",
        "title": "陳文盛 助理教授",
        "affiliation": "國立東華大學 通識教育中心",
        "keywords": [
            "陳文盛", "文盛", "wschen", "陳老師", "wensheng", "chen",
        ],
        "summary": (
            "國立東華大學通識教育中心助理教授（教學型助理教授級編制外專任教學人員），"
            "研究與教學方向為嵌入式系統、單晶片電腦、電路設計、程式設計、AI 與 IoT。"
        ),
        "fields": [
            ("職稱", "助理教授（教學型助理教授級編制外專任教學人員）"),
            ("單位", "國立東華大學 洄瀾學院 通識教育中心"),
            ("研究室", "理工二館 C306"),
            ("電話", "03-8906610"),
            ("電子郵件", "wschen@gms.ndhu.edu.tw"),
            (
                "學歷",
                "國立東華大學資訊工程學系博士（2003/9–2015/1）、碩士（1998/9–2000/6）；"
                "國立臺灣科技大學電子工程技術系學士（1996/9–1998/6）",
            ),
            (
                "經歷",
                "2017 年至今 台灣東部地震中心專案研究員；2000–2014 大漢技術學院講師",
            ),
            (
                "開設課程",
                "初級程式設計-Python、初級程式設計-Scratch 與 Python、"
                "中級程式設計-Python、資訊科技與應用",
            ),
            (
                "研究領域",
                "嵌入式系統、單晶片電腦、電路設計、程式設計、AI、IoT、"
                "紅外線熱顯影人臉辨識、YOLO 物件追蹤",
            ),
            (
                "博士論文",
                "基於服務品質感知動態整合與應用導向事件處理之 RFID 資料管理研究"
                "（指導教授：吳秀陽博士）",
            ),
            (
                "碩士論文",
                "利用語音介面擷取影像資料庫之模組化架構（指導教授：吳秀陽博士）",
            ),
        ],
        "source": "https://genedu.ndhu.edu.tw/p/412-1076-18517.php?Lang=zh-tw",
    },
    {
        "id": "ndhu",
        "title": "國立東華大學",
        "affiliation": "國立東華大學",
        "keywords": [
            "東華大學", "東華", "NDHU", "ndhu", "國立東華",
            "National Dong Hwa University", "ndhu.edu.tw",
        ],
        "summary": (
            "國立東華大學（National Dong Hwa University，NDHU），位於花蓮縣壽豐鄉，"
            "成立於 1994 年，為花蓮地區最重要的綜合型國立大學。"
        ),
        "fields": [
            ("全名", "國立東華大學（National Dong Hwa University，NDHU）"),
            ("地址", "花蓮縣壽豐鄉大學路二段一號"),
            ("成立年份", "1994 年"),
            ("英文縮寫", "NDHU"),
            ("官方網站", "https://www.ndhu.edu.tw/"),
        ],
        "source": "https://www.ndhu.edu.tw/",
    },
    {
        "id": "genedu-center",
        "title": "通識教育中心",
        "affiliation": "國立東華大學 洄瀾學院",
        "keywords": [
            "通識教育中心", "通識中心", "通識", "genedu", "洄瀾學院",
            "通識課程", "通識教育",
        ],
        "summary": (
            "國立東華大學通識教育中心隸屬洄瀾學院，負責規劃與推動全校通識課程，"
            "提供多元化的跨領域學習機會。"
        ),
        "fields": [
            ("所屬學院", "洄瀾學院"),
            ("主要功能", "負責全校通識課程規劃與推動"),
            ("網站", "https://genedu.ndhu.edu.tw/"),
        ],
        "source": "https://genedu.ndhu.edu.tw/",
    },
]

# 命中門檻：關鍵字越長權重越高，分數達到此值即視為有效命中
MATCH_THRESHOLD = 3


def search_kb(query: str, limit: int = 3) -> List[Dict]:
    """以關鍵字比對搜尋知識庫，回傳分數由高到低的條目（含 score 欄位）。"""
    q = query.strip()
    if not q:
        return []

    scored: List[tuple] = []
    for entry in ENTRIES:
        score = 0
        for keyword in entry["keywords"]:
            if keyword in q:
                score += len(keyword)  # 關鍵字越長，權重越高
        for _field_name, value in entry["fields"]:
            if q in value:
                score += 2
        if score > 0:
            scored.append((score, entry))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [{**entry, "score": score} for score, entry in scored[:limit]]


def is_strong_match(query: str) -> bool:
    """判斷問題是否明確命中知識庫（用於自動回覆）。"""
    hits = search_kb(query, limit=1)
    return bool(hits) and hits[0]["score"] >= MATCH_THRESHOLD


def format_entry(entry: Dict) -> str:
    """將知識庫條目格式化為 LINE 訊息文字。"""
    lines = [f"📚 {entry['title']} — {entry['affiliation']}", ""]
    for field_name, value in entry["fields"]:
        lines.append(f"• {field_name}：{value}")
    lines.append("")
    lines.append(f"來源：{entry['source']}")
    return "\n".join(lines)
