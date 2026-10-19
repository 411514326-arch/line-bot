"""
core/storage.py — 對話紀錄持久化儲存引擎抽象層

支援：
1. FileHistoryStorage：本機 JSON 檔案儲存（預設）
2. MemoryHistoryStorage：記憶體儲存（用於測試或純暫存）
3. FirestoreHistoryStorage：Google Cloud Firestore 雲端資料庫（預留擴充）
"""

import os
import json
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from config import CHAT_HISTORY_DIR

logger = logging.getLogger("storage")


class BaseHistoryStorage(ABC):
    """對話歷史儲存基底抽象類別"""

    @abstractmethod
    def load(self, user_id: str) -> List[Dict[str, str]]:
        """載入特定使用者的對話紀錄"""
        pass

    @abstractmethod
    def save(self, user_id: str, history: List[Dict[str, str]]) -> None:
        """儲存特定使用者的對話紀錄"""
        pass

    @abstractmethod
    def clear(self, user_id: str) -> bool:
        """清空特定使用者的對話紀錄"""
        pass


class FileHistoryStorage(BaseHistoryStorage):
    """基於檔案系統的 JSON 對話紀錄儲存（本機開發與單實例使用）"""

    def __init__(self, base_dir: str = CHAT_HISTORY_DIR):
        self.base_dir = base_dir

    def _get_path(self, user_id: str) -> Optional[str]:
        try:
            os.makedirs(self.base_dir, exist_ok=True)
            safe_name = "".join(c if c.isalnum() else "_" for c in user_id)
            return os.path.join(self.base_dir, f"{safe_name}.json")
        except Exception:
            return None

    def load(self, user_id: str) -> List[Dict[str, str]]:
        path = self._get_path(user_id)
        if path and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    return [
                        m for m in data
                        if isinstance(m, dict) and "role" in m and "content" in m
                    ]
            except Exception as e:
                logger.warning(f"無法讀取對話紀錄 {path}: {e}")
        return []

    def save(self, user_id: str, history: List[Dict[str, str]]) -> None:
        path = self._get_path(user_id)
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"無法儲存對話紀錄 {path}: {e}")

    def clear(self, user_id: str) -> bool:
        path = self._get_path(user_id)
        if path and os.path.exists(path):
            try:
                os.remove(path)
                return True
            except Exception as e:
                logger.warning(f"無法刪除對話紀錄 {path}: {e}")
        return False


class FirestoreHistoryStorage(BaseHistoryStorage):
    """
    Google Cloud Firestore 雲端對話持久化適配器（預留供 Cloud Run 多實例擴充）
    使用方式：當設定了 FIRESTORE_COLLECTION 時啟用。
    """

    def __init__(self, collection_name: str = "chat_histories"):
        self.collection_name = collection_name
        self._db = None

    def _get_db(self):
        if self._db is None:
            try:
                from google.cloud import firestore
                self._db = firestore.Client()
            except Exception as e:
                logger.warning(f"無法初始化 Firestore Client: {e}，將回退至記憶體暫存。")
        return self._db

    def load(self, user_id: str) -> List[Dict[str, str]]:
        db = self._get_db()
        if not db:
            return []
        try:
            doc_ref = db.collection(self.collection_name).document(user_id)
            doc = doc_ref.get()
            if doc.exists:
                data = doc.to_dict()
                return data.get("messages", [])
        except Exception as e:
            logger.warning(f"Firestore load 失敗 ({user_id}): {e}")
        return []

    def save(self, user_id: str, history: List[Dict[str, str]]) -> None:
        db = self._get_db()
        if not db:
            return
        try:
            doc_ref = db.collection(self.collection_name).document(user_id)
            doc_ref.set({"messages": history, "updated_at": firestore.SERVER_TIMESTAMP})
        except Exception as e:
            logger.warning(f"Firestore save 失敗 ({user_id}): {e}")

    def clear(self, user_id: str) -> bool:
        db = self._get_db()
        if not db:
            return False
        try:
            db.collection(self.collection_name).document(user_id).delete()
            return True
        except Exception as e:
            logger.warning(f"Firestore delete 失敗 ({user_id}): {e}")
            return False


# 全域儲存引擎工廠
def get_storage_engine() -> BaseHistoryStorage:
    # 若環境設定了 USE_FIRESTORE 且有專案 ID 則可切換為 Firestore，預設為檔案儲存
    if os.getenv("USE_FIRESTORE", "").lower() in ("true", "1", "yes"):
        return FirestoreHistoryStorage()
    return FileHistoryStorage()
