#!/usr/bin/env python3
"""產生 WordUnlock 的行事曆訂閱檔 words.ics（給 iPhone 鎖定畫面「行事曆」小工具顯示單字）。

用法：python3 tools/build_feeds.py [開始日期 YYYY-MM-DD] [天數]
預設從今天開始排 90 天，每天 07:00–22:59 每小時一個單字。
字庫來自同資料夾的 words.json。快到期時重新執行一次再推上 GitHub 即可。
"""
import json, sys, hashlib, datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TZ = dt.timezone(dt.timedelta(hours=8))          # 台灣時間，沒有日光節約
HOURS = range(7, 23)                             # 07:00 ~ 22:00 開始的時段


def esc(t: str) -> str:
    return t.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def fold(line: str) -> str:
    """RFC 5545：每行最多 75 個位元組，中文以 UTF-8 計算"""
    out, cur = [], b""
    for ch in line:
        b = ch.encode()
        if len(cur) + len(b) > (75 if not out else 74):
            out.append(cur.decode()); cur = b""
        cur += b
    out.append(cur.decode())
    return "\r\n ".join(out)


def order_for_day(n_words: int, day: dt.date) -> list:
    """每天用日期當種子打亂順序，連續幾天不會一模一樣"""
    idx = list(range(n_words))
    idx.sort(key=lambda i: hashlib.md5(f"{day.isoformat()}-{i}".encode()).hexdigest())
    return idx


def main():
    start = dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else dt.date.today()
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 90
    words = json.loads((ROOT / "words.json").read_text(encoding="utf-8"))["words"]
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    utc = lambda d: d.astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//WordUnlock//Daily Words//ZH-TW",
        "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
        "X-WR-CALNAME:WordUnlock 每日單字", "X-WR-TIMEZONE:Asia/Taipei",
        "X-WR-CALDESC:每小時一個英文單字，顯示在鎖定畫面的行事曆小工具",
        "REFRESH-INTERVAL;VALUE=DURATION:P1D", "X-PUBLISHED-TTL:P1D",
    ]
    for d in range(days):
        day = start + dt.timedelta(days=d)
        order = order_for_day(len(words), day)
        for k, h in enumerate(HOURS):
            w = words[order[k % len(words)]]
            begin = dt.datetime(day.year, day.month, day.day, h, 0, tzinfo=TZ)
            desc = f"{w['ipa']}  KK {w['kk']}\n{w['pos']}（{w['posZh']}）· {w['lv']}" + (f"\n\n{w['ex']}\n{w['exZh']}".rstrip() if w['ex'] else "")
            lines += [
                "BEGIN:VEVENT",
                f"UID:wordunlock-{day.isoformat()}-{h:02d}@o4444.github.io",
                f"DTSTAMP:{stamp}",
                f"DTSTART:{utc(begin)}",
                f"DTEND:{utc(begin + dt.timedelta(minutes=59))}",
                "SUMMARY:" + esc(f"{w['w']}｜{w['zh']}"),
                "LOCATION:" + esc(f"{w['ipa']} {w['posZh']}"),
                "DESCRIPTION:" + esc(desc),
                "TRANSP:TRANSPARENT",
                "END:VEVENT",
            ]
    lines.append("END:VCALENDAR")
    (ROOT / "words.ics").write_text("\r\n".join(fold(l) for l in lines) + "\r\n", encoding="utf-8")
    end = start + dt.timedelta(days=days - 1)
    print(f"words.ics：{start} ~ {end}，共 {days * len(HOURS)} 個事件")


if __name__ == "__main__":
    main()
