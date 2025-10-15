#!/usr/bin/env python3
"""
translate_mods.py
簡易: MODファイル群の英語文字列をDeepLで日本語に翻訳して上書きするツール（バックアップ付き）。
対応: .json, .xml, .properties, .yml/.yaml, .po, .txt
使い方例:
  export DEEPL_API_KEY="xxxx"
  python translate_mods.py --src en --tgt ja --backup mods_dir/
"""

import os, sys, argparse, json, time, shutil, csv, re
from pathlib import Path
import requests
import polib
import yaml
import chardet
from xml.etree import ElementTree as ET
import shelve

DEEPL_API_URL = "https://api-free.deepl.com/v2/translate"  # or paid endpoint
CACHE_DB = ".translate_cache.db"

# ---------- util ----------
def detect_encoding(path):
    b = Path(path).read_bytes()
    enc = chardet.detect(b)['encoding'] or 'utf-8'
    return enc

def call_deepl(text, src_lang, tgt_lang, api_key):
    # simple wrapper, no advanced glossary handling here
    params = {
        "auth_key": api_key,
        "text": text,
        "source_lang": src_lang.upper(),
        "target_lang": tgt_lang.upper()
    }
    resp = requests.post(DEEPL_API_URL, data=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return data["translations"][0]["text"]

# ---------- caching ----------
class TMCache:
    def __init__(self, path=CACHE_DB):
        self.db = shelve.open(path)

    def get(self, src):
        return self.db.get(src)

    def put(self, src, tgt):
        self.db[src] = tgt

    def close(self):
        self.db.close()

# ---------- file handlers ----------
def translate_json(path, translate_func, cache, args):
    enc = detect_encoding(path)
    with open(path, 'r', encoding=enc) as f:
        data = json.load(f)

    def walk(obj):
        if isinstance(obj, dict):
            return {k: walk(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [walk(x) for x in obj]
        if isinstance(obj, str):
            return translate_text(obj, translate_func, cache, args)
        return obj

    new = walk(data)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(new, f, ensure_ascii=False, indent=2)

def translate_yaml(path, translate_func, cache, args):
    enc = detect_encoding(path)
    with open(path, 'r', encoding=enc) as f:
        data = yaml.safe_load(f)
    def walk(obj):
        if isinstance(obj, dict):
            return {k: walk(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [walk(x) for x in obj]
        if isinstance(obj, str):
            return translate_text(obj, translate_func, cache, args)
        return obj
    new = walk(data)
    with open(path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(new, f, allow_unicode=True)
    
def translate_properties(path, translate_func, cache, args):
    enc = detect_encoding(path)
    lines_out = []
    with open(path, 'r', encoding=enc) as f:
        for line in f:
            if line.strip().startswith('#') or '=' not in line:
                lines_out.append(line)
                continue
            key, val = line.split('=',1)
            val_s = val.rstrip('\n')
            newval = translate_text(val_s, translate_func, cache, args)
            lines_out.append(f"{key}={newval}\n")
    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(lines_out)

def translate_txt(path, translate_func, cache, args):
    enc = detect_encoding(path)
    out_lines=[]
    with open(path, 'r', encoding=enc) as f:
        for line in f:
            s=line.rstrip('\n')
            if s.strip()=='':
                out_lines.append(line)
            else:
                out = translate_text(s, translate_func, cache, args)
                out_lines.append(out+"\n")
    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(out_lines)

def translate_po(path, translate_func, cache, args):
    po = polib.pofile(path)
    changed=False
    for entry in po:
        if entry.msgid.strip()=='':
            continue
        src = entry.msgid
        if entry.msgstr.strip()=='':
            entry.msgstr = translate_text(src, translate_func, cache, args)
            changed=True
    if changed:
        po.save(path)

def translate_xml(path, translate_func, cache, args):
    enc = detect_encoding(path)
    parser = ET.XMLParser(encoding=enc)
    tree = ET.parse(path, parser=parser)
    root = tree.getroot()
    def walk(elem):
        if elem.text and elem.text.strip():
            elem.text = translate_text(elem.text, translate_func, cache, args)
        for k,v in list(elem.attrib.items()):
            elem.attrib[k] = translate_text(v, translate_func, cache, args)
        for c in elem:
            walk(c)
    walk(root)
    tree.write(path, encoding='utf-8', xml_declaration=True)

# ---------- translate wrapper ----------
def translate_text(s, translate_func, cache, args):
    s_stripped = s.strip()
    if s_stripped=='':
        return s
    # skip placeholders or numeric lines, simple heuristics
    if args.skip_regex and re.search(args.skip_regex, s_stripped):
        return s
    cached = cache.get(s_stripped)
    if cached:
        return s.replace(s_stripped, cached)
    # call translator
    try:
        translated = translate_func(s_stripped)
        cache.put(s_stripped, translated)
        # preserve leading/trailing whitespace
        return s.replace(s_stripped, translated)
    except Exception as e:
        print("Translate error:", e, file=sys.stderr)
        return s  # fail safe

# ---------- main ----------
def main():
    p = argparse.ArgumentParser()
    p.add_argument("targets", nargs='+', help="file or directory paths")
    p.add_argument("--src", default="EN", help="source lang code (EN)")
    p.add_argument("--tgt", default="JA", help="target lang code (JA)")
    p.add_argument("--backup", action="store_true", help="backup files before overwriting")
    p.add_argument("--api-key", default=os.getenv("DEEPL_API_KEY"), help="DeepL API key")
    p.add_argument("--skip-regex", default=None, help="regex: skip translating strings that match")
    p.add_argument("--delay", type=float, default=0.6, help="delay between API calls (sec)")
    args = p.parse_args()

    if not args.api_key:
        print("DEEPL API key required (env DEEPL_API_KEY or --api-key)", file=sys.stderr)
        sys.exit(1)

    # gather files
    exts_handlers = {
        '.json': translate_json,
        '.yml': translate_yaml,
        '.yaml': translate_yaml,
        '.properties': translate_properties,
        '.txt': translate_txt,
        '.po': translate_po,
        '.xml': translate_xml
    }
    file_list=[]
    for t in args.targets:
        pth = Path(t)
        if pth.is_dir():
            for e,h in exts_handlers.items():
                file_list += list(pth.rglob(f'*{e}'))
        elif pth.is_file():
            file_list.append(pth)
        else:
            print("Not found:", t, file=sys.stderr)

    if args.backup:
        backup_dir = Path(".backup_mods_"+time.strftime("%Y%m%d%H%M%S"))
        backup_dir.mkdir(parents=True, exist_ok=True)
        for f in file_list:
            dst = backup_dir / f.name
            shutil.copy2(f, dst)
        print("Backed up files to:", backup_dir)

    cache = TMCache()
    log_rows = []
    def translate_func_factory():
        def f(text):
            # rate limit
            time.sleep(args.delay)
            return call_deepl(text, args.src, args.tgt, args.api_key)
        return f
    translate_func = translate_func_factory()

    for f in file_list:
        ext = f.suffix.lower()
        handler = exts_handlers.get(ext)
        if not handler:
            print("skip (no handler):", f)
            continue
        print("Translating:", f)
        try:
            handler(str(f), translate_func, cache, args)
            log_rows.append([str(f), "OK"])
        except Exception as e:
            print("Error processing", f, e, file=sys.stderr)
            log_rows.append([str(f), "ERROR", str(e)])

    cache.close()
    # write CSV log
    with open('translate_log.csv','w',encoding='utf-8',newline='') as csvf:
        writer = csv.writer(csvf)
        writer.writerow(['file','status','note'])
        writer.writerows(log_rows)

    print("Done. See translate_log.csv and cache:", CACHE_DB)

if __name__ == "__main__":
    main()
