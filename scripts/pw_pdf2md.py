#!/usr/bin/env python3
"""Convert a revised-edition legislation PDF (Pacific 'CAP.' layout, as produced by the
templates) — generic plain-layout conversion (convert_plain) to Markdown body text.

Uses poppler's `pdftotext -raw` (much better word spacing than pure-Python extractors).
"""
import re
import subprocess

HEADER_PATTERNS = [
    r"\bCAP\.\s*\d", r"\bVAHE\s+\d", r"^to$", r"\bPage \d+\b", r"\bPeesi \d+\b",
    r"Revised Edition", r"Tohi Lao Fakatonutonu", r"^C\s*T$", r"^[CT]$", r"^Sections$",
    r"^Clauses$", r"^Regulations$", r"^Rules$", r"^Kupu$",
]
HDR = re.compile("|".join(HEADER_PATTERNS))
TOC_HINT = re.compile(r"Arrangement of|Fokotu.?utu.?u", re.I)
ENDNOTES = re.compile(r"^(ENDNOTES|FAKAMATALA FAKALAHI)$")
PART = re.compile(r"^(PART|Part|KONGA)\s+([0-9IVXLC]+[A-Z]?)\b(.*)$")
DIVISION = re.compile(r"^(Division|DIVISION|Vahe ?[Ii]ki|VAHE ?IKI)\s+(\d+[A-Z]?)\b(.*)$")
SCHEDULE = re.compile(r"^(SCHEDULE|TEPILE|FIRST SCHEDULE|SECOND SCHEDULE|THIRD SCHEDULE|FOURTH SCHEDULE|FIFTH SCHEDULE)\b.*$")
SECTION = re.compile(r"^(\d{1,4}[A-Z]{0,2})\.?\s+(\S.{0,180})$")
LABEL = re.compile(r"^(\(\w{1,6}\)|“|\"|‘|[a-z]\)|\d+\.\s)")
DOTS = re.compile(r"\.{6,}\s*\d*\s*$")


PUA = re.compile("[\ue000-\uf8ff]")
GLUED = re.compile(r"[A-Za-z,.;:()'’-]{32,}")


def _run(path, raw):
    args = ["pdftotext"] + (["-raw"] if raw else []) + ["-enc", "UTF-8", path, "-"]
    return PUA.sub("", subprocess.run(args, capture_output=True, check=True).stdout.decode("utf-8", "replace"))


def pdf_pages(path):
    """Pages of `pdftotext -raw` text; lines where raw mode lost inter-word spaces (justified
    text) are replaced by the same line from pdftotext's default mode."""
    out = _run(path, True)
    if GLUED.search(out):
        fix = {}
        for l in _run(path, False).split("\n"):
            k = re.sub(r"\s+", "", l)
            if len(k) > 20:
                fix.setdefault(k, l.strip())
        lines = []
        for l in out.split("\n"):
            if GLUED.search(l):
                l = fix.get(re.sub(r"\s+", "", l), l)
            lines.append(l)
        out = "\n".join(lines)
    pages = out.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    return pages


def split_header(lines):
    hdr = []
    i = 0
    while i < len(lines) and i < 8 and (not lines[i].strip() or HDR.search(lines[i].strip())):
        hdr.append(lines[i].strip())
        i += 1
    return hdr, lines[i:]


def secnum(s):
    m = re.match(r"\d+", s)
    return int(m.group()) if m else -1


def convert(path):
    """Return (markdown_body, info) for a revised-edition PDF."""
    pages = pdf_pages(path)
    if not pages:
        return "", {"pages": 0}
    # title block on the cover page: lines after the "C T" marker
    cover = [l.strip() for l in pages[0].split("\n") if l.strip()]
    title_lines = set()
    if any(re.fullmatch(r"C\s*T|[CT]", l) for l in cover):
        seen = False
        for l in cover:
            if re.fullmatch(r"C\s*T|[CT]", l):
                seen = True
                continue
            if seen:
                title_lines.add(l)
    body_lines, endnote_lines, in_end = [], [], False
    for pi, page in enumerate(pages):
        lines = page.split("\n")
        if pi == 0 and (title_lines or len([l for l in lines if l.strip()]) < 15):
            continue  # cover
        hdr, rest = split_header(lines)
        if any(TOC_HINT.search(h) for h in hdr):
            continue
        rest = [l.rstrip() for l in rest]
        # strip repeated title lines at the top of the first body page
        while rest and (rest[0].strip() in title_lines or not rest[0].strip()):
            rest.pop(0)
        if any(TOC_HINT.search(l) for l in rest[:3]) and sum(bool(DOTS.search(l)) for l in rest) > 2:
            continue
        for l in rest:
            s = l.strip()
            if not s:
                continue
            if ENDNOTES.match(s) or (any("Endnotes" in h for h in hdr) and not in_end):
                in_end = True
                if ENDNOTES.match(s):
                    continue
            (endnote_lines if in_end else body_lines).append(s)
    md = structure(body_lines)
    if endnote_lines:
        md += "\n\n## Endnotes\n\n" + endnotes(endnote_lines)
    return md.strip() + "\n", {"pages": len(pages), "chars": len(md)}


