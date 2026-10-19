/**
 * Google Apps Script (GAS) 整合範例腳本
 * 
 * 此腳本可直接複製到 Google Sheets、Google Docs 或獨立 GAS 專案中使用。
 * 支援將 Antigravity LINE Bot 核心服務無縫嵌入 Google 生態系！
 */

// 請將此網址替換為您的 Google Cloud Run 或本機測試網址 (需加 https://)
// 例如: "https://line-bot-service-xxxx-de.a.run.app"
var BOT_SERVER_URL = "https://YOUR_CLOUD_RUN_URL";

// 若您的伺服器 .env 有設定 WEB_API_KEY，請填入；若留空則免填
var BOT_API_KEY = "";


/**
 * 【功能 1】：在 Google Sheets 試算表中當作自訂函數使用
 * 
 * 試算表使用範例：
 *   =ASK_BOT("請問陳文盛老師是誰？")
 *   =ASK_BOT(A2)
 *
 * @param {string} prompt 要詢問機器人的問題或指令
 * @return {string} 機器人回覆的文字
 * @customfunction
 */
function ASK_BOT(prompt) {
  if (!prompt || typeof prompt !== "string") {
    return "⚠️ 請輸入有效的問題內容";
  }

  try {
    var response = callBotApi(prompt, "sheets_user");
    return response.reply || "(無回覆)";
  } catch (err) {
    return "❌ 呼叫失敗: " + err.message;
  }
}


/**
 * 【功能 2】：通用的 API 呼叫函式 (可在 GAS 任何指令或定時觸發器中調用)
 *
 * @param {string} message 要發送的訊息
 * @param {string} [sessionId] 對話 Session ID (選填，相同 ID 可保有上下文記憶)
 * @return {Object} 包含 status, reply, source, model 的物件
 */
function callBotApi(message, sessionId) {
  var url = BOT_SERVER_URL + "/api/gas/chat";
  var payload = {
    message: message,
    session_id: sessionId || ("gas_" + Session.getTemporaryActiveUserKey()),
    api_key: BOT_API_KEY
  };

  var options = {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };

  var httpResponse = UrlFetchApp.fetch(url, options);
  var responseCode = httpResponse.getResponseCode();
  var content = httpResponse.getContentText();

  if (responseCode !== 200) {
    throw new Error("HTTP " + responseCode + ": " + content);
  }

  var data = JSON.parse(content);
  return data;
}


/**
 * 【功能 3】：測試執行範例
 * 在 GAS 編輯器中點選「執行」>「testAskBot」即可直接在日誌查看回傳！
 */
function testAskBot() {
  Logger.log("--- 測試詢問本地知識庫 ---");
  var res1 = callBotApi("陳文盛是誰？", "test_gas_session");
  Logger.log("回覆來源: " + res1.source);
  Logger.log("回覆內容:\n" + res1.reply);

  Logger.log("\n--- 測試系統指令 ---");
  var res2 = callBotApi("/help", "test_gas_session");
  Logger.log("回覆內容:\n" + res2.reply);
}

