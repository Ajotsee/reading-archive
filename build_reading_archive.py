from __future__ import annotations

import bisect
import html
import io
import json
import re
import shutil
import subprocess
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

from PIL import Image
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parent
PDF_PATH = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else Path("/Users/min/Downloads/독서 노트.pdf")
POST_START_RE = re.compile(r"(?m)^\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}\s+https?://\S+")


STYLE_CSS = """
:root {
  color-scheme: light;
  --ink: #151515;
  --muted: #6a645e;
  --line: #ddd6cc;
  --paper: #fbfaf7;
  --panel: #ffffff;
  --accent: #0f766e;
  --accent-soft: #d8f1ec;
  --gold: #8a5a00;
  --blue: #245c9e;
  --green: #256f47;
  --gray: #5d6268;
  --red: #9f2f2f;
  --shadow: 0 18px 44px rgba(31, 26, 18, .08);
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Noto Sans KR", "Segoe UI", sans-serif;
  background: var(--paper);
  color: var(--ink);
  line-height: 1.68;
}
a { color: inherit; }
img { max-width: 100%; height: auto; display: block; }
.wrap { width: min(1120px, calc(100% - 32px)); margin: 0 auto; }
.site-header {
  border-bottom: 1px solid var(--line);
  background: linear-gradient(180deg, #fff 0%, #fbfaf7 100%);
}
.hero {
  display: grid;
  align-content: center;
  gap: 24px;
  min-height: 42vh;
  padding: 64px 0 42px;
}
.kicker {
  margin: 0 0 4px;
  color: var(--accent);
  font-size: 14px;
  font-weight: 850;
  letter-spacing: 0;
}
h1 {
  margin: 0;
  max-width: 820px;
  font-family: ui-serif, "New York", "Apple SD Gothic Neo", "Noto Serif KR", serif;
  font-size: clamp(38px, 6.5vw, 72px);
  line-height: 1.08;
  letter-spacing: 0;
}
.intro {
  margin: 0;
  max-width: 780px;
  color: #3f3a35;
  font-size: 18px;
}
.stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  max-width: 900px;
}
.stat {
  border-left: 3px solid var(--accent);
  padding: 10px 14px;
  background: #fff;
  box-shadow: var(--shadow);
}
.stat strong { display: block; font-size: 24px; line-height: 1.15; }
.stat span { color: var(--muted); font-size: 13px; }
.toolbar {
  position: sticky;
  top: 0;
  z-index: 10;
  padding: 14px 0;
  background: color-mix(in srgb, var(--paper) 92%, transparent);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--line);
}
.toolbar-inner {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 12px;
  align-items: center;
}
.search {
  width: 100%;
  border: 1px solid var(--line);
  background: #fff;
  color: var(--ink);
  border-radius: 6px;
  padding: 12px 14px;
  font-size: 16px;
}
.filters { display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
button {
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #fff;
  color: var(--ink);
  padding: 10px 12px;
  font: inherit;
  cursor: pointer;
}
button.active { border-color: var(--accent); background: var(--accent-soft); color: #063f3b; font-weight: 850; }
main { padding: 34px 0 80px; }
.section-title {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: end;
  margin: 28px 0 14px;
}
.section-title h2 {
  margin: 0;
  font-size: 22px;
  letter-spacing: 0;
}
.section-title p { margin: 0; color: var(--muted); }
.library {
  overflow: clip;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
  box-shadow: var(--shadow);
}
.book-row {
  display: grid;
  grid-template-columns: 66px 82px minmax(150px, 250px) minmax(230px, 1fr) 92px;
  gap: 14px;
  align-items: center;
  min-height: 86px;
  padding: 12px 16px;
  border-bottom: 1px solid #eee8df;
  text-decoration: none;
}
.book-row:last-child { border-bottom: 0; }
.book-row:hover { background: #f5fbf9; }
.thumb {
  width: 54px;
  height: 64px;
  border: 1px solid #e7dfd5;
  border-radius: 6px;
  overflow: hidden;
  background: #f2eee7;
}
.thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.thumb-empty {
  width: 100%;
  height: 100%;
  display: grid;
  place-items: center;
  color: var(--muted);
  font-size: 12px;
  font-weight: 850;
}
.row-score, .note-score {
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
}
.score-legend { color: var(--gold); background: #fff2c7; }
.score-buy { color: var(--blue); background: #e7f0ff; }
.score-neutral { color: var(--green); background: #e7f6ec; }
.score-borrow { color: var(--gray); background: #eff0f2; }
.score-low { color: var(--red); background: #ffe6e3; }
.score-none { color: #6b5b36; background: #f1ead7; }
.row-title { font-weight: 850; }
.row-line { color: #37322d; }
.row-date { color: var(--muted); font-size: 14px; text-align: right; }
.empty {
  display: none;
  padding: 30px 16px;
  text-align: center;
  color: var(--muted);
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 8px;
}
.note-shell {
  width: min(860px, calc(100% - 32px));
  margin: 0 auto;
}
.note-nav {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  padding: 22px 0 0;
}
.back-link {
  color: var(--accent);
  font-weight: 850;
  text-decoration: none;
}
.note-header {
  padding: 44px 0 24px;
  border-bottom: 1px solid var(--line);
}
.note-header h1 {
  font-size: clamp(34px, 6vw, 60px);
}
.note-meta {
  margin: 14px 0 0;
  color: var(--muted);
}
.note-summary {
  margin-top: 24px;
  padding: 18px 20px;
  border-left: 4px solid var(--accent);
  background: #edf8f5;
  font-weight: 850;
}
.generated-note {
  display: inline-block;
  margin-top: 10px;
  color: var(--muted);
  font-size: 13px;
}
.inline-figure {
  margin: 26px 0;
  border: 1px solid var(--line);
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
  box-shadow: var(--shadow);
}
.inline-figure img {
  width: 100%;
  max-height: 720px;
  object-fit: contain;
  background: #f3f0ea;
}
.inline-figure figcaption {
  padding: 8px 10px;
  color: var(--muted);
  font-size: 13px;
}
.body-text {
  padding: 12px 0 70px;
}
.body-text p {
  margin: 0 0 15px;
  word-break: keep-all;
  overflow-wrap: anywhere;
}
.site-footer {
  padding: 34px 0;
  border-top: 1px solid var(--line);
  color: var(--muted);
  font-size: 14px;
}
@media (max-width: 860px) {
  .stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .toolbar-inner { grid-template-columns: 1fr; }
  .filters { justify-content: flex-start; }
  .book-row {
    grid-template-columns: 54px 76px 1fr;
    gap: 8px 12px;
  }
  .row-line, .row-date { grid-column: 3; text-align: left; }
  .row-title { align-self: end; }
  .thumb { width: 48px; height: 58px; }
}
@media (max-width: 560px) {
  .wrap, .note-shell { width: min(100% - 20px, 1120px); }
  .hero { padding-top: 48px; }
  .stats { grid-template-columns: 1fr; }
  .book-row {
    grid-template-columns: 46px 1fr;
    padding: 12px;
  }
  .row-score { grid-column: 1; grid-row: 2; min-width: 46px; font-size: 12px; }
  .row-title, .row-line, .row-date { grid-column: 2; }
  .row-line { font-size: 15px; }
}
"""


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
    return f"note-{index:02d}"


