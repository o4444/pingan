"""小家教系列互連區塊：在每個家教頁底部插入「其他小家教」連結與 QR code。
新增家教時，在 TUTORS 加一行，再執行：python3 tools/series.py
重複執行會更新區塊，不會重複插入。"""
import os, re, qrcode

BASE = 'https://o4444.github.io/pingan/'
TUTORS = [
    ('oshb', '🦺', '職安乙級', '職業安全衛生管理員'),
    ('esb', '🤝', '就服乙級', '就業服務乙級技術士'),
    ('netzero', '🌱', '淨零碳規劃管理師', '經濟部 iPAS'),
    ('env', '🌏', '空水廢毒', '環保專責證照'),
    ('wem', '🔬', '作業環境監測乙級', '化學性／物理性因子'),
    ('pe', '🎓', '工安／職衛技師', '專技高考 工業安全・職業衛生'),
]
START, END = '<!--SERIES-START-->', '<!--SERIES-END-->'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def qr_svg(url):
    q = qrcode.QRCode(border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
    q.add_data(url); q.make(fit=True)
    m = q.get_matrix(); n = len(m)
    d = ''.join(f'M{x} {y}h1v1h-1z' for y, row in enumerate(m) for x, v in enumerate(row) if v)
    return f'<svg viewBox="0 0 {n} {n}" shape-rendering="crispEdges" aria-hidden="true"><rect width="{n}" height="{n}" fill="#fff"/><path d="{d}" fill="#14202b"/></svg>'

CSS = """<style>
.series{max-width:960px;margin:8px auto 120px;padding:0 16px;font-family:inherit}
.series h2{font-size:18px;margin:0 0 4px}
.series p{margin:0 0 12px;font-size:14px;color:#5b6675}
.series .sg{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:10px}
.series a.sc2{display:flex;gap:10px;align-items:center;text-decoration:none;color:#14202b;background:#fff;border:2px solid #d9dee6;border-radius:12px;padding:10px}
.series a.sc2:hover{border-color:#14202b}
.series .sq{flex:0 0 76px;width:76px;height:76px}
.series .sq svg{width:100%;height:100%;display:block}
.series b{display:block;font-size:15px}
.series small{display:block;color:#5b6675;font-size:12px;margin-top:2px}
.series .go{display:inline-block;margin-top:6px;font-size:12px;font-weight:700;color:#0b6e4f}
</style>"""

def block(cur):
    cards = ''.join(
        f'<a class="sc2" href="../{k}/"><span class="sq">{qr_svg(BASE + k + "/")}</span><span><b>{ic} {name}</b><small>{sub}</small><span class="go">前往陪考 →</span></span></a>'
        for k, ic, name, sub in TUTORS if k != cur)
    return f'{START}\n{CSS}\n<section class="series" aria-label="小家教系列"><h2>📚 小家教系列・其他陪考</h2><p>點卡片直接前往，或用手機掃 QR code 分享給一起準備考試的朋友。</p><div class="sg">{cards}</div></section>\n{END}'

for k, *_ in TUTORS:
    p = os.path.join(ROOT, k, 'index.html')
    s = open(p, encoding='utf-8').read()
    b = block(k)
    if START in s:
        s = re.sub(re.escape(START) + r'.*?' + re.escape(END), lambda _: b, s, flags=re.S)
    else:
        if s.count('<main id="app"></main>') != 1: raise SystemExit(f'{k}: 找不到 <main id="app">')
        s = s.replace('<main id="app"></main>', '<main id="app"></main>\n' + b, 1)
    open(p, 'w', encoding='utf-8').write(s)
    print('ok', k)
