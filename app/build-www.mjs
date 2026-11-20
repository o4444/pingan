// 把 repo 裡的小家教網頁複製成 App 用的 www/ 資料夾（原本網站的檔案不會被改動）
// 用法：在 app/ 資料夾執行 `node build-www.mjs`
import { cpSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const repo = join(here, '..');
const www = join(here, 'www');

// 要放進 App 的家教（資料夾名稱）。之後新增科目只要加在這裡，並在 hub/index.html 加一張卡片。
const TUTORS = ['oshb', 'esb', 'netzero', 'env'];

// 家教頁左下角的「回合集」按鈕（只加在 App 版的複本裡）
const BACK_BTN = `
<a href="../index.html" id="app-hub-back" aria-label="回小家教合集"
 style="position:fixed;left:10px;bottom:calc(14px + env(safe-area-inset-bottom));z-index:99999;background:#14213d;color:#fff;
 text-decoration:none;font:600 14px/1 system-ui,sans-serif;padding:10px 14px;border-radius:999px;box-shadow:0 2px 8px rgba(0,0,0,.25);opacity:.92">‹ 合集</a>
`;

rmSync(www, { recursive: true, force: true });
mkdirSync(www, { recursive: true });

cpSync(join(here, 'hub', 'index.html'), join(www, 'index.html'));
cpSync(join(repo, 'icon.png'), join(www, 'icon.png'));

for (const t of TUTORS) {
  const src = join(repo, t, 'index.html');
  let html = readFileSync(src, 'utf8');
  if (!html.includes('</body>')) throw new Error(`${t}/index.html 找不到 </body>`);
  html = html.replace('</body>', `${BACK_BTN}</body>`);
  mkdirSync(join(www, t), { recursive: true });
  writeFileSync(join(www, t, 'index.html'), html);
  console.log(`✓ ${t}  ${(html.length / 1024).toFixed(0)} KB`);
}
console.log('www/ 完成');
