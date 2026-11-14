/**
 * 全員找找看 Hazard Scouter — AI 代理 (Cloudflare Worker) v2
 *
 * 作用：AI 金鑰只放在這個代理伺服器上，網頁訪客不用登入、不用金鑰就能用 AI 分析。
 * 自動模式（provider: "auto"）依序嘗試，前一個失敗或額度用完就換下一個：
 *   1. Gemini Flash（最準，免費額度很少）
 *   2. Gemini Flash-Lite（免費額度較多）
 *   3. Cloudflare Workers AI（不需金鑰，用 Cloudflare 每日免費額度）
 *   放大檢查的局部圖（stage: "zoom"）直接從第 2 步開始，把 Flash 額度留給整張照片。
 *
 * 必要設定（Cloudflare 後台 → 這個 Worker → Settings）
 *   Variables and Secrets（型別選 Secret）：
 *     GEMINI_API_KEY      Google AI Studio 免費金鑰（金鑰所屬專案「不要」開啟帳單）
 *   Bindings：
 *     Workers AI          變數名稱 AI
 *     KV namespace        變數名稱 RL（每個 IP 每日次數上限要用）
 *
 * 選填變數
 *   ALLOWED_ORIGINS     允許呼叫的網站，逗號分隔。預設只允許 https://o4444.github.io
 *   DAILY_LIMIT         每個 IP 每天可呼叫幾次（預設 100；開啟放大檢查時一張照片最多用 5 次）
 *   GEMINI_MODEL        預設 gemini-3.8-flash
 *   GEMINI_LITE_MODEL   預設 gemini-3.5-flash-lite；填 off 可停用這一層
 *   CF_MODEL            預設 @cf/google/gemma-4-26b-a4b-it
 *   APP_TOKEN           存取碼（會寫在網頁原始碼裡，只能擋一般濫用，不建議依賴）
 *   其他服務（保留，自動模式不使用）：ANTHROPIC_API_KEY、OPENAI_API_KEY、GROQ_API_KEY、OPENROUTER_API_KEY
 *   以及對應的 ANTHROPIC_MODEL / OPENAI_MODEL / GROQ_MODEL / OPENROUTER_MODEL
 *
 * 防盜用設計
 *   - 只接受允許的網站來源（瀏覽器會擋其他網站；偽造來源的程式仍可呼叫，所以還有下面幾層）
 *   - 每個 IP 每日次數上限（IP 只存雜湊值，25 小時後自動刪除）
 *   - 只接受本工具的危害辨識提示詞與圖片，限制大小，不能當成一般 AI 代理
 *   - Gemini 專案不開帳單、Cloudflare 用免費方案：被濫用最多就是當天額度用完，不會產生費用
 *   - 不儲存照片與分析結果
 *
 * 介面
 *   GET  /health    → { ok, engines, perIpDailyLimit }（給你自己在瀏覽器測試，不含任何金鑰）
 *   GET  /providers → { providers: ["auto", ...] }
 *   POST /analyze   { provider, prompt, image(dataURL), stage? } → { text, engine }
 */

const DEFAULT_ORIGINS = "https://o4444.github.io";
const MAX_BODY_BYTES = 4_500_000;
const MAX_IMAGE_CHARS = 4_000_000; // dataURL 長度上限（約 3 MB 圖片）
const MAX_PROMPT_CHARS = 8000;
const PROMPT_PREFIX = "你是台灣職業安全衛生檢查輔助員"; // 須與 HTML 內 PROMPT 開頭一致
const UPSTREAM_TIMEOUT_MS = 60_000;

const DEFAULT_MODEL = {
  claude: "claude-sonnet-5-5",
  gpt: "gpt-4o",
  gemini: "gemini-3.8-flash",
  geminiLite: "gemini-3.5-flash-lite",
  groq: "qwen/qwen3.8-27b",
  openrouter: "openrouter/free",
  cf: "@cf/google/gemma-4-26b-a4b-it",
};

// OpenAI 相容介面的服務：[網址, 金鑰變數, 模型變數, 是否要求 JSON 模式]
const OPENAI_LIKE = {
  gpt: ["https://api.openai.com/v1/chat/completions", "OPENAI_API_KEY", "OPENAI_MODEL", true],
  groq: ["https://api.groq.com/openai/v1/chat/completions", "GROQ_API_KEY", "GROQ_MODEL", true],
  openrouter: ["https://openrouter.ai/api/v1/chat/completions", "OPENROUTER_API_KEY", "OPENROUTER_MODEL", false],
};

const dailyLimit = (env) => Math.max(1, parseInt(env.DAILY_LIMIT || "100", 10) || 100);

