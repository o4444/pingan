#!/usr/bin/env python3
"""從公開字典資料產生 WordUnlock 字庫（A1–C2 各 N 字）。

資料來源（請保留出處）：
- 分級：CEFR-J Wordlist 1.5（Tono Laboratory, TUFS，可商用須註明出處）
         Octanove Vocabulary Profile C1/C2 1.0（CC BY-SA 4.0）
- 中文翻譯、英式音標、詞頻、考試標籤：ECDICT（MIT），經 OpenCC s2twp 轉台灣繁體
- 美式音標（IPA、KK）：CMU Pronouncing Dictionary（BSD）
- 英文解釋、同反義字、例句、主題分類：WordNet 3.0（Princeton WordNet License）

用法：NLTK_DATA=<含 corpora/wordnet.zip 的資料夾> python3 tools/build_words.py <資料夾> [每級字數]
資料夾內需有 cefrj.csv、c1c2.csv、ecdict.csv。輸出 words-db.js 與 words.json。
"""
import csv, json, re, sys
from pathlib import Path

import cmudict
import opencc
from nltk.corpus import wordnet as wn

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(sys.argv[1])
PER_LEVEL = int(sys.argv[2]) if len(sys.argv) > 2 else 500
LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]
CC = opencc.OpenCC("s2twp")
CMU = cmudict.dict()

# ---------------- 詞性 ----------------
POS_MAP = {"noun": "noun", "verb": "verb", "adjective": "adjective", "adverb": "adverb",
           "preposition": "preposition", "pronoun": "pronoun", "conjunction": "conjunction",
           "determiner": "determiner", "interjection": "interjection", "number": "number",
           "modal auxiliary": "verb", "be-verb": "verb", "do-verb": "verb", "have-verb": "verb", "vern": "verb"}
CONTENT = {"noun", "verb", "adjective", "adverb"}
ECD_POS = {"noun": ["n."], "verb": ["v.", "vt.", "vi."], "adjective": ["a.", "adj."], "adverb": ["ad.", "adv."],
           "preposition": ["prep."], "pronoun": ["pron."], "conjunction": ["conj."], "determiner": ["det.", "a.", "pron."],
           "interjection": ["int.", "interj."], "number": ["num.", "n.", "a."]}
WN_POS = {"noun": "n", "verb": "v", "adjective": "a", "adverb": "r"}

# ---------------- 美式音標：ARPAbet → IPA / KK ----------------
V_IPA = {"AA": "ɑː", "AE": "æ", "AH": "ʌ", "AO": "ɔː", "AW": "aʊ", "AY": "aɪ", "EH": "ɛ", "ER": "ɝː", "EY": "eɪ",
         "IH": "ɪ", "IY": "iː", "OW": "oʊ", "OY": "ɔɪ", "UH": "ʊ", "UW": "uː"}
V_KK = {"AA": "ɑ", "AE": "æ", "AH": "ʌ", "AO": "ɔ", "AW": "aʊ", "AY": "aɪ", "EH": "ɛ", "ER": "ɝ", "EY": "e",
        "IH": "ɪ", "IY": "i", "OW": "o", "OY": "ɔɪ", "UH": "ʊ", "UW": "u"}
C_IPA = {"B": "b", "CH": "tʃ", "D": "d", "DH": "ð", "F": "f", "G": "ɡ", "HH": "h", "JH": "dʒ", "K": "k", "L": "l",
         "M": "m", "N": "n", "NG": "ŋ", "P": "p", "R": "r", "S": "s", "SH": "ʃ", "T": "t", "TH": "θ", "V": "v",
         "W": "w", "Y": "j", "Z": "z", "ZH": "ʒ"}
C_KK = dict(C_IPA, G="g")
ONSETS = {tuple(o.split()) for o in """P R|P L|B R|B L|T R|D R|K R|K L|G R|G L|F R|F L|TH R|SH R|S P|S T|S K|S M|S N|S L|S W|S F|S P R|S P L|S T R|S K R|S K W|T W|D W|K W|G W|P Y|B Y|F Y|M Y|K Y|HH Y|V Y|S K Y""".replace("|", "\n").splitlines()}


