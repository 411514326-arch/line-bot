"""
test_web_api.py — 網頁聊天介面與 REST API 功能完整驗證
"""

import sys
import unittest
import json

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from app import app


class TestWebAPI(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.session_id = "test_web_session_999"

    def test_web_chat_page_render(self):
        """測試 GET /chat 能否正確渲染網頁聊天頁面"""
        response = self.client.get("/chat")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Antigravity", response.data)
        self.assertIn(b"messages-list", response.data)

    def test_index_browser_access(self):
        """測試瀏覽器造訪 GET / 是否能渲染網頁"""
        response = self.client.get("/", headers={"Accept": "text/html,application/xhtml+xml"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"<!DOCTYPE html>", response.data)

    def test_api_chat_empty_message(self):
        """測試 POST /api/chat 空白訊息阻擋"""
        response = self.client.post(
            "/api/chat",
            data=json.dumps({"session_id": self.session_id, "message": "   "}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data["success"])

    def test_api_chat_help_command(self):
        """測試 POST /api/chat 執行 /help 指令"""
        response = self.client.post(
            "/api/chat",
            data=json.dumps({"session_id": self.session_id, "message": "/help"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["source"], "command")
        self.assertIn("指令清單", data["reply"])

    def test_api_chat_kb_query(self):
        """測試 POST /api/chat 詢問本地知識庫"""
        response = self.client.post(
            "/api/chat",
            data=json.dumps({"session_id": self.session_id, "message": "陳文盛是誰？"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["source"], "kb")
        self.assertIn("陳文盛", data["reply"])

    def test_api_history_and_clear(self):
        """測試取得對話紀錄與清空對話"""
        # 1. 查詢歷史紀錄
        res_history = self.client.get(f"/api/history?session_id={self.session_id}")
        self.assertEqual(res_history.status_code, 200)
        data_h = res_history.get_json()
        self.assertTrue(data_h["success"])
        self.assertIsInstance(data_h["history"], list)

        # 2. 清空對話
        res_clear = self.client.post(
            "/api/clear",
            data=json.dumps({"session_id": self.session_id}),
            content_type="application/json",
        )
        self.assertEqual(res_clear.status_code, 200)
        data_c = res_clear.get_json()
        self.assertTrue(data_c["success"])


if __name__ == "__main__":
    print("🚀 正在執行網頁端 Web API 與介面端對端測試...")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestWebAPI)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)
    print("✅ 網頁端 Web API 與介面端對端測試全數通過！")