def safe_filename(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value)
    name = re.sub(r"[^0-9A-Za-z가-힣._-]+", "-", normalized)
    return re.sub(r"-{2,}", "-", name).strip("-._") or "image"


def read_pdf(path: Path) -> tuple[PdfReader, list[str], str, list[int]]:
    reader = PdfReader(str(path))
    page_texts: list[str] = []
    page_offsets: list[int] = []
    chunks: list[str] = []
    cursor = 0
    for page in reader.pages:
        page_offsets.append(cursor)
        text = page.extract_text() or ""
        page_texts.append(text)
        chunk = text + "\n"
        chunks.append(chunk)
        cursor += len(chunk)
    return reader, page_texts, "".join(chunks), page_offsets


def char_to_page(position: int, page_offsets: list[int]) -> int:
    return max(1, bisect.bisect_right(page_offsets, position))


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


def clean_body_line(line: str, skip_scale: bool, seen_recent: list[str]) -> tuple[str | None, bool]:
    line = dedupe_export_echo(line)
    if not line:
        return None, skip_scale
    if re.match(r"^\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}", line):
        return None, skip_scale
    if re.match(r"^https?://blog\.naver\.com/ajotsee/\d+", line):
        return None, skip_scale
    if line in {"독서", "독서독서"}:
        return None, skip_scale
    if re.search(r"소장점수\s*[0-9]+(?:\.[0-9]+)?/10", line):
        return None, skip_scale
    if "한줄평" in line:
        return None, skip_scale
    if "소장가치 스케일러" in line:
        return None, True
    if re.match(r"^(1점|3~4점|5~6점|7~8점|9~10\s*점?)", line):
        return None, skip_scale
    if line in {"·", "아조씨의 개소리"} or re.match(r"^\d{1,3}$", line):
        return None, skip_scale
    if skip_scale and (
        re.match(r"^(1점|3~4점|5~6점|7~8점|9~10)", line)
        or "쓰레기" in line
        or "빌려" in line
        or "후손에게" in line
    ):
        return None, True
    skip_scale = False
    if re.match(r"^\d+\s*·\s*아조씨의 개소리$", line):
        return None, skip_scale
    if line in {"blog.naver.com", "m.blog.naver.com", "x.com"}:
        return None, skip_scale
    if seen_recent and line == seen_recent[-1]:
        return None, skip_scale
    seen_recent.append(line)
    if len(seen_recent) > 6:
        seen_recent.pop(0)
    return line, skip_scale


