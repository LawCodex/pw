# LawCodex — Palau (`pw`)

Legislation of the Republic of Palau that is published as text on the official Government of Palau
website (<https://www.palaugov.pw>), as plain Markdown.

Part of [LawCodex](https://github.com/LawCodex): the legislation of every country as Markdown in git.

Retrieved: **2026-10-13**. Status: **minimal / partial**.

## Contents

| Category | Directory | Files |
|---|---|---:|
| Palau National Code (PNCA) titles | `pnc/` | 2 (Title 24 — Environmental Protection; Title 40 — Revenue and Taxation) |
| Republic of Palau Public Laws (RPPL), as signed | `rppl/congress-NN/` | 1 (RPPL 11-11) |
| Regulations (EQPB environmental regulations, tax regulations, civil service rules, …) | `regulations/` | 24 |
| **Total** | | **27** |

## What is NOT covered (gaps)

- **The Constitution of the Republic of Palau** and **most of the Palau National Code**: no official
  online text could be found. The Palau Judiciary site (`palausupremecourt.net`, which historically
  hosted the PNC) no longer resolves and its Internet Archive captures contain only court
  decisions/reports; `palaugov.pw` only summarises the Constitution; the OEK (`palauoek.org`) only
  tracks bills. PacLII (`paclii.org`, `pacliirms.paclii.org`), which hosts the Constitution and
  PNC, is behind a bot challenge (HTTP 403) and was not used.
- **~45 RPPL public laws** (Congresses 9–11) and some regulations posted on palaugov.pw are image-only
  scans (no OCR performed): listed by `scripts/pw_fetch_convert.py`.
- Draft/proposed regulations, guidance manuals, budget pay scales and transmittal letters were
  excluded on purpose.

## Structure

```
pnc/pnc-title-24.md                 ## DIVISION — ### Chapter — #### Subchapter — ##### § N. heading
rppl/congress-11/rppl-no-11-11.md
regulations/<slug>.md
```

## Sources and licence

- Official source: Government of the Republic of Palau, <https://www.palaugov.pw>. The list of
  documents was read from the site's public WordPress REST API (`/wp-json/wp/v2/media`, PDFs only),
  then each PDF was downloaded once (sequential, identifying User-Agent). robots.txt allows this.
- Official legislative texts of Palau, reproduced verbatim (text only) as public legal information.
  Not an official version.

## Regenerate

```sh
python3 scripts/pw_fetch_convert.py ../_raw/pw .     # needs poppler `pdftotext`
```
