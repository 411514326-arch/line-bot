import sys
import os
import unittest
from unittest.mock import patch, MagicMock

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from core.schemas import BotRequest, BotResponse, BotPlatform
from core.bot_service import handle_bot_request


class TestCoreBotService(unittest.TestCase):
    def setUp(self):
        self.user_id = "test_user_123"

    def test_empty_message(self):
        """測試空白訊息處理"""
        req = BotRequest(user_id=self.user_id, text="   ", platform=BotPlatform.WEB)
        resp = handle_bot_request(req)
        self.assertFalse(resp.success)
        self.assertIn("空白訊息", resp.text)

    def test_help_command(self):
        """測試 /help 指令"""
        req = BotRequest(user_id=self.user_id, text="/help", platform=BotPlatform.WEB)
        resp = handle_bot_request(req)
        self.assertTrue(resp.success)
        self.assertEqual(resp.source, "command")
        self.assertIn("指令清單", resp.text)

    def test_status_command(self):
        """測試 /status 指令"""
        req = BotRequest(user_id=self.user_id, text="/status", platform=BotPlatform.WEB)
        resp = handle_bot_request(req)
        self.assertTrue(resp.success)
        self.assertEqual(resp.source, "command")
        self.assertIn("System Status", resp.text)

    @patch("core.bot_service.is_user_allowed", return_value=True)
    def test_knowledge_base_hit(self, mock_allowed):
        """測試本地知識庫（問陳文盛教授）"""
        req = BotRequest(user_id=self.user_id, text="請問陳文盛是誰？", platform=BotPlatform.LINE)
        resp = handle_bot_request(req)
        self.assertTrue(resp.success)
        self.assertEqual(resp.source, "kb")
        self.assertIn("陳文盛", resp.text)
        self.assertIn("東華大學", resp.text)

    @patch("core.bot_service.is_user_allowed", return_value=False)
    def test_line_whitelist_rejected(self, mock_allowed):
        """測試 LINE 未在白名單的使用者會被拒絕"""
        req = BotRequest(user_id="unauthorized_user", text="你好", platform=BotPlatform.LINE)
        resp = handle_bot_request(req)
        self.assertFalse(resp.success)
        self.assertEqual(resp.source, "permission")
        self.assertIn("Access restricted", resp.text)

    def test_clear_command(self):
        """測試 /clear 清空記憶"""
        req = BotRequest(user_id=self.user_id, text="/clear", platform=BotPlatform.WEB)
        resp = handle_bot_request(req)
        self.assertTrue(resp.success)
        self.assertEqual(resp.source, "command")
        self.assertTrue("清空" in resp.text or "沒有" in resp.text)

    def test_cloud_security_guard_for_cmd(self):
        """測試當系統處於雲端環境時，/cmd 是否被安全攔截"""
        with patch("core.bot_service.RUNNING_ON_CLOUD", True):
            req = BotRequest(user_id=self.user_id, text="/cmd dir", platform=BotPlatform.WEB)
            resp = handle_bot_request(req)
            self.assertFalse(resp.success)
            self.assertEqual(resp.source, "security")
            self.assertIn("Google Cloud Run", resp.text)


if __name__ == "__main__":
    print("🚀 正在執行核心共用邏輯單元測試...")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestCoreBotService)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)
    print("✅ 所有核心邏輯單元測試均已通過！")