def cleaned_body_lines(block: str) -> list[str]:
    lines = [dedupe_export_echo(line) for line in block.splitlines()]
    cleaned: list[str] = []
    skip_scale = False
    seen_recent: list[str] = []

    for line in lines:
        cleaned_line, skip_scale = clean_body_line(line, skip_scale, seen_recent)
        if cleaned_line:
            cleaned.append(cleaned_line)
    return cleaned


def parse_posts(text: str, page_offsets: list[int]) -> list[dict[str, object]]:
    starts = list(POST_START_RE.finditer(text))
    entries: list[dict[str, object]] = []

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
        start_page = char_to_page(start.start(), page_offsets)
        end_page = char_to_page(max(start.start(), end - 1), page_offsets)

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
                "startPage": start_page,
                "endPage": end_page,
                "images": [],
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


def reset_generated_dirs() -> None:
    for path in [ROOT / "notes", ROOT / "assets" / "images"]:
        if path.exists():
            subprocess.run(["/bin/rm", "-rf", str(path)], check=True)
        if path.exists():
            shutil.rmtree(path)
    (ROOT / "notes").mkdir(parents=True, exist_ok=True)
    (ROOT / "assets" / "images").mkdir(parents=True, exist_ok=True)


def extract_images(reader: PdfReader, entries: list[dict[str, object]]) -> int:
    total = 0
    for entry in entries:
        slug = str(entry["slug"])
        image_dir = ROOT / "assets" / "images" / slug
        image_dir.mkdir(parents=True, exist_ok=True)
        images = []
        image_index = 1
        for page_number in range(int(entry["startPage"]), int(entry["endPage"]) + 1):
            page = reader.pages[page_number - 1]
            for page_image_index, image in enumerate(getattr(page, "images", []), start=1):
                original_name = safe_filename(getattr(image, "name", "") or f"image-{page_image_index}.bin")
                suffix = Path(original_name).suffix.lower() or ".bin"
                filename = f"p{page_number:03d}-{image_index:02d}{suffix}"
                target = image_dir / filename
                target.write_bytes(image.data)
                width = None
                height = None
                try:
                    with Image.open(io.BytesIO(image.data)) as opened_image:
                        width, height = opened_image.size
                except Exception:
                    pass
                root_src = f"assets/images/{slug}/{filename}"
                images.append(
                    {
                        "src": root_src,
                        "filename": filename,
                        "page": page_number,
                        "xobject": f"/{Path(original_name).stem}",
                        "width": width,
                        "height": height,
                    }
                )
                image_index += 1
                total += 1
        entry["images"] = images
    return total


