"""
test_app_routes.py — 驗證 Flask 與 LINE Webhook 路由運作正常
"""

import sys
import unittest

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from app import app


class TestAppRoutes(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_health_check_endpoint(self):
        """測試 GET / 健康檢查端點"""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data.get("status"), "online")
        self.assertEqual(data.get("service"), "Antigravity LINE Bot")
        self.assertIn("endpoint", data)

    def test_callback_without_signature_returns_400(self):
        """測試 POST /callback 在沒有合法簽名時回傳 400（驗證安全機制有效）"""
        response = self.client.post("/callback", data="dummy_body")
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    print("🚀 正在執行 app.py 路由與 LINE 簽章驗證測試...")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestAppRoutes)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)
    print("✅ app.py 路由與 LINE 驗證測試全數通過！")