export default {
  async fetch(req, env) {
    const url = new URL(req.url);

    // 健康檢查：不需來源檢查，不含任何秘密，方便在瀏覽器直接開來測試
    if (req.method === "GET" && url.pathname === "/health") {
      return new Response(JSON.stringify({
        ok: true,
        engines: autoChain(env, "main").map((s) => s.name),
        perIpDailyLimit: env.RL ? dailyLimit(env) : null,
      }), { headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" } });
    }

    const origin = req.headers.get("Origin") || "";
    const allowed = (env.ALLOWED_ORIGINS || DEFAULT_ORIGINS).split(",").map((s) => s.trim().replace(/\/+$/, "")).filter(Boolean);
    const openToAll = allowed.includes("*");
    const originOK = openToAll || allowed.includes(origin);

    const cors = {
      "Access-Control-Allow-Origin": openToAll ? "*" : originOK ? origin : "null",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, X-App-Token",
      "Access-Control-Max-Age": "86400",
      Vary: "Origin",
    };
    const json = (obj, status = 200) =>
      new Response(JSON.stringify(obj), {
        status,
        headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store", ...cors },
      });

    if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });
    if (!originOK) return json({ error: "origin not allowed" }, 403);

    const available = [];
    if (env.GEMINI_API_KEY || env.AI) available.push("auto");
    if (env.ANTHROPIC_API_KEY) available.push("claude");
    if (env.OPENAI_API_KEY) available.push("gpt");
    if (env.GEMINI_API_KEY) available.push("gemini");
    if (env.GROQ_API_KEY) available.push("groq");
    if (env.OPENROUTER_API_KEY) available.push("openrouter");
    if (env.AI) available.push("cf");

    if (req.method === "GET" && url.pathname === "/providers") {
      return json({ providers: available });
    }

    if (req.method !== "POST" || url.pathname !== "/analyze") {
      return json({ error: "not found" }, 404);
    }

    if (env.APP_TOKEN && req.headers.get("X-App-Token") !== env.APP_TOKEN) {
      return json({ error: "bad token" }, 401);
    }

    const len = parseInt(req.headers.get("Content-Length") || "0", 10) || 0;
    if (len > MAX_BODY_BYTES) return json({ error: "too large" }, 413);

    let body;
    try {
      body = await req.json();
    } catch {
      return json({ error: "bad json" }, 400);
    }
    const { provider, prompt, image } = body || {};
    const stage = body && body.stage === "zoom" ? "zoom" : "main";
    if (!available.includes(provider)) return json({ error: "provider not available" }, 400);
    if (typeof prompt !== "string" || !prompt.startsWith(PROMPT_PREFIX) || !prompt.includes('"hazards"') || prompt.length > MAX_PROMPT_CHARS) {
      return json({ error: "bad prompt" }, 400);
    }
    const m = typeof image === "string" && image.length <= MAX_IMAGE_CHARS
      ? image.match(/^data:(image\/(?:jpeg|png|webp));base64,([A-Za-z0-9+/=]+)$/)
      : null;
    if (!m) return json({ error: "bad image" }, 400);
    const p = { prompt, mime: m[1], b64: m[2], dataUrl: image };

    // 每個 IP 每日次數上限（有綁定 KV「RL」才啟用；IP 只存雜湊；計數非原子操作，僅作概略限制）
    if (env.RL) {
      const limit = dailyLimit(env);
      const ip = req.headers.get("CF-Connecting-IP") || "unknown";
      try {
        const key = "d:" + new Date().toISOString().slice(0, 10) + ":" + (await sha(ip));
        const used = parseInt((await env.RL.get(key)) || "0", 10) || 0;
        if (used >= limit) return json({ error: "daily limit reached", detail: "每個 IP 每日上限 " + limit + " 次" }, 429);
        await env.RL.put(key, String(used + 1), { expirationTtl: 90000 });
      } catch { /* KV 故障或超過免費寫入次數時不阻擋服務 */ }
    }

    try {
      if (provider === "auto") return json(await runAuto(env, stage, p));
      const text = await callProvider(provider, env, p);
      return json({ text, engine: provider });
    } catch (e) {
      const status = e && e.status === 429 ? 429 : 502;
      return json({ error: "upstream failed", detail: String((e && e.detail) || "").slice(0, 300) }, status);
    }
  },
};

async function sha(s) {
  const d = await crypto.subtle.digest("SHA-256", new TextEncoder().encode("hs-salt:" + s));
  return [...new Uint8Array(d)].slice(0, 12).map((b) => b.toString(16).padStart(2, "0")).join("");
}

/* ===== 自動模式：Gemini Flash → Gemini Flash-Lite → Workers AI ===== */
function autoChain(env, stage) {
  const c = [];
  if (env.GEMINI_API_KEY) {
    const main = env.GEMINI_MODEL || DEFAULT_MODEL.gemini;
    const lite = env.GEMINI_LITE_MODEL || DEFAULT_MODEL.geminiLite;
    if (stage !== "zoom") c.push({ name: main, run: (p) => callGemini(env, main, p) });
    if (lite !== "off" && lite !== main) c.push({ name: lite, run: (p) => callGemini(env, lite, p) });
    if (stage === "zoom" && lite === "off") c.push({ name: main, run: (p) => callGemini(env, main, p) });
  }
  if (env.AI) c.push({ name: "workers-ai", run: (p) => callCF(env, p) });
  return c;
}

