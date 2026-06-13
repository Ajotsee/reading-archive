from __future__ import annotations

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from PIL import Image, ImageStat


ROOT = Path(__file__).resolve().parent
PUBLIC_BASE = "https://ajotsee.github.io/reading-archive/"


class ImageTagParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "img":
            self.tags.append({key: value or "" for key, value in attrs})


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def parse_img_tags(path: Path) -> list[dict[str, str]]:
    parser = ImageTagParser()
    parser.feed(read_text(path))
    return parser.tags


def resolve_src(html_path: Path, src: str) -> Path:
    if src.startswith("../"):
        return (html_path.parent / src).resolve()
    return (ROOT / src).resolve()


def is_probably_blank(path: Path) -> bool:
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        stat = ImageStat.Stat(rgb)
        extrema = stat.extrema
    channel_ranges = [high - low for low, high in extrema]
    return max(channel_ranges) <= 3


def image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size


def public_status(url: str) -> tuple[str, int | None, str]:
    request = Request(url, method="HEAD", headers={"Cache-Control": "no-cache", "User-Agent": "reading-archive-validator"})
    try:
        with urlopen(request, timeout=20) as response:
            return url, response.status, ""
    except HTTPError as error:
        if error.code == 405:
            get_request = Request(url, headers={"Cache-Control": "no-cache", "User-Agent": "reading-archive-validator"})
            try:
                with urlopen(get_request, timeout=20) as response:
                    return url, response.status, ""
            except Exception as get_error:  # noqa: BLE001
                return url, None, str(get_error)
        return url, error.code, str(error)
    except (URLError, TimeoutError) as error:
        return url, None, str(error)


def public_url(src: str) -> str:
    return PUBLIC_BASE + src.lstrip("/")


def validate(public: bool = False) -> int:
    errors: list[str] = []
    warnings: list[str] = []

    data = json.loads((ROOT / "data" / "reading_notes.json").read_text(encoding="utf-8"))
    slugs = [str(entry["slug"]) for entry in data]
    note_pages = sorted((ROOT / "notes").glob("note-*/index.html"))
    note_slugs = [path.parent.name for path in note_pages]

    if len(data) != 82:
        errors.append(f"expected 82 entries, found {len(data)}")
    if note_slugs != sorted(slugs):
        errors.append("note page slugs do not match data slugs")

    html_pages = [ROOT / "index.html", *note_pages]
    referenced_images: set[Path] = set()
    public_urls = {PUBLIC_BASE, *(PUBLIC_BASE + f"notes/{slug}/" for slug in slugs)}

    for html_path in html_pages:
        for tag in parse_img_tags(html_path):
            src = tag.get("src", "")
            if not src:
                errors.append(f"{html_path.relative_to(ROOT)} has an img without src")
                continue
            target = resolve_src(html_path, src)
            referenced_images.add(target)
            if not target.exists():
                errors.append(f"{html_path.relative_to(ROOT)} references missing image: {src}")
                continue
            try:
                width, height = image_size(target)
            except Exception as error:  # noqa: BLE001
                errors.append(f"{target.relative_to(ROOT)} is not a readable image: {error}")
                continue
            if width <= 0 or height <= 0:
                errors.append(f"{target.relative_to(ROOT)} has invalid size {width}x{height}")
            public_urls.add(public_url(str(target.relative_to(ROOT))))

    asset_images = set((ROOT / "assets" / "images").glob("note-*/*"))
    if asset_images != referenced_images:
        missing_refs = sorted(asset_images - referenced_images)
        extra_refs = sorted(referenced_images - asset_images)
        for path in missing_refs[:10]:
            warnings.append(f"asset image is not referenced by HTML: {path.relative_to(ROOT)}")
        for path in extra_refs[:10]:
            errors.append(f"HTML references non-asset image: {path.relative_to(ROOT)}")

    json_images = []
    for entry in data:
        for image in entry.get("images") or []:
            json_images.append((entry["slug"], image))
            target = ROOT / str(image["src"])
            if not target.exists():
                errors.append(f"JSON references missing image: {image['src']}")
                continue
            width, height = image_size(target)
            if image.get("width") != width or image.get("height") != height:
                errors.append(f"JSON size mismatch for {image['src']}: json={image.get('width')}x{image.get('height')} file={width}x{height}")
            try:
                if is_probably_blank(target):
                    warnings.append(f"image has almost no pixel variation: {target.relative_to(ROOT)}")
            except Exception as error:  # noqa: BLE001
                errors.append(f"could not inspect pixels for {target.relative_to(ROOT)}: {error}")

    if len(json_images) != 231:
        errors.append(f"expected 231 JSON images, found {len(json_images)}")
    if len(asset_images) != 231:
        errors.append(f"expected 231 asset images, found {len(asset_images)}")

    inline_figures = 0
    for html_path in note_pages:
        text = read_text(html_path)
        for block in re.findall(r'<figure class="inline-figure">.*?</figure>', text, flags=re.S):
            inline_figures += 1
            img_match = re.search(r"<img\s+([^>]+)>", block)
            if not img_match:
                errors.append(f"{html_path.relative_to(ROOT)} has an inline figure without img")
                continue
            attrs = dict(re.findall(r'([a-zA-Z:-]+)="([^"]*)"', img_match.group(1)))
            src = attrs.get("src", "")
            if "loading" in attrs:
                errors.append(f"{html_path.relative_to(ROOT)} keeps lazy loading on inline image: {src}")
            target = resolve_src(html_path, src)
            if not target.exists():
                errors.append(f"{html_path.relative_to(ROOT)} inline image is missing: {src}")
                continue
            width, height = image_size(target)
            if attrs.get("width") != str(width) or attrs.get("height") != str(height):
                errors.append(f"{html_path.relative_to(ROOT)} inline size mismatch for {src}: html={attrs.get('width')}x{attrs.get('height')} file={width}x{height}")

    if inline_figures != 231:
        errors.append(f"expected 231 inline figures, found {inline_figures}")

    if public:
        with ThreadPoolExecutor(max_workers=16) as executor:
            futures = [executor.submit(public_status, url) for url in sorted(public_urls)]
            for future in as_completed(futures):
                url, status, message = future.result()
                if status != 200:
                    errors.append(f"public URL failed ({status}): {url} {message}".strip())

    print("Reading archive validation")
    print(f"- entries: {len(data)}")
    print(f"- note pages: {len(note_pages)}")
    print(f"- inline figures: {inline_figures}")
    print(f"- image files: {len(asset_images)}")
    print(f"- referenced images: {len(referenced_images)}")
    if public:
        print(f"- public URLs checked: {len(public_urls)}")
    print(f"- warnings: {len(warnings)}")
    print(f"- errors: {len(errors)}")

    for warning in warnings[:20]:
        print(f"WARNING: {warning}")
    for error in errors[:50]:
        print(f"ERROR: {error}")

    return 1 if errors else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the generated reading archive.")
    parser.add_argument("--public", action="store_true", help="also check GitHub Pages URLs")
    args = parser.parse_args()
    raise SystemExit(validate(public=args.public))


if __name__ == "__main__":
    main()
