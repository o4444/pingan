# 全員找找看 AI 代理

給「全員找找看-危害辨識裝置」用的 Cloudflare Worker。訪客不用登入、不用金鑰就能用 AI 分析照片；金鑰只存在你的 Cloudflare。

[![Deploy to Cloudflare](https://deploy.workers.cloudflare.com/button)](https://deploy.workers.cloudflare.com/?url=https://github.com/o4444/pingan/tree/main/hazard-worker)

- 分析順序：Gemini Flash → Gemini Flash-Lite → Cloudflare Workers AI（前一個失敗或額度用完就換下一個）
- 防盜用：只允許 o4444.github.io 呼叫、每個 IP 每日上限（預設 100 次）、只接受本工具的提示詞與圖片
- 費用：Gemini 專案不開帳單、Cloudflare 用免費方案，最壞情況只是當天額度用完
- 部署後打開 `https://<Worker 網址>/health` 檢查設定
