from __future__ import annotations

import html
import json
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parent
PDF_PATH = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else Path("/Users/min/Downloads/독서 노트.pdf")
POST_START_RE = re.compile(r"(?m)^\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}\s+https?://\S+")


def compact_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def dedupe_export_echo(value: str) -> str:
    value = compact_spaces(value)
    if not value:
        return value
    if len(value) % 2 == 0:
        half = len(value) // 2
        if value[:half] == value[half:]:
            return value[:half].strip()
    words = value.split()
    if len(words) % 2 == 0:
        half = len(words) // 2
        if words[:half] == words[half:]:
            return " ".join(words[:half]).strip()
    return value


def slugify(title: str, index: int) -> str:
    normalized = unicodedata.normalize("NFC", title).lower()
    slug = re.sub(r"[^0-9a-z가-힣]+", "-", normalized)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return f"note-{index:02d}-{slug[:44] or 'book'}"


def extract_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def parse_header(lines: list[str]) -> tuple[str, str, str]:
    match = re.match(r"(\d{4}/\d{2}/\d{2})\s+(\d{2}:\d{2})\s+(https?://\S+)", lines[0])
    if not match:
        return "", "", ""
    return match.group(1), match.group(2), match.group(3)


def parse_title_and_rating(block: str, lines: list[str]) -> tuple[str, str]:
    top = "\n".join(lines[1:8])
    title_match = re.search(r"(.+?)-\s*소장점수\s*([0-9]+(?:\.[0-9]+)?)/10", top, re.S)
    if title_match:
        return dedupe_export_echo(title_match.group(1).replace("\n", " ")), title_match.group(2)

    title = dedupe_export_echo(lines[1] if len(lines) > 1 else "제목 없음")
    title = re.sub(r"\s*-\s*$", "", title).strip()
    rating_match = re.search(r"소장점수\s*([0-9]+(?:\.[0-9]+)?)/10", block)
    return title, rating_match.group(1) if rating_match else ""


def parse_one_liner(block: str) -> tuple[str, bool]:
    marker = re.search(r"한줄평\s*:.*?(?:\n|$)", block, re.S)
    if marker:
        for raw_line in block[marker.end() :].splitlines():
            line = dedupe_export_echo(raw_line)
            if not line:
                continue
            if "소장가치" in line or re.match(r"^\d+\s*·", line):
                continue
            if re.match(r"^\d+점|^\d+~\d+점|^9~10", line):
                continue
            return line, False

    for raw_line in cleaned_body_lines(block):
        line = dedupe_export_echo(raw_line)
        if len(line) >= 18:
            return line[:120].rstrip() + ("..." if len(line) > 120 else ""), True
    return "한줄평 없음", True


def cleaned_body_lines(block: str) -> list[str]:
    lines = [dedupe_export_echo(line) for line in block.splitlines()]
    cleaned: list[str] = []
    skip_scale = False
    seen_recent: list[str] = []

    for line in lines:
        if not line:
            continue
        if re.match(r"^\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}\s+https?://", line):
            continue
        if line == "독서" or line == "독서독서":
            continue
        if re.search(r"소장점수\s*[0-9]+(?:\.[0-9]+)?/10", line):
            continue
        if "한줄평" in line:
            continue
        if "소장가치 스케일러" in line:
            skip_scale = True
            continue
        if skip_scale and (
            re.match(r"^(1점|3~4점|5~6점|7~8점|9~10)", line)
            or "쓰레기" in line
            or "빌려" in line
            or "후손에게" in line
        ):
            continue
        skip_scale = False
        if re.match(r"^\d+\s*·\s*아조씨의 개소리$", line):
            continue
        if line in {"blog.naver.com", "m.blog.naver.com", "x.com"}:
            continue
        if seen_recent and line == seen_recent[-1]:
            continue
        seen_recent.append(line)
        if len(seen_recent) > 6:
            seen_recent.pop(0)
        cleaned.append(line)
    return cleaned