def page_layout_items(reader: PdfReader, page_number: int, image_lookup: dict[tuple[int, str], dict[str, object]]) -> list[dict[str, object]]:
    page = reader.pages[page_number - 1]
    items: list[dict[str, object]] = []

    def before_operand(operator, operands, cm, tm):
        if operator != b"Do" or not operands:
            return
        key = str(operands[0])
        image = image_lookup.get((page_number, key))
        if image:
            items.append({"type": "image", "image": image})

    def visit_text(text, cm, tm, font_dict, font_size):
        line = dedupe_export_echo(text)
        if line:
            items.append({"type": "text", "text": line})

    page.extract_text(visitor_operand_before=before_operand, visitor_text=visit_text)
    return items


def is_url_or_domain_line(text: str) -> bool:
    return bool(re.match(r"^(https?://|[A-Za-z0-9.-]+\.[A-Za-z]{2,})(/\S*)?$", text.strip()))


def is_outline_line(text: str) -> bool:
    text = text.strip()
    return bool(
        re.match(r"^(목차|추천사|서문|프롤로그|에필로그|결론)$", text)
        or re.match(r"^제\s*\d+\s*장\b", text)
        or re.match(r"^\d+(?:\.\d+)+\s+\S+", text)
        or re.match(r"^\d+\s*[.)]\s+\S+", text)
    )


def is_sentence_end(text: str) -> bool:
    text = text.strip().rstrip("\"'”’)]}〉》」』")
    if not text:
        return False
    if is_url_or_domain_line(text) or is_outline_line(text):
        return True
    return bool(re.search(r"([.!?…。]|요|죠|군요|네요|니다|습니다|했습니다|됩니다|입니다|있습니다|없습니다|싶습니다|같습니다|봅니다|합니다|였습니다|였죠|겠죠|ㅠ+|ㅜ+|ㅋ+|ㅎ+)$", text))


def hangul_tail_token_length(text: str) -> int:
    match = re.search(r"([가-힣]+)$", text)
    return len(match.group(1)) if match else 0


def needs_join_without_space(left: str, right: str) -> bool:
    left = left.rstrip()
    right = right.lstrip()
    if not left or not right:
        return True
    if re.match(r"^[,.;:!?…)\]}〉》」』]", right):
        return True
    if re.search(r"[(\[{'\"“‘〈《「『]$", left):
        return True
    if re.search(r"[가-힣]$", left) and re.match(r"^[가-힣]", right):
        if hangul_tail_token_length(left) <= 1:
            return True
        if re.match(r"^(에서|에게|으로|부터|까지|처럼|보다|이나|라도|마저|조차|들이|면서|지만|다가|는데|라서|라고|하고|해야|하는|했던|했다|한|할)", right):
            return True
        if re.match(r"^(은|는|이|가|을|를|의|에|께|와|과|도|만|로|랑|나|들|면|며|고|게)(?:\s|$)", right):
            return True
    return False


def join_wrapped_text(left: str, right: str) -> str:
    left = left.rstrip()
    right = right.lstrip()
    if needs_join_without_space(left, right):
        return left + right
    return left + " " + right