def is_vowel(p):
    return p[-1].isdigit()


def syllable_starts(ph):
    """回傳每個母音所屬音節的開頭位置（最大首音原則）"""
    starts, prev_v = {}, -1
    for i, p in enumerate(ph):
        if not is_vowel(p):
            continue
        cons = list(range(prev_v + 1, i))
        start = i
        for k in range(len(cons)):          # 由長到短找合法首音
            seg = tuple(ph[j] for j in cons[k:])
            if len(seg) == 1 and seg[0] != "NG" or seg in ONSETS:
                start = cons[k]
                break
        if prev_v < 0:
            start = 0
        starts[i] = start
        prev_v = i
    return starts


def transcribe(ph, kk=False):
    fixed = []
    for i, p in enumerate(ph):          # correct: K ER0 EH1 → kə ˈrɛ
        if p == "ER0" and i + 1 < len(ph) and is_vowel(ph[i + 1]):
            fixed += ["AH0", "R"]
        else:
            fixed.append(p)
    ph = fixed
    starts = syllable_starts(ph)
    marks = {}
    for vi, st in starts.items():
        s = ph[vi][-1]
        if s == "1":
            marks[st] = "ˋ" if kk else "ˈ"
        elif s == "2" and sum(1 for p in ph if is_vowel(p)) > 1:
            marks[st] = "ˌ"
    out = []
    for i, p in enumerate(ph):
        if i in marks:
            out.append(marks[i])
        if is_vowel(p):
            base, s = p[:-1], p[-1]
            if base == "AH" and s == "0":
                out.append("ə")
            elif base == "IY" and s == "0":
                out.append("ɪ" if kk else "i")
            elif base == "ER" and s == "0":
                out.append("ɚ")
            else:
                out.append((V_KK if kk else V_IPA)[base])
        else:
            out.append((C_KK if kk else C_IPA)[p])
    if len([p for p in ph if is_vowel(p)]) == 1:   # 單音節不標重音
        out = [x for x in out if x not in ("ˈ", "ˋ", "ˌ")]
    return "".join(out)


def us_pron(word):
    parts = word.lower().split()
    ipa, kk = [], []
    for w in parts:
        prons = CMU.get(w)
        if not prons:
            return None, None
        ipa.append(transcribe(prons[0]))
        kk.append(transcribe(prons[0], kk=True))
    return "/" + " ".join(ipa) + "/", "[" + " ".join(kk) + "]"


def uk_pron(ph):
    if not ph:
        return None
    p = ph.replace("'", "ˈ").replace(",", "ˌ").replace(":", "ː").replace("ә", "ə").replace("ɑ", "ɑ").strip()
    if p.startswith("."):
        p = "ˌ" + p[1:]
    p = p.replace(".", "")
    if not p or " " in p and len(p) > 30:
        return None
    return "/" + p + "/"


# ---------------- 中文翻譯 ----------------
def pick_translation(trans, pos):
    if not trans:
        return None
    lines = [l.strip() for l in trans.replace("\\n", "\n").split("\n") if l.strip() and not l.startswith("[网络]")]
    prefixes = ECD_POS.get(pos, [])
    chosen = None
    for l in lines:
        if any(l.startswith(pf + " ") or l.startswith(pf) and l[len(pf):len(pf) + 1] in " ，" for pf in prefixes):
            chosen = l
            break
    if chosen is None:
        if pos in CONTENT:
            return None        # 找不到對應詞性的翻譯：寧可不要，避免詞性錯
        chosen = lines[0] if lines else None
    if not chosen:
        return None
    chosen = re.sub(r"^[a-z]+\.\s*", "", chosen)
    chosen = re.sub(r"\[[^\]]*\]", "", chosen)        # 拿掉 [医] [美] 等標記
    chosen = re.sub(r"[（(][^）)]{0,12}[）)]", "", chosen)
    senses = [s.strip(" ，,;；") for s in re.split(r"[；;]", chosen) if s.strip(" ，,;；")]
    out, length = [], 0
    for s in senses:
        s = s.split("，")[0].split(",")[0].strip()
        if not s or s in out or re.search(r"[a-zA-Z]{3,}", s):
            continue
        if length + len(s) > 14 and out:
            break
        out.append(s)
        length += len(s)
        if len(out) >= 3:
            break
    if not out:
        return None
    return CC.convert("；".join(out))