def endnotes(lines):
    out, cur = [], []
    for l in lines:
        if re.fullmatch(r"\d{1,4}", l):
            if cur:
                out.append(" ".join(cur))
            cur = [l]
        else:
            cur.append(l)
    if cur:
        out.append(" ".join(cur))
    return "\n\n".join(out)


def structure(lines):
    out, para = [], []
    last = 0

    def flush():
        if para:
            out.append(" ".join(para))
            para.clear()

    skip = 0
    for i, s in enumerate(lines):
        if skip:
            skip -= 1
            continue
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        m = SECTION.match(s)
        if PART.match(s) and len(s) < 160:
            # heading text on the following all-caps line(s)
            j = i + 1
            while j < len(lines) and j <= i + 2 and lines[j].upper() == lines[j] and re.search(r"[A-Z]{3}", lines[j]) \
                    and not PART.match(lines[j]) and not DIVISION.match(lines[j]) and not SECTION.match(lines[j]) and len(lines[j]) < 100:
                s += " " + lines[j]
                j += 1
            skip = j - i - 1
            flush(); out.append("## " + s)
            continue
        if DIVISION.match(s) and len(s) < 160:
            flush(); out.append("### " + s)
            continue
        if SCHEDULE.match(s) and len(s) < 120:
            flush(); out.append("## " + s)
            last = 0
            continue
        if m and (re.search(r"\b(shall|may|hereby|amended|cited|means|is|are)\b", m.group(2)) or re.search(r"[.;:,]$", s)):
            m = None
        if m and len(s) < 160 and not re.search(r"[;,:—-]$", s) and (m.group(2)[0].isupper() or m.group(2)[0] in "‘'“\"("):
            n = secnum(m.group(1))
            if last <= n <= last + 15 and not (n == last and not re.search(r"[A-Z]$", m.group(1))):
                flush()
                out.append(f"#### {m.group(1)} {m.group(2)}")
                last = n
                continue
        if LABEL.match(s):
            flush()
        para.append(s)
        if re.search(r"[.:;—]$", s) and nxt and (LABEL.match(nxt) or nxt[:1].isupper()):
            flush()
    flush()
    return "\n\n".join(out)


def norm(l):
    return re.sub(r"\d+", "#", l.strip().lower())


def convert_plain(path):
    """Acts as published (not revised-edition layout): drop running headers/footers found on many
    pages, start at the enacting/long-title text, then structure."""
    pages = pdf_pages(path)
    import collections
    cnt = collections.Counter()
    for p in pages:
        for k in {norm(l) for l in p.split("\n") if 0 < len(l.strip()) < 90}:
            cnt[k] += 1
    thr = max(3, len(pages) * 0.4)
    hdr = {k for k, v in cnt.items() if v >= thr and not re.match(r"^(part|division|schedule|#\.?\s|\()", k)}
    lines = []
    for p in pages:
        for l in p.split("\n"):
            s = l.strip()
            if not s or norm(s) in hdr or re.fullmatch(r"-?\s*\d{1,3}\s*-?", s) or DOTS.search(s):
                continue
            lines.append(s)
    # marginal-note style: "Short title" / "1. This Act may be cited ..." -> "1 Short title" + text
    out = []
    i = 0
    while i < len(lines):
        l = lines[i]
        nx = lines[i + 1] if i + 1 < len(lines) else ""
        m = re.match(r"^(\d{1,3}[A-Z]?)\.\s*(.*)$", nx)
        if m and len(l) < 80 and l[:1].isupper() and not re.search(r"[.;:,—–-]$", l) and not PART.match(l) \
                and not re.match(r"^\d", l) and not l.isupper():
            out.append(f"{m.group(1)} {l}")
            if m.group(2):
                out.append(m.group(2))
            i += 2
            continue
        out.append(l)
        i += 1
    return structure(out) + "\n", {"pages": len(pages)}
