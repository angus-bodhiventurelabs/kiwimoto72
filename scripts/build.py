from __future__ import annotations

from pathlib import Path
import shutil

import markdown

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
CONTENT_DIR = ROOT / "content" / "posts"
TEMPLATE_PATH = ROOT / "templates" / "post.html"
DIST_DIR = ROOT / "dist"
BLOG_DIR = DIST_DIR / "blog"
ROOT_INDEX_PATH = ROOT / "index.html"


def ensure_dist() -> None:
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    BLOG_DIR.mkdir(parents=True, exist_ok=True)


def copy_static_files() -> None:
    for item in SRC_DIR.iterdir():
        if item.is_file():
            shutil.copy2(item, DIST_DIR / item.name)

    if ROOT_INDEX_PATH.exists():
        shutil.copy2(ROOT_INDEX_PATH, DIST_DIR / "index.html")


def parse_title(md_text: str, fallback: str) -> str:
    for line in md_text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def build_posts() -> list[tuple[str, str]]:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    posts: list[tuple[str, str]] = []

    for post_path in sorted(CONTENT_DIR.glob("*.md"), reverse=True):
        raw = post_path.read_text(encoding="utf-8")
        html_body = markdown.markdown(raw, extensions=["extra"])
        slug = post_path.stem
        title = parse_title(raw, slug)
        post_html = template.replace("{{ title }}", title).replace("{{ content }}", html_body)

        output_path = BLOG_DIR / f"{slug}.html"
        output_path.write_text(post_html, encoding="utf-8")
        posts.append((title, f"/blog/{slug}.html"))

    return posts


def build_blog_index(posts: list[tuple[str, str]]) -> None:
    items = "\n".join([f'<li><a href="{url}">{title}</a></li>' for title, url in posts])
    page = f"""<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"UTF-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
    <title>Blog | Kiwimoto77</title>
    <link rel=\"stylesheet\" href=\"/styles.css\" />
  </head>
  <body>
    <main>
      <p><a href=\"/\">← Home</a></p>
      <h1>Blog</h1>
      <ul>
        {items if items else '<li>No posts yet.</li>'}
      </ul>
    </main>
  </body>
</html>
"""
    (BLOG_DIR / "index.html").write_text(page, encoding="utf-8")


def main() -> None:
    ensure_dist()
    copy_static_files()
    posts = build_posts()
    build_blog_index(posts)
    print(f"Built site to {DIST_DIR}")
    print(f"Posts generated: {len(posts)}")


if __name__ == "__main__":
    main()