# ---------------- WordNet ----------------
LEX_TOPIC = {"noun.food": "dining", "verb.consumption": "dining", "noun.body": "medical", "verb.body": "medical",
             "noun.feeling": "emotion", "verb.emotion": "emotion", "noun.possession": "business",
             "verb.possession": "business", "noun.location": "travel", "noun.cognition": "academic",
             "noun.communication": "academic", "verb.cognition": "academic", "noun.artifact": "daily",
             "noun.time": "daily", "noun.person": "daily", "verb.social": "workplace", "noun.group": "workplace"}
TAG_TOPIC = {"toefl": "toefl", "ielts": "ielts", "gre": "gre"}


def wordnet_info(word, pos):
    p = WN_POS.get(pos)
    if not p:
        return None, [], [], None, []
    syns = wn.synsets(word.replace(" ", "_"), p)
    if not syns:
        return None, [], [], None, []
    s0 = syns[0]
    definition = s0.definition()
    synonyms, antonyms = [], []
    for s in syns[:3]:
        for l in s.lemmas():
            name = l.name().replace("_", " ")
            if name.lower() != word.lower() and name not in synonyms and len(synonyms) < 3 and re.fullmatch(r"[a-z][a-z' -]{2,}", name):
                synonyms.append(name)
            for a in l.antonyms():
                an = a.name().replace("_", " ")
                if an not in antonyms and len(antonyms) < 2:
                    antonyms.append(an)
    example = None
    for s in syns[:2]:
        for ex in s.examples():
            if re.search(r"\b" + re.escape(word.split()[0][:max(3, len(word) - 2)]), ex, re.I) and 15 <= len(ex) <= 110 and len(ex.split()) >= 4:
                example = ex[0].upper() + ex[1:] + ("" if ex.endswith((".", "!", "?")) else ".")
                break
        if example:
            break
    topics = []
    for s in syns[:2]:
        t = LEX_TOPIC.get(s.lexname())
        if t and t not in topics:
            topics.append(t)
    return definition, synonyms, antonyms, example, topics