def parse_posts(text: str) -> list[dict[str, object]]:
    starts = list(POST_START_RE.finditer(text))
    entries = []

    for index, start in enumerate(starts, start=1):
        end = starts[index].start() if index < len(starts) else len(text)
        block = text[start.start() : end]
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue

        date, time, url = parse_header(lines)
        title, rating = parse_title_and_rating(block, lines)
        one_liner, one_liner_generated = parse_one_liner(block)
        body = cleaned_body_lines(block)

        entries.append(
            {
                "index": index,
                "slug": slugify(title, index),
                "date": date,
                "time": time,
                "url": url,
                "title": title,
                "rating": rating,
                "ratingNumber": float(rating) if rating else None,
                "oneLiner": one_liner,
                "oneLinerGenerated": one_liner_generated,
                "body": body,
            }
        )
    return entries


def score_label(rating: str) -> str:
    if not rating:
        return "점수 없음"
    return f"{rating}/10"


def score_class(rating_number: float | None) -> str:
    if rating_number is None:
        return "score-none"
    if rating_number >= 9:
        return "score-legend"
    if rating_number >= 7:
        return "score-buy"
    if rating_number >= 5:
        return "score-neutral"
    if rating_number >= 3:
        return "score-borrow"
    return "score-low"


def render_overview(entries: list[dict[str, object]]) -> str:
    rows = []
    for entry in entries:
        rows.append(
            f"""
            <a class="book-row" href="#{html.escape(str(entry["slug"]))}" data-rating="{html.escape(str(entry["ratingNumber"] or ""))}" data-search="{html.escape((str(entry["title"]) + " " + str(entry["oneLiner"])).lower())}">
              <span class="row-score {score_class(entry["ratingNumber"])}">{html.escape(score_label(str(entry["rating"])))}</span>
              <span class="row-title">{html.escape(str(entry["title"]))}</span>
              <span class="row-line">{html.escape(str(entry["oneLiner"]))}</span>
              <span class="row-date">{html.escape(str(entry["date"]).replace("/", "."))}</span>
            </a>
            """
        )
    return "\n".join(rows)


def render_details(entries: list[dict[str, object]]) -> str:
    articles = []
    for entry in entries:
        body = "\n".join(f"<p>{html.escape(line)}</p>" for line in entry["body"][:80])
        generated_note = (
            '<span class="generated-note">본문 첫머리에서 만든 임시 한줄평</span>'
            if entry["oneLinerGenerated"]
            else ""
        )
        articles.append(
            f"""
            <article class="note" id="{html.escape(str(entry["slug"]))}">
              <div class="note-head">
                <a class="back-link" href="#library">목록</a>
                <span class="note-score {score_class(entry["ratingNumber"])}">{html.escape(score_label(str(entry["rating"])))}</span>
              </div>
              <h2>{html.escape(str(entry["title"]))}</h2>
              <p class="note-meta">{html.escape(str(entry["date"]).replace("/", "."))} · <a href="{html.escape(str(entry["url"]))}" target="_blank" rel="noopener">원문 보기</a></p>
              <blockquote>{html.escape(str(entry["oneLiner"]))}</blockquote>
              {generated_note}
              <div class="body-text">{body}</div>
            </article>
            """
        )
    return "\n".join(articles)


