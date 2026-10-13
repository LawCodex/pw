#!/usr/bin/env python3
"""Fetch Palau legislation published on the official Government of Palau website
(https://www.palaugov.pw): Republic of Palau Public Laws (RPPL), Palau National Code titles and regulations
found in the site's WordPress media library (public REST API), then convert them to Markdown.

Usage: pw_fetch_convert.py RAW_DIR OUT_DIR       (needs poppler `pdftotext`)
"""
import datetime, html, json, os, re, sys, time, unicodedata
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pw_pdf2md  # noqa: E402

API = "https://www.palaugov.pw/wp-json/wp/v2/media?mime_type=application/pdf&per_page=100&page={}&_fields=id,source_url,title,date"
UA = "LawCodex/1.0 (+https://github.com/LawCodex)"
RAW, OUT = sys.argv[1], sys.argv[2]
S = requests.Session()
S.headers["User-Agent"] = UA
TODAY = datetime.date.today().isoformat()


def slug(s, n=90):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:n].rstrip("-")


def yq(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def media():
    p = os.path.join(RAW, "media.json")
    if os.path.exists(p):
        return json.load(open(p))
    out, page = [], 1
    while True:
        r = S.get(API.format(page), timeout=120)
        if r.status_code != 200:
            break
        d = r.json()
        if not d:
            break
        out += d
        page += 1
        time.sleep(1)
    json.dump(out, open(p, "w"))
    return out


def classify(m):
    t = html.unescape(m["title"]["rendered"])
    u = m["source_url"]
    if re.search(r"transmittal|payscale|salary|pay scale", t + u, re.I):
        return None
    rp = re.search(r"RPPL\s*(No\.?\s*)?(\d+)\s*-\s*(\d+)", t, re.I) or re.search(r"RPPL-(No\.-)?(\d+)-(\d+)", u, re.I)
    if rp:
        return ("rppl", f"RPPL No. {rp.group(2)}-{int(rp.group(3))}", t)
    tn = re.search(r"(Palau National Code|PNCA)\s*Title\s*(\d+)", t, re.I)
    if tn:
        return ("pnc", f"PNC Title {tn.group(2)}", t)
    if re.search(r"regulation", t, re.I) and not re.search(r"draft|proposed|manual|guidance|grid", t, re.I):
        key = re.sub(r"[-_ ]?\d*$", "", re.sub(r"\W+", " ", t).strip().lower())
        return ("reg", key, t)
    return None


def dl(url):
    p = os.path.join(RAW, "pdf", re.sub(r"[^A-Za-z0-9._-]+", "_", url.split("/uploads/")[-1]))
    if os.path.exists(p):
        return p
    os.makedirs(os.path.dirname(p), exist_ok=True)
    for a in range(4):
        r = S.get(url, timeout=300)
        if r.status_code == 200 and r.content[:5] == b"%PDF-" and b"%%EOF" in r.content[-2048:]:
            open(p, "wb").write(r.content)
            time.sleep(1)
            return p
        time.sleep(5 * 2 ** a)
    return None


def convert_pnc(path):
    """Palau National Code title PDF -> Markdown (Division/Chapter/Subchapter/section headings)."""
    import subprocess
    txt = subprocess.run(["pdftotext", "-raw", "-enc", "UTF-8", path, "-"], capture_output=True, check=True).stdout.decode()
    lines = []
    for page in txt.split("\f"):
        pl = [l.strip() for l in page.split("\n")]
        k = 0
        while k < len(pl) and k < 3 and (re.search(r"\d+ PNCA §", pl[k]) or re.fullmatch(r"\d+\s*-\s*\d+", pl[k]) or not pl[k]):
            k += 1
        lines += [l for l in pl[k:] if l]
    out, para = [], []

    def flush():
        if para:
            out.append(" ".join(para))
            para.clear()

    i = 0
    while i < len(lines):
        l = lines[i]
        nx = lines[i + 1] if i + 1 < len(lines) else ""
        if re.fullmatch(r"TITLE \d+", l):
            flush(); i += 2; continue  # repeated in H1
        if re.fullmatch(r"DIVISION \d+", l):
            flush(); out.append(f"## {l} — {nx}"); i += 2; continue
        if re.fullmatch(r"Chapter \d+[A-Z]?", l):
            flush(); out.append(f"### {l} — {nx}"); i += 2; continue
        if re.fullmatch(r"Subchapter [IVXLC]+[A-Z]?", l):
            flush(); out.append(f"#### {l} — {nx}"); i += 2; continue
        if l.startswith("§ "):
            if nx.startswith("§ ") or (re.match(r"^(Chapter|Subchapter|DIVISION) ", nx)):
                i += 1; continue  # table of sections
            flush(); out.append("##### " + l); i += 1; continue
        if l in ("Source", "Cross-reference", "Notes", "Note", "Case annotations", "Commission Comment"):
            flush(); out.append(f"**{l}**"); i += 1; continue
        if re.match(r"^\(\w{1,5}\)", l):
            flush()
        para.append(l)
        if re.search(r"[.:;]$", l) and nx[:1].isupper():
            flush()
        i += 1
    flush()
    return "\n\n".join(out) + "\n"


def main():
    os.makedirs(RAW, exist_ok=True)
    picked = {}
    for m in media():
        c = classify(m)
        if not c:
            continue
        kind, ident, title = c
        # several uploads of the same law: keep the most recent upload
        if ident not in picked or m["date"] > picked[ident][0]["date"]:
            picked[ident] = (m, kind, title)
    counts, problems = {}, []
    for ident, (m, kind, title) in sorted(picked.items()):
        p = dl(m["source_url"])
        if not p:
            problems.append(("download", m["source_url"]))
            continue
        body = convert_pnc(p) if kind == "pnc" else pw_pdf2md.convert_plain(p)[0]
        if len(body.strip()) < 300:
            problems.append(("no text (scan)", m["source_url"]))
            continue
        clean_title = re.sub(r"\s+", " ", title).strip()
        if kind == "rppl":
            cong = ident.split()[-1].split("-")[0]
            rel = os.path.join("rppl", f"congress-{int(cong):02d}", slug(ident) + ".md")
            typ = "act"
        elif kind == "pnc":
            rel = os.path.join("pnc", slug(ident) + ".md")
            typ = "code"
        else:
            rel = os.path.join("regulations", slug(clean_title) + ".md")
            typ = "regulation"
            ident = ""
        fm = ["---", f"title: {yq(clean_title)}", f"identifier: {yq(ident)}", f"type: {typ}",
              "jurisdiction: pw", "language: en", "status: unknown",
              f"source: {yq(m['source_url'])}", f"published_on_site: {m['date'][:10]}",
              'format_note: "text extracted from the official PDF; layout not preserved"',
              f"retrieved: {TODAY}", "---", ""]
        out = os.path.join(OUT, rel)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(fm) + f"# {clean_title}\n\n" + body)
        counts[kind] = counts.get(kind, 0) + 1
    print(counts)
    print(len(problems), problems)


if __name__ == "__main__":
    main()
