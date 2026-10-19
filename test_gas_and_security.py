"""
test_gas_and_security.py — 驗證 CORS、API Key 安全防護與 Google Apps Script (GAS) 端點
"""

import sys
import unittest
import json
from unittest.mock import patch

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from app import app
from core.storage import FileHistoryStorage


class TestGASAndSecurity(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_cors_headers_present(self):
        """測試所有回應均包含 CORS 標頭（確保 GAS HTMLService 與外部跨域通訊正常）"""
        response = self.client.get("/health")
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "*")
        self.assertIn("POST", response.headers.get("Access-Control-Allow-Methods", ""))

    def test_options_preflight(self):
        """測試 OPTIONS 預檢請求正常回傳 200"""
        response = self.client.options("/api/gas/chat")
        self.assertEqual(response.status_code, 200)

    def test_gas_endpoint_post(self):
        """測試 Google Apps Script (GAS) POST 端點呼叫"""
        payload = {"message": "陳文盛老師是誰？", "session_id": "gas_unit_test"}
        response = self.client.post(
            "/api/gas/chat",
            data=json.dumps(payload),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data.get("status"), "success")
        self.assertIn("陳文盛", data.get("reply", ""))
        self.assertEqual(data.get("source"), "kb")

    def test_gas_endpoint_get(self):
        """測試 Google Sheets 自訂公式常使用的 GET 請求呼叫"""
        response = self.client.get("/api/gas/chat?message=/help")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data.get("status"), "success")
        self.assertIn("指令清單", data.get("reply", ""))

    def test_api_key_protection(self):
        """測試當設定 WEB_API_KEY 時的金鑰驗證機制"""
        with patch("config.WEB_API_KEY", "secret_gas_key_123"):
            # 1. 未帶金鑰 ➔ 401
            res_no_key = self.client.post(
                "/api/gas/chat",
                data=json.dumps({"message": "hi"}),
                content_type="application/json"
            )
            self.assertEqual(res_no_key.status_code, 401)

            # 2. 帶錯誤金鑰 ➔ 401
            res_wrong_key = self.client.post(
                "/api/gas/chat",
                data=json.dumps({"message": "hi", "api_key": "wrong"}),
                content_type="application/json"
            )
            self.assertEqual(res_wrong_key.status_code, 401)

            # 3. 帶正確金鑰 ➔ 200
            res_correct_key = self.client.post(
                "/api/gas/chat",
                data=json.dumps({"message": "/status", "api_key": "secret_gas_key_123"}),
                content_type="application/json"
            )
            self.assertEqual(res_correct_key.status_code, 200)

    def test_file_storage_lifecycle(self):
        """測試抽象持久化儲存層生命週期 (儲存 ➔ 讀取 ➔ 清空)"""
        storage = FileHistoryStorage(base_dir="chat_history_test")
        uid = "storage_test_user"
        test_history = [{"role": "user", "content": "測試對話"}]

        try:
            storage.save(uid, test_history)
            loaded = storage.load(uid)
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0]["content"], "測試對話")

            cleared = storage.clear(uid)
            self.assertTrue(cleared)
            self.assertEqual(len(storage.load(uid)), 0)
        finally:
            import shutil
            import os
            if os.path.exists("chat_history_test"):
                shutil.rmtree("chat_history_test")


if __name__ == "__main__":
    print("🚀 正在執行 GAS 整合、CORS 與安全防護測試...")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestGASAndSecurity)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)
    print("✅ GAS 整合、CORS 與安全防護測試全數通過！")