def polish_extracted_text(text: str) -> str:
    replacements = {
        "읽으니참": "읽으니 참",
        "코어개발자": "코어 개발자",
        "돈'비트코인": "돈' 비트코인",
        "돈&#x27;비트코인": "돈&#x27; 비트코인",
        "라이 벌": "라이벌",
        "받아들여야 함비트코인": "받아들여야 함. 비트코인",
        "바꾸게 됨사람": "바꾸게 됨. 사람",
        "보게 됨몰입": "보게 됨. 몰입",
        "도움이 됨스위치": "도움이 됨. 스위치",
        "힘훌륭한": "힘: 훌륭한",
        "거래 소": "거래소",
        "두입장": "두 입장",
        "영희로과": "영희와",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    text = re.sub(r"([가-힣])\s+(니다|습니다|입니다|합니다|했습니다|됩니다|였습니다|었습니다|았습니다|겠죠|군요|네요)", r"\1\2", text)
    return text


def merge_wrapped_paragraphs(content: list[dict[str, object]]) -> list[dict[str, object]]:
    merged: list[dict[str, object]] = []
    buffer = ""

    def flush() -> None:
        nonlocal buffer
        if buffer:
            merged.append({"type": "paragraph", "text": polish_extracted_text(buffer)})
            buffer = ""

    for item in content:
        if item["type"] == "image":
            flush()
            merged.append(item)
            continue

        line = compact_spaces(str(item["text"]))
        if not line:
            continue
        if re.match(r"^[.!?…。]", line) and not buffer and merged and merged[-1].get("type") == "paragraph":
            merged[-1]["text"] = polish_extracted_text(str(merged[-1]["text"]).rstrip() + line)
            continue
        if is_url_or_domain_line(line) or is_outline_line(line):
            flush()
            merged.append({"type": "paragraph", "text": line})
            continue

        buffer = join_wrapped_text(buffer, line) if buffer else line
        if is_sentence_end(line):
            flush()

    flush()
    return merged


def build_content_items(reader: PdfReader, entries: list[dict[str, object]]) -> None:
    image_lookup: dict[tuple[int, str], dict[str, object]] = {}
    for entry in entries:
        for image in entry.get("images") or []:
            image_lookup[(int(image["page"]), str(image["xobject"]))] = image

    for entry in entries:
        content: list[dict[str, object]] = []
        skip_scale = False
        seen_recent: list[str] = []
        one_liner = str(entry["oneLiner"])
        title = str(entry["title"]).rstrip(" -")

        for page_number in range(int(entry["startPage"]), int(entry["endPage"]) + 1):
            for item in page_layout_items(reader, page_number, image_lookup):
                if item["type"] == "image":
                    image = item["image"]
                    if any(image is known for known in (entry.get("images") or [])):
                        content.append(
                            {
                                "type": "image",
                                "src": image["src"],
                                "page": image["page"],
                                "filename": image["filename"],
                                "width": image.get("width"),
                                "height": image.get("height"),
                            }
                        )
                    continue

                cleaned_line, skip_scale = clean_body_line(str(item["text"]), skip_scale, seen_recent)
                is_title_echo = bool(cleaned_line) and (
                    cleaned_line == title
                    or title.startswith(cleaned_line.rstrip(" -"))
                    and len(cleaned_line.rstrip(" -")) >= 12
                )
                if cleaned_line and cleaned_line != one_liner and not is_title_echo:
                    content.append({"type": "paragraph", "text": cleaned_line})

        entry["content"] = merge_wrapped_paragraphs(content)


def render_thumb(entry: dict[str, object]) -> str:
    images = entry.get("images") or []
    if images:
        first = images[0]
        return f'<span class="thumb"><img src="{html.escape(str(first["src"]))}" alt="{html.escape(str(entry["title"]))} 이미지"></span>'
    return '<span class="thumb"><span class="thumb-empty">NO<br>IMG</span></span>'


def render_overview(entries: list[dict[str, object]]) -> str:
    rows = []
    for entry in entries:
        href = f'notes/{html.escape(str(entry["slug"]))}/'
        rows.append(
            f"""
            <a class="book-row" href="{href}" data-rating="{html.escape(str(entry["ratingNumber"] or ""))}" data-search="{html.escape((str(entry["title"]) + " " + str(entry["oneLiner"])).lower())}">
              {render_thumb(entry)}
              <span class="row-score {score_class(entry["ratingNumber"])}">{html.escape(score_label(str(entry["rating"])))}</span>
              <span class="row-title">{html.escape(str(entry["title"]))}</span>
              <span class="row-line">{html.escape(str(entry["oneLiner"]))}</span>
              <span class="row-date">{html.escape(str(entry["date"]).replace("/", "."))}</span>
            </a>
            """
        )
    return "\n".join(rows)


def render_index(entries: list[dict[str, object]], source_name: str) -> str:
    ratings = [entry["ratingNumber"] for entry in entries if entry["ratingNumber"] is not None]
    average = sum(ratings) / len(ratings) if ratings else 0
    high_count = sum(1 for rating in ratings if rating >= 9)
    image_count = sum(len(entry.get("images") or []) for entry in entries)
    first_date = entries[-1]["date"].replace("/", ".") if entries else ""
    last_date = entries[0]["date"].replace("/", ".") if entries else ""
    generated_at = datetime.now().strftime("%Y.%m.%d %H:%M")

    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>독서록 아카이브</title>
  <link rel="stylesheet" href="assets/site.css">
</head>
<body>
  <header class="site-header">
    <div class="wrap hero">
      <div>
        <p class="kicker">BOOK NOTE ARCHIVE</p>
        <h1>독서록 아카이브</h1>
      </div>
      <p class="intro">모든 독서 기록을 한눈에 볼 수 있는 목록입니다. 책을 누르면 별도 페이지로 이동해 사진과 본문을 함께 볼 수 있습니다.</p>
      <div class="stats" aria-label="독서록 통계">
        <div class="stat"><strong>{len(entries)}</strong><span>정리한 글</span></div>
        <div class="stat"><strong>{average:.1f}</strong><span>평균 소장점수</span></div>
        <div class="stat"><strong>{high_count}</strong><span>9점 이상</span></div>
        <div class="stat"><strong>{image_count}</strong><span>추출한 이미지</span></div>
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
    <section aria-labelledby="library-title">
      <div class="section-title">
        <h2 id="library-title">한눈에 보는 책 목록</h2>
        <p><span id="visible-count">{len(entries)}</span>권 표시 중 · {first_date} - {last_date}</p>
      </div>
      <div class="library" id="book-list">
        {render_overview(entries)}
      </div>
      <div class="empty" id="empty">조건에 맞는 책이 없습니다.</div>
    </section>
  </main>

  <footer class="site-footer">
    <div class="wrap">원본: {html.escape(source_name)} · 생성: {generated_at}</div>
  </footer>
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


def render_content(entry: dict[str, object]) -> str:
    parts = []
    image_index = 1
    for item in entry.get("content") or []:
        if item["type"] == "image":
            src = "../../" + str(item["src"])
            width = f' width="{int(item["width"])}"' if item.get("width") else ""
            height = f' height="{int(item["height"])}"' if item.get("height") else ""
            parts.append(
                f"""
                <figure class="inline-figure">
                  <img src="{html.escape(src)}" alt="{html.escape(str(entry["title"]))} 이미지 {image_index}"{width}{height} decoding="async">
                  <figcaption>PDF {item["page"]}쪽 이미지 {image_index}</figcaption>
                </figure>
                """
            )
            image_index += 1
        else:
            parts.append(f"<p>{html.escape(str(item['text']))}</p>")
    return "\n".join(parts)


def render_note_page(entry: dict[str, object], source_name: str) -> str:
    generated_note = (
        '<span class="generated-note">본문 첫머리에서 만든 임시 한줄평</span>'
        if entry["oneLinerGenerated"]
        else ""
    )
    body = render_content(entry)

    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(str(entry["title"]))} · 독서록 아카이브</title>
  <link rel="stylesheet" href="../../assets/site.css">