# ---------------- 主流程 ----------------
def main():
    ecd = {}
    with open(DATA / "ecdict.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            w = r["word"]
            if w and w.lower() == w and w not in ecd:
                ecd[w] = r

    rows = []
    for fn in ("cefrj.csv", "c1c2.csv"):
        with open(DATA / fn, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                rows.append((r["headword"].split("/")[0].strip(), POS_MAP.get(r["pos"].strip()), r["CEFR"].strip()))

    # 既有的手工精修單字優先保留
    old = json.loads((ROOT / "words-curated.json").read_text(encoding="utf-8"))
    curated = {w[0]: w for w in old}

    first_level = {}
    for (w, p, l) in rows:
        if l in LEVELS and (w not in first_level or LEVELS.index(l) < LEVELS.index(first_level[w])):
            first_level[w] = l
    ECD_TAG = {"n": "noun", "v": "verb", "j": "adjective", "r": "adverb", "i": "preposition", "c": "conjunction", "p": "pronoun", "u": "interjection", "d": "determiner", "m": "number"}
    def pos_share(word, pos):
        wp = WN_POS.get(pos)
        if wp:   # WordNet 語料出現次數：同一個字哪個詞性最常用
            cnt = sum(l.count() for s in wn.synsets(word.replace(" ", "_"), wp) for l in s.lemmas() if l.name().lower() == word.replace(" ", "_"))
            if cnt:
                return 1000 + cnt
        e = ecd.get(word)
        if not e or not e["pos"]:
            return 0
        for part in e["pos"].split("/"):
            k, _, v = part.partition(":")
            if ECD_TAG.get(k) == pos and v.isdigit():
                return int(v)
        return 0
    used, out, stats = set(curated), {lv: [] for lv in LEVELS}, {}
    for w in curated.values():
        out[w[12]].append(w)

    def freq_rank(word):
        e = ecd.get(word)
        if not e:
            return 10 ** 9
        vals = [int(e[k]) for k in ("frq", "bnc") if e[k] and int(e[k]) > 0]
        return min(vals) if vals else 10 ** 8

    for lv in LEVELS:
        cands = [(w, p) for (w, p, l) in rows if l == lv and p and w not in used
                 and re.fullmatch(r"[a-z][a-z' -]*[a-z]", w)]
        cands = [c for c in cands if first_level.get(c[0]) == lv]
        best = {}
        for c in cands:   # 同一個字只留最常用的詞性
            if c[0] not in best or pos_share(c[0], c[1]) > pos_share(c[0], best[c[0]][1]):
                best[c[0]] = c
        cands = list(best.values())
        cands.sort(key=lambda x: (x[1] not in CONTENT, freq_rank(x[0])))
        skipped = 0
        for w, p in cands:
            if len(out[lv]) >= PER_LEVEL:
                break
            if w in used:
                continue
            e = ecd.get(w)
            ipa, kk = us_pron(w)
            zh = pick_translation(e["translation"], p) if e else None
            if not (e and ipa and zh):
                skipped += 1
                continue
            definition, syn, ant, ex, topics = wordnet_info(w, p)
            if not definition:
                d = [l for l in (e["definition"] or "").replace("\\n", "\n").split("\n") if l.strip()]
                definition = re.sub(r"^[a-z]+\.\s*", "", d[0]).strip() if d else ""
            if not definition and p in CONTENT:
                skipped += 1
                continue
            tags = (e["tag"] or "").split()
            for t in tags:
                if t in TAG_TOPIC and TAG_TOPIC[t] not in topics:
                    topics.append(TAG_TOPIC[t])
            if lv in ("A1", "A2") and not topics:
                topics.append("daily")
            if " " in w and "phrases" not in topics:
                topics.append("phrases")
            out[lv].append([w, p, ipa, uk_pron(e["phonetic"]), kk, zh, definition, "", ex or "", "", syn, ant, lv, topics])
            used.add(w)
        stats[lv] = (len(out[lv]), skipped)

    allw = [w for lv in LEVELS for w in out[lv]]
    js = "/* WordUnlock 字庫：由 tools/build_words.py 產生，請勿手動編輯（手工精修請改 words-curated.json）*/\n"
    js += "const RAW = " + json.dumps(allw, ensure_ascii=False, separators=(",", ":")) + ";\n"
    (ROOT / "words-db.js").write_text(js, encoding="utf-8")

    POS_LABEL = {"noun": ("Noun", "名詞"), "verb": ("Verb", "動詞"), "adjective": ("Adjective", "形容詞"),
                 "adverb": ("Adverb", "副詞"), "phrase": ("Phrase", "片語"), "phrasalVerb": ("Phrasal Verb", "動詞片語"),
                 "preposition": ("Preposition", "介系詞"), "pronoun": ("Pronoun", "代名詞"),
                 "conjunction": ("Conjunction", "連接詞"), "determiner": ("Determiner", "限定詞"),
                 "interjection": ("Interjection", "感嘆詞"), "number": ("Number", "數詞")}
    small = [{"w": r[0], "pos": POS_LABEL[r[1]][0], "posZh": POS_LABEL[r[1]][1], "ipa": r[2], "kk": r[4], "zh": r[5],
              "ex": r[8], "exZh": r[9], "lv": r[12]} for r in allw]
    (ROOT / "words.json").write_text(json.dumps({"version": 2, "words": small}, ensure_ascii=False, separators=(",", ":")),
                                     encoding="utf-8")
    n_ex = sum(1 for r in allw if r[8])
    print("各級字數（略過筆數）：", stats)
    print(f"總計 {len(allw)} 字；有例句 {n_ex}；有英式音標 {sum(1 for r in allw if r[3])}；有同義字 {sum(1 for r in allw if r[10])}")


if __name__ == "__main__":
    main()
