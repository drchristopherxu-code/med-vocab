#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
convert_vocab.py —— 词表转换工具

把现有词表一键转换成背单词 App 可用的 vocab/*.js 词库文件，并在 manifest.js 登记。

支持两种输入：
  1) docx  「医学专有名词解释_双语术语表」格式的 Word 文档：
     每章一个 4 列表格（术语 Term / 英文释义 Definition / 中文译名 / 中文解释），
     按章拆分为多个学科词库。
  2) csv   通用 CSV / TSV 词表，列名可识别：
     word|term|术语, def_en|definition|英文释义, def_zh|中文解释|translation,
     name_zh|中文译名, phonetic|音标, pos|词性, example|例句, example_zh|例句翻译,
     etymology|词根, tags|标签

用法示例：
  # 从 docx 术语表生成全部学科词库
  python3 tools/convert_vocab.py --docx "/path/20_医学专有名词解释_双语术语表.docx" --out vocab

  # 从 CSV 追加一个自定义词库
  python3 tools/convert_vocab.py --csv mywords.csv --bank-id mywords \
      --label "自定义词库" --out vocab

  # 同一学科的两套词库（如核心 + "-full" 全集）合并去重成一个词库
  python3 tools/convert_vocab.py --merge --out vocab

生成：
  vocab/vocab_<id>.js   每个词库一个文件（window.registerVocab({...})）
  vocab/manifest.js     词库清单 window.VOCAB_MANIFEST（docx 模式会重建清单；
                        csv 模式在清单后追加/替换对应条目）

合并去重规则（--merge）：
  撞词判定 = 单词大小写/空格/连接号（en dash、em dash）归一后相同；
  保留 def_en + def_zh + example + example_zh + etymology 文本量更大的那条，
  完全平局时保留基础词库（核心版）的版本；合并后按字母序（忽略大小写）重排。
"""

import argparse
import csv
import json
import os
import re
import sys
import unicodedata
import zipfile

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

# docx 章节（按英文标题）→ 词库 id / 中文名
CHAPTER_MAP = {
    "Biochemistry": ("biochem", "生物化学"),
    "Biostatistics and Epidemiology": ("biostat", "生物统计与流行病学"),
    "General Pathology": ("genpath", "病理学总论"),
    "Immunology": ("immun", "免疫学"),
    "Cardiovascular System": ("cardio", "心血管系统"),
    "Pulmonary and Critical Care": ("pulm", "呼吸与危重症"),
    "Renal, Urinary, and Electrolytes": ("renal", "肾脏泌尿与电解质"),
    "Endocrine System": ("endo", "内分泌系统"),
    "Gastrointestinal and Nutrition": ("gi", "消化与营养"),
    "Rheumatology, Orthopedics, and Sports Medicine": ("rheum", "风湿病学骨科与运动医学"),
    "Dermatology": ("derm", "皮肤病学"),
    "Ophthalmology": ("ophtho", "眼科学"),
    "Otolaryngology": ("ent", "耳鼻咽喉科学"),
    "Female Reproductive System": ("gyn", "女性生殖系统"),
    "Male Reproductive System": ("male", "男性生殖系统"),
    "Pregnancy and Obstetrics": ("ob", "妊娠与产科"),
    "Psychiatry and Behavioral Medicine": ("psych", "精神病学与行为医学"),
    "Pharmacology": ("pharm", "药理学"),
    "Toxicology and Emergency Medicine": ("tox", "中毒与急救"),
}

CSV_FIELDS = {
    "word": ("word", "term", "术语", "单词"),
    "def_en": ("def_en", "definition", "英文释义", "english"),
    "def_zh": ("def_zh", "translation", "中文解释", "中文释义", "chinese"),
    "name_zh": ("name_zh", "中文译名"),
    "phonetic": ("phonetic", "音标", "ipa"),
    "pos": ("pos", "词性"),
    "example": ("example", "例句"),
    "example_zh": ("example_zh", "例句翻译"),
    "etymology": ("etymology", "词根", "词根词缀"),
    "audio": ("audio", "音频"),
}


def clean(text):
    """合并空白、去掉首尾，保留单行文本。"""
    if text is None:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


# ---------------------------------------------------------------- docx 解析（表格模式）
def parse_docx(path):
    """返回 [(chapter_header, [(term, def_en, name_zh, def_zh), ...]), ...]"""
    with zipfile.ZipFile(path) as z:
        import xml.etree.ElementTree as ET

        root = ET.fromstring(z.read("word/document.xml"))
    body = root.find(f"{{{W_NS}}}body")

    chapters, current = [], None
    for el in body:
        tag = el.tag.split("}")[1]
        if tag == "p":
            text = "".join(t.text or "" for t in el.iter(f"{{{W_NS}}}t")).strip()
            # 形如 “第 2 章　生物化学　Biochemistry” 的章节标题
            if text.startswith("第 ") and "\u3000" in text and "章" in text.split("\u3000")[0]:
                current = text
        elif tag == "tbl" and current:
            rows = []
            for tr in el.findall(f"{{{W_NS}}}tr"):
                cells = []
                for tc in tr.findall(f"{{{W_NS}}}tc"):
                    cells.append("".join(t.text or "" for t in tc.iter(f"{{{W_NS}}}t")))
                if len(cells) >= 4 and clean(cells[0]) and clean(cells[0]) != "术语 Term":
                    rows.append((clean(cells[0]), clean(cells[1]), clean(cells[2]), clean(cells[3])))
            if rows:
                chapters.append((current, rows))
                current = None
    return chapters


def header_to_bank(header, fallback_idx):
    """'第 2 章　生物化学　Biochemistry' → (id, label_zh, label_en)"""
    parts = [p.strip() for p in header.split("\u3000") if p.strip()]
    zh = parts[1] if len(parts) > 1 else parts[0]
    en = parts[-1] if len(parts) > 2 else ""
    if en in CHAPTER_MAP:
        bid, zh_known = CHAPTER_MAP[en]
        return bid, zh_known, en
    slug = re.sub(r"[^a-z0-9]+", "-", en.lower()).strip("-") or f"bank{fallback_idx}"
    return slug, zh, en


def parse_docx_paragraphs(path):
    """
    解析「段落式」双语术语表：每条词条占 4 个连续段落
    （英文术语 / 中文译名 / 英文释义 / 中文解释）。学科部分形如：
        1. Biochemistry          ← 学科头
        生物化学                  ← 学科中文名
        622 terms · …            ← 两行词条数说明（跳过）
        622 个词条 · …
        3' polyadenylation       ← 词条组开始
        3'端多聚腺苷酸化
        Template-independent …
        于mRNA 3'端…
    返回 [(subject_en, subject_zh, [(term, name_zh, def_en, def_zh), ...]), ...]
    """
    with zipfile.ZipFile(path) as z:
        import xml.etree.ElementTree as ET

        root = ET.fromstring(z.read("word/document.xml"))
    body = root.find(f"{{{W_NS}}}body")

    paras = []
    for el in body:
        if el.tag.split("}")[1] == "p":
            paras.append("".join(t.text or "" for t in el.iter(f"{{{W_NS}}}t")).strip())

    hdr = re.compile(r"^(\d+)\.\s+(\S.*)$")
    count_en = re.compile(r"^\d+\s*terms\b", re.I)
    count_zh = re.compile(r"个词条")

    subjects, cur = [], None
    for p in paras:
        if cur is None:
            m = hdr.match(p)
            if m:
                cur = {"en": m.group(2).strip(), "zh": "", "entries": [], "buf": [], "state": "zh", "skips": 0}
                subjects.append(cur)
            continue
        if cur["state"] == "zh":
            cur["zh"] = p
            cur["state"] = "counts"
            continue
        if cur["state"] == "counts":
            if cur["skips"] < 2 and (count_en.match(p) or count_zh.search(p)):
                cur["skips"] += 1
                if cur["skips"] == 2:
                    cur["state"] = "entries"
                continue
            cur["state"] = "entries"  # 计数行缺失时容错进入词条
        # state == entries
        if not cur["buf"] and hdr.match(p):
            cur = {"en": hdr.match(p).group(2).strip(), "zh": "", "entries": [], "buf": [], "state": "zh", "skips": 0}
            subjects.append(cur)
            continue
        cur["buf"].append(p)
        if len(cur["buf"]) == 4:
            cur["entries"].append(tuple(cur["buf"]))
            cur["buf"] = []
    if cur and cur["buf"]:
        raise SystemExit(f"学科「{cur['en']}」末尾残留 {len(cur['buf'])} 段，无法凑成 4 段词条组：{cur['buf']}")
    return [(s["en"], s["zh"], s["entries"]) for s in subjects]


def paragraph_banks(path, source_name, id_suffix="", label_suffix=""):
    banks = []
    for en, zh, entries in parse_docx_paragraphs(path):
        if en in CHAPTER_MAP:
            base_id, zh_known = CHAPTER_MAP[en]
            zh = zh or zh_known
        else:
            base_id = re.sub(r"[^a-z0-9]+", "-", en.lower()).strip("-")
        words, seen = [], set()
        for term, name_zh, def_en, def_zh in entries:
            key = term.lower()
            if key in seen:
                print(f"  [跳过重复] {base_id}: {term}", file=sys.stderr)
                continue
            seen.add(key)
            words.append({
                "word": term,
                "phonetic": "",
                "pos": "",
                "def_en": def_en,
                "def_zh": def_zh,
                "name_zh": name_zh,
                "example": "",
                "example_zh": "",
                "etymology": "",
                "tags": [en] if en else [],
                "audio": "",
            })
        banks.append({
            "id": base_id + id_suffix,
            "label": f"{zh} · {en}{label_suffix}",
            "source": source_name,
            "words": words,
        })
    return banks


def docx_banks(path, source_name, id_suffix="", label_suffix=""):
    chapters = parse_docx(path)
    if chapters:  # 表格模式：每章一个 4 列表
        banks = table_mode_banks(chapters, source_name, id_suffix, label_suffix)
    else:         # 段落模式：4 段一组
        banks = paragraph_banks(path, source_name, id_suffix, label_suffix)
    return banks


def table_mode_banks(chapters, source_name, id_suffix="", label_suffix=""):
    banks = []
    for i, (header, rows) in enumerate(chapters):
        bid, zh, en = header_to_bank(header, i)
        words, seen = [], set()
        for term, def_en, name_zh, def_zh in rows:
            key = term.lower()
            if key in seen:
                print(f"  [跳过重复] {bid}: {term}", file=sys.stderr)
                continue
            seen.add(key)
            words.append({
                "word": term,
                "phonetic": "",
                "pos": "",
                "def_en": def_en,
                "def_zh": def_zh,
                "name_zh": name_zh,
                "example": "",
                "example_zh": "",
                "etymology": "",
                "tags": [en] if en else [],
                "audio": "",
            })
        label = f"{zh} · {en}" if en else zh
        banks.append({
            "id": bid + id_suffix,
            "label": label + label_suffix,
            "source": source_name,
            "words": words,
        })
    return banks


# ---------------------------------------------------------------- csv 解析
def csv_bank(path, bank_id, label, source=None):
    with open(path, newline="", encoding="utf-8-sig") as f:
        sample = f.read(4096)
        f.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
        reader = csv.DictReader(f, dialect=dialect)
        headers = {re.sub(r"[\s_]+", "", (h or "").lower()): h for h in (reader.fieldnames or [])}

        colmap = {}
        for field, aliases in CSV_FIELDS.items():
            for alias in aliases:
                key = re.sub(r"[\s_]+", "", alias.lower())
                if key in headers:
                    colmap[field] = headers[key]
                    break
        if "word" not in colmap or ("def_en" not in colmap and "def_zh" not in colmap):
            raise SystemExit(f"CSV 缺少必需列（word + def_en/def_zh）。识别到的列：{reader.fieldnames}")

        words, seen = [], set()
        for row in reader:
            term = clean(row.get(colmap["word"], ""))
            if not term:
                continue
            key = term.lower()
            if key in seen:
                continue
            seen.add(key)
            entry = {"word": term, "phonetic": "", "pos": "", "def_en": "", "def_zh": "",
                     "name_zh": "", "example": "", "example_zh": "", "etymology": "",
                     "tags": [], "audio": ""}
            for field, col in colmap.items():
                if field == "word":
                    continue
                val = clean(row.get(col, ""))
                if field == "tags":
                    entry["tags"] = [t.strip() for t in re.split(r"[;；|,，]", val) if t.strip()]
                else:
                    entry[field] = val
            if not entry["name_zh"] and entry["def_zh"]:
                entry["name_zh"] = entry["def_zh"]
            words.append(entry)
    return {"id": bank_id, "label": label, "source": source or os.path.basename(path), "words": words}


# ---------------------------------------------------------------- 输出
def js_escape(s):
    return json.dumps(s, ensure_ascii=False)


def write_bank(bank, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    fname = f"vocab_{bank['id']}.js"
    lines = [
        "// 由 tools/convert_vocab.py 自动生成 —— 请勿手工编辑；重新运行脚本会覆盖本文件。",
        f"// 词库：{bank['label']}（{len(bank['words'])} 词）",
        "window.registerVocab({",
        f"  id: {js_escape(bank['id'])},",
        f"  label: {js_escape(bank['label'])},",
        f"  source: {js_escape(bank['source'])},",
        "  words: [",
    ]
    for i, w in enumerate(bank["words"]):
        comma = "," if i < len(bank["words"]) - 1 else ""
        lines.append("    " + json.dumps(w, ensure_ascii=False) + comma)
    lines += ["  ]", "});", ""]
    with open(os.path.join(out_dir, fname), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return fname


def manifest_path(out_dir):
    return os.path.join(out_dir, "manifest.js")


def read_manifest(out_dir):
    """读取 manifest.js 的词库条目列表（文件不存在时返回空表）。"""
    mpath = manifest_path(out_dir)
    if not os.path.exists(mpath):
        return []
    entries = []
    for m in re.finditer(r"\{[^{}]*\}", open(mpath, encoding="utf-8").read()):
        try:
            obj = json.loads(m.group(0).replace("'", '"'))
        except Exception:
            continue
        if obj.get("id"):
            entries.append(obj)
    return entries


def write_manifest_entries(entries, out_dir):
    lines = ["// 由 tools/convert_vocab.py 自动生成 —— 词库清单；新增词库可在此登记。",
             "window.VOCAB_MANIFEST = ["]
    for e in entries:
        lines.append("  " + json.dumps(e, ensure_ascii=False) + ",")
    lines += ["];", ""]
    with open(manifest_path(out_dir), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def write_manifest(banks, out_dir, replace_docx_only=False):
    entries = read_manifest(out_dir) if replace_docx_only else []
    keep = [e for e in entries if e.get("source") != banks[0]["source"]] if banks else entries
    for b in banks:
        keep = [e for e in keep if e["id"] != b["id"]] + [{
            "id": b["id"],
            "label": b["label"],
            "file": f"vocab/vocab_{b['id']}.js",
            "count": len(b["words"]),
        }]
    write_manifest_entries(keep, out_dir)


# ---------------------------------------------------------------- 合并去重
def read_bank(path):
    """读取已生成的 vocab_*.js，返回 (id, label, source, words)。"""
    txt = open(path, encoding="utf-8").read()

    def field(name):
        m = re.search(rf'^\s*{name}: "(.*)",$', txt, re.M)
        return m.group(1) if m else ""

    m = re.search(r"\n\s*words: \[\n(.*?)\n\s*\],?\n", txt, re.S)
    if not m:
        raise ValueError(f"未找到 words 数组：{path}")
    words = []
    for line in m.group(1).split("\n"):
        line = line.strip().rstrip(",")
        if not line:
            continue
        if not line.startswith("{"):
            raise ValueError(f"词条行无法解析：{path} → {line[:60]}")
        words.append(json.loads(line))
    return field("id"), field("label"), field("source"), words


def norm_word(s):
    """撞词判定用的归一化：忽略大小写、连续空白与连接号变体。"""
    s = unicodedata.normalize("NFKD", str(s))
    for dash in ("\u2013", "\u2014", "\u2212"):
        s = s.replace(dash, "-")
    return re.sub(r"\s+", " ", s.replace("\u2019", "'")).strip().lower()


def richness(w):
    """词条的信息量：释义、例句、词根的文本总量。"""
    return sum(len(str(w.get(k) or "")) for k in
               ("def_en", "def_zh", "example", "example_zh", "etymology"))


def merge_banks(out_dir, suffix="-full"):
    """把 <id> 与 <id><suffix> 两套词库合并去重成 <id>，删除后者并更新清单。"""
    entries = read_manifest(out_dir)
    by_id = {e["id"]: e for e in entries}
    base_of_full = lambda fid: fid[: -len(suffix)]
    bases = [e["id"] for e in entries
             if not e["id"].endswith(suffix) and e["id"] + suffix in by_id]
    orphans = [e["id"] for e in entries
               if e["id"].endswith(suffix) and base_of_full(e["id"]) not in by_id]
    if not bases:
        print(f"没有可合并的词库对（后缀 {suffix}）；清单保持 {len(entries)} 个条目。")
        return
    counts = {}
    removed_total = 0
    for bid in bases:
        base_e, full_e = by_id[bid], by_id[bid + suffix]
        _, _, base_src, base_words = read_bank(os.path.join(out_dir, os.path.basename(base_e["file"])))
        _, _, full_src, full_words = read_bank(os.path.join(out_dir, os.path.basename(full_e["file"])))
        chosen = {}
        for w in base_words + full_words:
            k = norm_word(w["word"])
            cur = chosen.get(k)
            # 严格大于：文本量完全相同时保留基础词库（核心版）的释义
            if cur is None or richness(w) > richness(cur):
                chosen[k] = w
        words = [chosen[k] for k in sorted(chosen)]
        removed = len(base_words) + len(full_words) - len(words)
        removed_total += removed
        counts[bid] = len(words)
        write_bank({"id": bid, "label": base_e["label"],
                    "source": f"{base_src} + {full_src}（合并去重）",
                    "words": words}, out_dir)
        os.remove(os.path.join(out_dir, os.path.basename(full_e["file"])))
        print(f"  ✓ {bid:8s} 核心{len(base_words):4d} + 全集{len(full_words):4d} "
              f"→ {len(words):4d} 词（去重 {removed}）")

    new_entries = []
    for e in entries:
        if e["id"].endswith(suffix) and base_of_full(e["id"]) in counts:
            continue
        if e["id"] in counts:
            e = dict(e, count=counts[e["id"]])
        new_entries.append(e)
    write_manifest_entries(new_entries, out_dir)
    total = sum(e.get("count", 0) for e in new_entries)
    print(f"合并 {len(bases)} 对 → {len(new_entries)} 个词库 / {total} 词，"
          f"去重 {removed_total} 条 → {manifest_path(out_dir)}")
    if orphans:
        print(f"提示：{len(orphans)} 个带 {suffix} 后缀的词库没有对应基础库，未做合并："
              f"{', '.join(orphans)}")


def main():
    ap = argparse.ArgumentParser(description="词表 → 背单词 App 词库转换器")
    ap.add_argument("--docx", help="双语术语表 docx 路径（按章拆分为多个词库；自动识别表格/段落两种排版）")
    ap.add_argument("--csv", help="通用 CSV/TSV 词表路径（生成单个词库）")
    ap.add_argument("--bank-id", help="CSV 模式词库 id")
    ap.add_argument("--label", help="CSV 模式词库显示名")
    ap.add_argument("--id-suffix", default="", help="词库 id 后缀（如 -full，用于同一学科多套词库共存）")
    ap.add_argument("--label-suffix", default="", help="词库显示名后缀（如 ' · 全集'）")
    ap.add_argument("--merge", action="store_true",
                    help="把 <id> 与 <id>+后缀 两套词库合并去重成一个词库")
    ap.add_argument("--merge-suffix", default="-full",
                    help="合并模式下视为同一学科第二套词库的 id 后缀（默认 -full）")
    ap.add_argument("--out", default="vocab", help="输出目录（默认 vocab/）")
    args = ap.parse_args()

    if args.merge:
        merge_banks(args.out, args.merge_suffix)
        return

    if not args.docx and not args.csv:
        ap.error("需要 --docx 或 --csv 之一（或使用 --merge 合并同词库）")

    if args.docx:
        source = os.path.basename(args.docx)
        banks = docx_banks(args.docx, source, args.id_suffix, args.label_suffix)
        for b in banks:
            name = write_bank(b, args.out)
            print(f"  ✓ {name:32s} {b['label']}  {len(b['words'])} 词")
        # 保留 manifest 中来自其他来源的词库条目，替换同 id 条目
        write_manifest(banks, args.out, replace_docx_only=True)
        total = sum(len(b["words"]) for b in banks)
        print(f"共 {len(banks)} 个词库 / {total} 词 → {args.out}/manifest.js")
    else:
        bank = csv_bank(args.csv, args.bank_id or "custom",
                        args.label or "自定义词库")
        name = write_bank(bank, args.out)
        print(f"  ✓ {name}  {bank['label']}  {len(bank['words'])} 词")
        write_manifest([bank], args.out, replace_docx_only=True)
        print(f"manifest 已更新 → {args.out}/manifest.js")


if __name__ == "__main__":
    main()