</head>
<body>
  <div class="note-shell">
    <nav class="note-nav" aria-label="독서록 이동">
      <a class="back-link" href="../../">목록으로</a>
      <span class="note-score {score_class(entry["ratingNumber"])}">{html.escape(score_label(str(entry["rating"])))}</span>
    </nav>
    <header class="note-header">
      <p class="kicker">BOOK NOTE</p>
      <h1>{html.escape(str(entry["title"]))}</h1>
      <p class="note-meta">{html.escape(str(entry["date"]).replace("/", "."))} · PDF {entry["startPage"]}-{entry["endPage"]}쪽 · <a href="{html.escape(str(entry["url"]))}" target="_blank" rel="noopener">원문 보기</a></p>
      <div class="note-summary">{html.escape(str(entry["oneLiner"]))}</div>
      {generated_note}
    </header>
    <main class="body-text">
      {body}
    </main>
  </div>
  <footer class="site-footer">
    <div class="note-shell">원본: {html.escape(source_name)}</div>
  </footer>
</body>
</html>
"""


def write_note_pages(entries: list[dict[str, object]], source_name: str) -> None:
    for entry in entries:
        note_dir = ROOT / "notes" / str(entry["slug"])
        note_dir.mkdir(parents=True, exist_ok=True)
        (note_dir / "index.html").write_text(render_note_page(entry, source_name), encoding="utf-8")


def write_readme(entries: list[dict[str, object]], image_count: int, source_name: str) -> str:
    return f"""# 독서록 아카이브

