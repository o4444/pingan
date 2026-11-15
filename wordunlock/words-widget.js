// WordUnlock 鎖定畫面小工具（Scriptable 用）
// 使用方式：App Store 安裝免費的「Scriptable」→ 新增腳本 → 貼上全部內容 → 存檔
// 然後在鎖定畫面「自訂 → 加入小工具 → Scriptable」選這個腳本。

// ===== 可以自己改的設定 =====
const CHANGE_EVERY_MINUTES = 60;   // 多久換一個字（實際時間由 iPhone 決定，可能晚幾分鐘）
const LEVELS = [];                 // 只看某些程度，例如 ["B1","B2"]；空的 = 全部
// ============================

const URL = "https://o4444.github.io/pingan/wordunlock/words.json";
const fm = FileManager.local();
const cachePath = fm.joinPath(fm.documentsDirectory(), "wordunlock-words.json");

async function loadWords() {
  try {
    const req = new Request(URL);
    req.timeoutInterval = 8;
    const data = await req.loadJSON();
    if (data && data.words && data.words.length) {
      fm.writeString(cachePath, JSON.stringify(data));   // 存一份，沒網路也能顯示
      return data.words;
    }
  } catch (e) {}
  if (fm.fileExists(cachePath)) {
    try { return JSON.parse(fm.readString(cachePath)).words; } catch (e) {}
  }
  // 最後的保底單字：任何情況都不會空白
  return [{ w: "resilient", pos: "Adjective", posZh: "形容詞", ipa: "/rɪˈzɪljənt/", kk: "[rɪˋzɪljənt]",
            zh: "有韌性的；能迅速恢復的", ex: "Children are often more resilient than we think.",
            exZh: "孩子往往比我們想像的更有韌性。", lv: "C1" }];
}

function pickWord(words, now) {
  let list = LEVELS.length ? words.filter(w => LEVELS.includes(w.lv)) : words;
  if (!list.length) list = words;
  const start = new Date(now); start.setHours(0, 0, 0, 0);
  const day = Math.floor(start.getTime() / 86400000);
  const slot = Math.floor((now - start) / 60000 / CHANGE_EVERY_MINUTES);
  // 每天換一種順序
  const order = list.map((w, i) => [((i + 1) * 2654435761 + day * 40503) % 4294967296, w])
                    .sort((a, b) => a[0] - b[0]).map(x => x[1]);
  return order[slot % order.length];
}

function nextChange(now) {
  const start = new Date(now); start.setHours(0, 0, 0, 0);
  const slot = Math.floor((now - start) / 60000 / CHANGE_EVERY_MINUTES) + 1;
  return new Date(start.getTime() + slot * CHANGE_EVERY_MINUTES * 60000);
}

function build(w, family) {
  const widget = new ListWidget();
  widget.url = "https://o4444.github.io/pingan/wordunlock/";   // 點一下打開 WordUnlock
  if (family === "accessoryInline") {
    widget.addText(`${w.w} · ${w.zh.split(/[；;、]/)[0]}`);
  } else if (family === "accessoryCircular") {
    widget.addAccessoryWidgetBackground = true;
    const t = widget.addText(w.w); t.font = Font.boldSystemFont(12); t.minimumScaleFactor = 0.4; t.centerAlignText();
    const z = widget.addText(w.zh.split(/[；;、]/)[0]); z.font = Font.systemFont(9); z.minimumScaleFactor = 0.5; z.centerAlignText();
  } else if (family === "accessoryRectangular") {
    const t = widget.addText(`${w.w}  ${w.ipa}`); t.font = Font.boldSystemFont(15); t.minimumScaleFactor = 0.6; t.lineLimit = 1;
    const z = widget.addText(`${w.posZh}｜${w.zh}`); z.font = Font.systemFont(12); z.lineLimit = 1; z.minimumScaleFactor = 0.7;
    const e = widget.addText(w.ex); e.font = Font.italicSystemFont(10); e.lineLimit = 1; e.minimumScaleFactor = 0.7; e.textOpacity = 0.85;
  } else {
    // 主畫面小工具
    widget.backgroundColor = new Color("#1d4ed8");
    const l = widget.addText(`${w.lv} · ${w.pos}`); l.font = Font.systemFont(11); l.textColor = new Color("#cfe0ff");
    widget.addSpacer(4);
    const t = widget.addText(w.w); t.font = Font.boldSystemFont(24); t.textColor = Color.white(); t.minimumScaleFactor = 0.5; t.lineLimit = 1;
    const i = widget.addText(`${w.ipa}  ${w.kk}`); i.font = Font.systemFont(11); i.textColor = new Color("#cfe0ff");
    widget.addSpacer(4);
    const z = widget.addText(w.zh); z.font = Font.systemFont(14); z.textColor = Color.white();
    if (family !== "small") {
      widget.addSpacer(6);
      const e = widget.addText(w.ex); e.font = Font.italicSystemFont(12); e.textColor = Color.white();
      const ez = widget.addText(w.exZh); ez.font = Font.systemFont(11); ez.textColor = new Color("#cfe0ff");
    }
  }
  return widget;
}

const now = new Date();
const words = await loadWords();
const word = pickWord(words, now);
const family = config.widgetFamily || "medium";
const widget = build(word, family);
widget.refreshAfterDate = nextChange(now);

if (config.runsInWidget || config.runsInAccessoryWidget) {
  Script.setWidget(widget);
} else {
  await widget.presentMedium();   // 在 App 裡按執行時先預覽
}
Script.complete();