async function runAuto(env, stage, p) {
  const errs = [];
  for (const step of autoChain(env, stage)) {
    try {
      const text = await step.run(p);
      if (!/"hazards"/.test(text)) {
        const e = new Error("no json");
        e.status = 502;
        e.detail = "reply is not the expected JSON";
        throw e;
      }
      return { text, engine: step.name };
    } catch (e) {
      errs.push({ name: step.name, status: (e && e.status) || 0, detail: String((e && (e.detail || e.message)) || "").replace(/\s+/g, " ").slice(0, 90) });
    }
  }
  const e = new Error("all engines failed");
  e.status = errs.length && errs.every((x) => x.status === 429) ? 429 : 502;
  e.detail = errs.length ? errs.map((x) => x.name + " " + x.status + " " + x.detail).join(" | ") : "no engine configured";
  throw e;
}

async function callGemini(env, model, p) {
  const r = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent`, {
    method: "POST",
    signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
    headers: { "x-goog-api-key": env.GEMINI_API_KEY, "Content-Type": "application/json" },
    body: JSON.stringify({
      contents: [{ role: "user", parts: [{ text: p.prompt }, { inline_data: { mime_type: p.mime, data: p.b64 } }] }],
      generationConfig: { temperature: 0.2, responseMimeType: "application/json" },
    }),
  });
  await ensureOK(r);
  const j = await r.json();
  return ((j.candidates && j.candidates[0] && j.candidates[0].content && j.candidates[0].content.parts) || [])
    .map((x) => x.text || "")
    .join("");
}

async function callCF(env, p) {
  let j;
  try {
    j = await env.AI.run(env.CF_MODEL || DEFAULT_MODEL.cf, {
      max_completion_tokens: 4000,
      temperature: 0.2,
      chat_template_kwargs: { enable_thinking: false },
      messages: [{
        role: "user",
        content: [
          { type: "text", text: p.prompt },
          { type: "image_url", image_url: { url: p.dataUrl } },
        ],
      }],
    });
  } catch (err) {
    const e = new Error("workers ai");
    e.status = /limit|quota|capacity|neuron|429/i.test(String(err)) ? 429 : 502;
    e.detail = String((err && err.message) || err);
    throw e;
  }
  if (j && typeof j.response === "string") return j.response;
  return (j && j.choices && j.choices[0] && j.choices[0].message && j.choices[0].message.content) || "";
}

/* ===== 單一服務（保留） ===== */
async function callProvider(provider, env, p) {
  let r, j;

  if (provider === "claude") {
    r = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
      headers: {
        "x-api-key": env.ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
      },
      body: JSON.stringify({
        model: env.ANTHROPIC_MODEL || DEFAULT_MODEL.claude,
        max_tokens: 4000,
        messages: [{
          role: "user",
          content: [
            { type: "image", source: { type: "base64", media_type: p.mime, data: p.b64 } },
            { type: "text", text: p.prompt },
          ],
        }],
      }),
    });
    await ensureOK(r);
    j = await r.json();
    return (j.content || []).map((x) => x.text || "").join("");
  }

  if (OPENAI_LIKE[provider]) {
    const [endpoint, keyVar, modelVar, jsonMode] = OPENAI_LIKE[provider];
    const payload = {
      model: env[modelVar] || DEFAULT_MODEL[provider],
      temperature: 0.2,
      messages: [{
        role: "user",
        content: [
          { type: "text", text: p.prompt },
          { type: "image_url", image_url: { url: p.dataUrl } },
        ],
      }],
    };
    if (jsonMode) payload.response_format = { type: "json_object" };
    r = await fetch(endpoint, {
      method: "POST",
      signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
      headers: { Authorization: "Bearer " + env[keyVar], "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    await ensureOK(r);
    j = await r.json();
    return (j.choices && j.choices[0] && j.choices[0].message && j.choices[0].message.content) || "";
  }

  if (provider === "cf") return callCF(env, p);

  // gemini
  return callGemini(env, env.GEMINI_MODEL || DEFAULT_MODEL.gemini, p);
}

async function ensureOK(r) {
  if (r.ok) return;
  let detail = "";
  try { detail = await r.text(); } catch { /* ignore */ }
  try { const j = JSON.parse(detail); detail = (j.error && (j.error.message || j.error.status)) || j.message || detail; } catch { /* 不是 JSON 就保留原文 */ }
  const e = new Error("upstream " + r.status);
  e.status = r.status;
  e.detail = detail;
  throw e;
}