이 저장소는 `{source_name}`에서 추출한 독서 노트를 GitHub Pages에 올리기 쉽게 정리한 정적 웹사이트입니다.

- `index.html`: 전체 책 목록
- `notes/`: 책별 독서록 개별 페이지
- `assets/images/`: PDF에서 추출한 책별 이미지
- `data/reading_notes.json`: 추출한 책 제목, 점수, 한줄평, 본문, 이미지 경로 데이터
- `build_reading_archive.py`: 원본 PDF에서 웹사이트를 다시 만드는 스크립트
- `validate_reading_archive.py`: 이미지 경로, 크기, 공개 URL을 검사하는 검증 스크립트

현재 정리된 글 수: {len(entries)}
추출한 이미지 수: {image_count}

## 다시 만들기

```bash
/Users/min/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 build_reading_archive.py "/Users/min/Downloads/독서 노트.pdf"
```

GitHub Pages는 `main` 브랜치의 루트(`/`)를 배포 대상으로 사용합니다.

## 검증하기

```bash
/Users/min/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 validate_reading_archive.py --public
```
"""


def main() -> None:
    reader, _page_texts, text, page_offsets = read_pdf(PDF_PATH)
    entries = parse_posts(text, page_offsets)
    reset_generated_dirs()
    image_count = extract_images(reader, entries)
    build_content_items(reader, entries)

    data_dir = ROOT / "data"
    data_dir.mkdir(exist_ok=True)
    (ROOT / "assets").mkdir(exist_ok=True)
    (ROOT / "assets" / "site.css").write_text(STYLE_CSS.strip() + "\n", encoding="utf-8")
    (data_dir / "reading_notes.json").write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / "index.html").write_text(render_index(entries, PDF_PATH.name), encoding="utf-8")
    write_note_pages(entries, PDF_PATH.name)
    (ROOT / "README.md").write_text(write_readme(entries, image_count, PDF_PATH.name), encoding="utf-8")

    missing_ratings = sum(1 for entry in entries if not entry["rating"])
    generated_one_liners = sum(1 for entry in entries if entry["oneLinerGenerated"])
    print(f"created {len(entries)} entries")
    print(f"extracted images: {image_count}")
    print(f"missing ratings: {missing_ratings}")
    print(f"generated one-liners: {generated_one_liners}")
    print(ROOT / "index.html")


if __name__ == "__main__":
    main()