def render_html(entries: list[dict[str, object]], source_name: str) -> str:
    ratings = [entry["ratingNumber"] for entry in entries if entry["ratingNumber"] is not None]
    average = sum(ratings) / len(ratings) if ratings else 0
    high_count = sum(1 for rating in ratings if rating >= 9)
    first_date = entries[-1]["date"].replace("/", ".") if entries else ""
    last_date = entries[0]["date"].replace("/", ".") if entries else ""
    generated_at = datetime.now().strftime("%Y.%m.%d %H:%M")
    data_json = html.escape(json.dumps(entries, ensure_ascii=False), quote=False)

    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>독서록 아카이브</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #151515;
      --muted: #68635d;
      --line: #ded8cf;
      --paper: #fbfaf7;
      --panel: #ffffff;
      --accent: #0f766e;
      --accent-soft: #d8f1ec;
      --gold: #8a5a00;
      --blue: #245c9e;
      --green: #256f47;
      --gray: #5d6268;
      --red: #9f2f2f;
      --shadow: 0 20px 45px rgba(31, 26, 18, .08);
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Noto Sans KR", "Segoe UI", sans-serif;
      background: var(--paper);
      color: var(--ink);
      line-height: 1.65;
    }}
    a {{ color: inherit; }}
    .wrap {{ width: min(1120px, calc(100% - 32px)); margin: 0 auto; }}
    header {{
      border-bottom: 1px solid var(--line);
      background: linear-gradient(180deg, #fff 0%, #fbfaf7 100%);
    }}
    .hero {{
      min-height: 48vh;
      display: grid;
      align-content: center;
      gap: 28px;
      padding: 72px 0 44px;
    }}
    .kicker {{
      margin: 0;
      color: var(--accent);
      font-size: 14px;
      font-weight: 800;
      letter-spacing: 0;
    }}
    h1 {{
      margin: 0;
      max-width: 760px;
      font-family: ui-serif, "New York", "Apple SD Gothic Neo", "Noto Serif KR", serif;
      font-size: clamp(42px, 7vw, 78px);
      line-height: 1.05;
      letter-spacing: 0;
    }}
    .intro {{
      margin: 0;
      max-width: 760px;
      color: #3f3a35;
      font-size: 18px;
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      max-width: 880px;
    }}
    .stat {{
      border-left: 3px solid var(--accent);
      padding: 10px 14px;
      background: #fff;
      box-shadow: var(--shadow);
    }}
    .stat strong {{ display: block; font-size: 24px; line-height: 1.1; }}
    .stat span {{ color: var(--muted); font-size: 13px; }}
    main {{ padding: 34px 0 80px; }}
    .toolbar {{
      position: sticky;
      top: 0;
      z-index: 10;
      padding: 14px 0;
      background: color-mix(in srgb, var(--paper) 92%, transparent);
      backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--line);
    }}
    .toolbar-inner {{
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 12px;
      align-items: center;
    }}
    .search {{
      width: 100%;
      border: 1px solid var(--line);
      background: #fff;
      color: var(--ink);
      border-radius: 6px;
      padding: 12px 14px;
      font-size: 16px;
    }}
    .filters {{ display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }}
    button {{
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--ink);
      padding: 10px 12px;
      font: inherit;
      cursor: pointer;
    }}
    button.active {{ border-color: var(--accent); background: var(--accent-soft); color: #063f3b; font-weight: 800; }}
    .section-title {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: end;
      margin: 32px 0 14px;
    }}
    .section-title h2 {{
      margin: 0;
      font-size: 22px;
      letter-spacing: 0;
    }}
    .section-title p {{ margin: 0; color: var(--muted); }}
    .library {{
      overflow: clip;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      box-shadow: var(--shadow);
    }}
    .book-row {{
      display: grid;
      grid-template-columns: 88px minmax(150px, 240px) minmax(260px, 1fr) 92px;
      gap: 14px;
      align-items: center;
      min-height: 72px;
      padding: 14px 16px;
      border-bottom: 1px solid #eee8df;
      text-decoration: none;
    }}
    .book-row:last-child {{ border-bottom: 0; }}
    .book-row:hover {{ background: #f5fbf9; }}
    .row-score, .note-score {{
      display: inline-flex;
      justify-content: center;
      align-items: center;
      min-width: 74px;
      min-height: 34px;
      border-radius: 999px;
      padding: 5px 10px;
      font-weight: 900;
      font-size: 14px;
      white-space: nowrap;
    }}
    .score-legend {{ color: var(--gold); background: #fff2c7; }}
    .score-buy {{ color: var(--blue); background: #e7f0ff; }}
    .score-neutral {{ color: var(--green); background: #e7f6ec; }}
    .score-borrow {{ color: var(--gray); background: #eff0f2; }}
    .score-low {{ color: var(--red); background: #ffe6e3; }}
    .score-none {{ color: #6b5b36; background: #f1ead7; }}
    .row-title {{ font-weight: 850; }}
    .row-line {{ color: #37322d; }}
    .row-date {{ color: var(--muted); font-size: 14px; text-align: right; }}
    .empty {{
      display: none;
      padding: 30px 16px;
      text-align: center;
      color: var(--muted);
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    .notes {{
      display: grid;
      gap: 22px;
      margin-top: 26px;
    }}
    .note {{
      scroll-margin-top: 96px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      padding: clamp(20px, 4vw, 34px);
      box-shadow: var(--shadow);
    }}
    .note-head {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
    }}
    .back-link {{
      color: var(--accent);
      font-weight: 800;
      text-decoration: none;
    }}
    .note h2 {{
      margin: 18px 0 6px;
      font-size: clamp(26px, 4vw, 42px);
      line-height: 1.2;
      letter-spacing: 0;
    }}
    .note-meta {{
      margin: 0 0 18px;
      color: var(--muted);
    }}
    blockquote {{
      margin: 0 0 20px;
      padding: 16px 18px;
      border-left: 4px solid var(--accent);
      background: #edf8f5;
      font-weight: 800;
    }}
    .generated-note {{
      display: inline-block;
      margin: -4px 0 16px;
      color: var(--muted);
      font-size: 13px;
    }}
    .body-text p {{
      margin: 0 0 14px;
      word-break: keep-all;
      overflow-wrap: anywhere;
    }}
    footer {{
      padding: 36px 0;
      border-top: 1px solid var(--line);
      color: var(--muted);
      font-size: 14px;
    }}
    @media (max-width: 820px) {{
      .stats {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .toolbar-inner {{ grid-template-columns: 1fr; }}
      .filters {{ justify-content: flex-start; }}
      .book-row {{
        grid-template-columns: 76px 1fr;
        gap: 8px 12px;
      }}
      .row-line, .row-date {{ grid-column: 2; text-align: left; }}
      .row-title {{ align-self: end; }}
    }}
    @media (max-width: 520px) {{
      .wrap {{ width: min(100% - 20px, 1120px); }}
      .hero {{ padding-top: 50px; }}
      .stats {{ grid-template-columns: 1fr; }}
      .book-row {{ padding: 12px; }}
      .row-line {{ font-size: 15px; }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="wrap hero">
      <div>
        <p class="kicker">BOOK NOTE ARCHIVE</p>
        <h1>독서록 아카이브</h1>
      </div>
      <p class="intro">블로그 독서 노트를 한 페이지로 정리했습니다. 위 목록에서 한줄평과 점수를 훑고, 마음에 드는 책을 누르면 해당 독서 기록으로 바로 이동합니다.</p>
      <div class="stats" aria-label="독서록 통계">
        <div class="stat"><strong>{len(entries)}</strong><span>정리한 글</span></div>
        <div class="stat"><strong>{average:.1f}</strong><span>평균 소장점수</span></div>
        <div class="stat"><strong>{high_count}</strong><span>9점 이상</span></div>
        <div class="stat"><strong>{first_date} - {last_date}</strong><span>기록 기간</span></div>
      </div>
    </div>
  </header>

  <div class="toolbar">
    <div class="wrap toolbar-inner">
      <input class="search" id="search" type="search" placeholder="책 제목이나 한줄평으로 찾기" autocomplete="off">
      <div class="filters" aria-label="점수 필터">
        <button class="active" data-filter="all">전체</button>
        <button data-filter="legend">9-10</button>
        <button data-filter="buy">7-8</button>
        <button data-filter="neutral">5-6</button>
        <button data-filter="borrow">3-4</button>
        <button data-filter="low">1-2</button>
      </div>
    </div>
  </div>

  <main class="wrap">
    <section id="library" aria-labelledby="library-title">
      <div class="section-title">
        <h2 id="library-title">한눈에 보는 책 목록</h2>
        <p><span id="visible-count">{len(entries)}</span>권 표시 중</p>
      </div>
      <div class="library" id="book-list">
        {render_overview(entries)}
      </div>
      <div class="empty" id="empty">조건에 맞는 책이 없습니다.</div>
    </section>

    <section class="notes" aria-label="독서 노트 본문">
      {render_details(entries)}
    </section>
  </main>

  <footer>
    <div class="wrap">원본: {html.escape(source_name)} · 생성: {generated_at}</div>
  </footer>

  <script type="application/json" id="archive-data">{data_json}</script>
  <script>
    const rows = [...document.querySelectorAll(".book-row")];
    const search = document.querySelector("#search");
    const buttons = [...document.querySelectorAll("[data-filter]")];
    const count = document.querySelector("#visible-count");
    const empty = document.querySelector("#empty");
    let currentFilter = "all";

    function inFilter(rating, filter) {{
      if (filter === "all") return true;
      if (!rating && filter !== "all") return false;
      const value = Number(rating);
      if (filter === "legend") return value >= 9;
      if (filter === "buy") return value >= 7 && value < 9;
      if (filter === "neutral") return value >= 5 && value < 7;
      if (filter === "borrow") return value >= 3 && value < 5;
      if (filter === "low") return value > 0 && value < 3;
      return true;
    }}

    function applyFilters() {{
      const query = search.value.trim().toLowerCase();
      let visible = 0;
      rows.forEach((row) => {{
        const matchesText = row.dataset.search.includes(query);
        const matchesFilter = inFilter(row.dataset.rating, currentFilter);
        const show = matchesText && matchesFilter;
        row.hidden = !show;
        if (show) visible += 1;
      }});
      count.textContent = visible;
      empty.style.display = visible ? "none" : "block";
    }}

    search.addEventListener("input", applyFilters);
    buttons.forEach((button) => {{
      button.addEventListener("click", () => {{
        buttons.forEach((item) => item.classList.remove("active"));
        button.classList.add("active");
        currentFilter = button.dataset.filter;
        applyFilters();
      }});
    }});
  </script>
</body>
</html>
"""


def write_readme(entries: list[dict[str, object]], source_name: str) -> str:
    return f"""# 독서록 아카이브

이 폴더는 `{source_name}`에서 추출한 독서 노트를 깃허브 Pages에 올리기 쉽게 정리한 정적 웹페이지입니다.

- `index.html`: 바로 배포할 수 있는 한 페이지 웹사이트
- `data/reading_notes.json`: 추출한 책 제목, 점수, 한줄평, 본문 데이터
- `build_reading_archive.py`: 원본 PDF에서 웹페이지를 다시 만드는 스크립트

현재 정리된 글 수: {len(entries)}

## 다시 만들기

```bash
/Users/min/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 build_reading_archive.py "/Users/min/Downloads/독서 노트.pdf"
```

깃허브에 올릴 때는 이 폴더 전체를 저장소에 넣고 Pages에서 루트 또는 `/docs` 대신 이 폴더를 기준으로 배포하면 됩니다.
"""


def main() -> None:
    text = extract_pdf_text(PDF_PATH)
    entries = parse_posts(text)
    data_dir = ROOT / "data"
    data_dir.mkdir(exist_ok=True)
    (data_dir / "reading_notes.json").write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / "index.html").write_text(render_html(entries, PDF_PATH.name), encoding="utf-8")
    (ROOT / "README.md").write_text(write_readme(entries, PDF_PATH.name), encoding="utf-8")

    missing_ratings = sum(1 for entry in entries if not entry["rating"])
    generated_one_liners = sum(1 for entry in entries if entry["oneLinerGenerated"])
    print(f"created {len(entries)} entries")
    print(f"missing ratings: {missing_ratings}")
    print(f"generated one-liners: {generated_one_liners}")
    print(ROOT / "index.html")


if __name__ == "__main__":
    main()
