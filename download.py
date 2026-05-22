#!/usr/bin/env python3
"""Download a Zhihu collection (收藏夹) as Markdown files with local images.

Usage:
    python3 download.py                    # uses default collection 646316355
    python3 download.py -c <collection_id>
    python3 download.py --limit 5          # only first 5 items, for testing

Cookie:
    Put the full `Cookie:` header value (copied from a logged-in zhihu.com
    tab via DevTools -> Network -> Request Headers) into ./cookie.txt.
"""

import argparse
import hashlib
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from markdownify import markdownify

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def sanitize_filename(s: str, maxlen: int = 80) -> str:
    s = re.sub(r'[\\/:*?"<>|\n\r\t]', "_", s)
    s = s.strip().strip(".")
    if len(s) > maxlen:
        s = s[:maxlen]
    return s or "untitled"


def fetch_collection(coll_id: str, cookie: str, sleep: float = 1.0):
    """Yield each item from the collection, paging through the API."""
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": UA,
            "Cookie": cookie,
            "Referer": f"https://www.zhihu.com/collection/{coll_id}",
            "Accept": "application/json, text/plain, */*",
        }
    )
    offset, limit = 0, 20
    while True:
        url = f"https://www.zhihu.com/api/v4/collections/{coll_id}/items"
        r = session.get(url, params={"offset": offset, "limit": limit}, timeout=30)
        if r.status_code == 403:
            print("ERROR 403: cookie invalid or you are not logged in.", file=sys.stderr)
            sys.exit(3)
        r.raise_for_status()
        data = r.json()
        items = data.get("data", [])
        if not items:
            break
        for it in items:
            yield it
        if data.get("paging", {}).get("is_end"):
            break
        offset += limit
        time.sleep(sleep)


def download_image(session: requests.Session, url: str, image_dir: Path) -> str | None:
    try:
        if url.startswith("//"):
            url = "https:" + url
        ext = Path(urlparse(url).path).suffix.lower() or ".jpg"
        if len(ext) > 5 or ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"):
            ext = ".jpg"
        name = hashlib.md5(url.encode()).hexdigest()[:16] + ext
        target = image_dir / name
        if not target.exists():
            r = session.get(url, timeout=30)
            r.raise_for_status()
            target.write_bytes(r.content)
            time.sleep(0.15)
        return name
    except Exception as e:
        print(f"  ! image failed: {url[:80]} - {e}", file=sys.stderr)
        return None


def process_html(html_content: str, image_dir: Path, session: requests.Session) -> str:
    """Replace <img> tags with locally-downloaded images using lazy-load attrs."""

    def replace_img(m: re.Match) -> str:
        tag = m.group(0)
        for attr in ("data-original", "data-actualsrc", "src"):
            mm = re.search(rf'{attr}="([^"]+)"', tag)
            if mm:
                src = mm.group(1)
                if src.startswith(("http", "//")):
                    local = download_image(session, src, image_dir)
                    if local:
                        return f'<img src="../images/{local}" alt="">'
        return tag

    return re.sub(r"<img\b[^>]*>", replace_img, html_content)


def html_to_md(content: str) -> str:
    md = markdownify(
        content, heading_style="ATX", bullets="-", strip=["script", "style"]
    )
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip()


def write_item(item: dict, out_dir: Path, image_dir: Path, session: requests.Session):
    typ = item.get("type") or item.get("content", {}).get("type")
    content = item.get("content") or item

    if typ == "answer":
        title = (content.get("question") or {}).get("title", "untitled")
        author = (content.get("author") or {}).get("name", "")
        body_html = content.get("content", "")
        qid = (content.get("question") or {}).get("id", "")
        url = f"https://www.zhihu.com/question/{qid}/answer/{content.get('id','')}"
        item_id = content.get("id")
        prefix = "answer"
    elif typ == "article":
        title = content.get("title", "untitled")
        author = (content.get("author") or {}).get("name", "")
        body_html = content.get("content", "")
        url = f"https://zhuanlan.zhihu.com/p/{content.get('id','')}"
        item_id = content.get("id")
        prefix = "article"
    elif typ == "zvideo":
        title = content.get("title", "untitled")
        author = (content.get("author") or {}).get("name", "")
        body_html = content.get("description", "") or ""
        url = f"https://www.zhihu.com/zvideo/{content.get('id','')}"
        item_id = content.get("id")
        prefix = "zvideo"
    else:
        print(f"  ? unknown item type: {typ}, skipped")
        return None

    body_html = process_html(body_html, image_dir, session)
    body_md = html_to_md(body_html)

    name = f"{prefix}_{item_id}_{sanitize_filename(title)}.md"
    target = out_dir / name

    front = [
        "---",
        f'title: "{title.replace(chr(34), chr(39))}"',
        f'author: "{author}"',
        f"type: {typ}",
        f"url: {url}",
        f"zhihu_id: {item_id}",
        "---",
    ]
    target.write_text(
        "\n".join(front) + "\n\n" + f"# {title}\n\n" + body_md + "\n",
        encoding="utf-8",
    )
    return name


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-c", "--collection", default="646316355", help="collection id")
    ap.add_argument("--cookie-file", default=str(Path(__file__).parent / "cookie.txt"))
    ap.add_argument("--out", default=None, help="output dir (default: ./output/<id>)")
    ap.add_argument("--limit", type=int, default=0, help="max items, 0 = all")
    args = ap.parse_args()

    cookie_path = Path(args.cookie_file)
    if not cookie_path.exists():
        print(f"ERROR: cookie file not found: {cookie_path}", file=sys.stderr)
        print(
            "Create it and paste the full Cookie header from a logged-in zhihu.com tab.",
            file=sys.stderr,
        )
        sys.exit(2)
    cookie = cookie_path.read_text(encoding="utf-8").strip()
    if not cookie:
        print("ERROR: cookie.txt is empty.", file=sys.stderr)
        sys.exit(2)

    base = (
        Path(args.out)
        if args.out
        else Path(__file__).parent / "output" / args.collection
    )
    art_dir = base / "articles"
    img_dir = base / "images"
    art_dir.mkdir(parents=True, exist_ok=True)
    img_dir.mkdir(parents=True, exist_ok=True)

    img_session = requests.Session()
    img_session.headers.update(
        {"User-Agent": UA, "Referer": "https://www.zhihu.com/"}
    )

    count = 0
    ok = 0
    for item in fetch_collection(args.collection, cookie):
        count += 1
        typ = item.get("type", "?")
        c = item.get("content") or {}
        preview = c.get("title") or (c.get("question") or {}).get("title") or "?"
        print(f"[{count}] {typ}: {preview[:60]}")
        try:
            name = write_item(item, art_dir, img_dir, img_session)
            if name:
                ok += 1
                print(f"   -> {name}")
        except Exception as e:
            print(f"   ! ERROR: {e}", file=sys.stderr)
        if args.limit and count >= args.limit:
            break

    print(f"\nDone. {ok}/{count} items written to {base}")


if __name__ == "__main__":
    main()
