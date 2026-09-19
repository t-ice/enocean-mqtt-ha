#!/usr/bin/env python3
"""Assemble the MkDocs input tree from the wiki sources and the reference docs.

`wiki/*.md` stays the single source for the user guides — those files are pushed verbatim into the
GitHub wiki repo (see `wiki/README.md`) — so the published site is *generated* from them instead of
being a second copy that drifts. Generating means translating three GitHub-wiki conventions into
plain Markdown:

* **Wiki links.** GitHub writes them alias-first, `[[Text|Page]]`. The order matters: the usual
  MkDocs wikilink plugins (roamlinks, ezlinks) follow Obsidian's opposite `[[Page|Text]]` and would
  silently resolve every aliased link here to the wrong page — hence this script.
* **Images.** Wiki pages must reference images by absolute `raw.githubusercontent.com` URL; on the
  site they are served locally, so the pages make no external requests and the images can be
  indexed with them.
* **Navigation.** `_Sidebar.md` / `_Footer.md` are replaced by the theme's own navigation.

The reference docs under `docs/` are copied to `reference/` and get the same link treatment, so
cross-links between the two halves resolve on the site.

Unresolvable targets are a hard error: a typo in a wiki link fails CI instead of shipping a 404.
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WIKI_DIR = ROOT / "wiki"
DOCS_DIR = ROOT / "docs"
OUT_DIR = ROOT / "build" / "docs-site"

# Wiki files that carry no page content: the publish instructions and the two navigation partials.
WIKI_SKIP = {"README.md", "_Sidebar.md", "_Footer.md"}

# The wiki page whose title contains parentheses; they would have to be percent-escaped in every
# link, so the site gets a plain slug instead.
SLUG_OVERRIDES = {"configuration-devices-yaml": "configuration"}

# The wiki's landing page is the site's landing page.
INDEX_KEY = "home"

REPO = "t-ice/enocean-mqtt-ha"
RAW_IMG_URL = re.compile(rf"https://raw\.githubusercontent\.com/{REPO}/master/docs/img/([\w.\-]+)")
WIKI_URL = re.compile(rf"https://github\.com/{REPO}/wiki/([\w.\-%()]+)")
BLOB_DOCS_URL = re.compile(rf"https://github\.com/{REPO}/blob/master/docs/([\w.\-]+)\.md")
REL_WIKI_LINK = re.compile(r"\.\./wiki/([\w.\-]+(?:\([\w.\-]*\))?[\w.\-]*)")
# Repo-root documents (CONTRIBUTING.md, STYLEGUIDE.md, …) are not part of the site; docs/ links to
# them relatively, which only resolves on GitHub — so point the site at GitHub.
ROOT_FILE_LINK = re.compile(r"\]\(\.\./([A-Z][\w.\-]*\.md)\)")
WIKI_LINK = re.compile(r"\[\[([^\]|]+?)(?:\|([^\]]+?))?\]\]")
DOCS_IMG_LINK = re.compile(r"\]\(img/([\w.\-]+)\)")


def normalize(name: str) -> str:
    """Reduce a page title or file stem to a comparison key.

    GitHub treats spaces and hyphens in wiki page names as equivalent and matches
    case-insensitively, so `[[Teach In]]`, `[[teach-in]]` and `Teach-In.md` are one page.
    """
    return re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")


def build_page_index() -> dict[str, str]:
    """Map every wiki page key to its output filename."""
    pages: dict[str, str] = {}
    for path in sorted(WIKI_DIR.glob("*.md")):
        if path.name in WIKI_SKIP:
            continue
        key = normalize(path.stem)
        slug = SLUG_OVERRIDES.get(key, key)
        pages[key] = "index.md" if key == INDEX_KEY else f"{slug}.md"
        if key != slug:  # let links use the long title as well as the short slug
            pages[slug] = pages[key]
    return pages


class Converter:
    """Rewrites one file's links for its place in the output tree.

    `prefix` is the path back to the site root ("" for the top-level pages, "../" for `reference/`),
    which is what turns a resolved page name into a working relative link.
    """

    def __init__(self, pages: dict[str, str], prefix: str) -> None:
        self.pages = pages
        self.prefix = prefix
        self.errors: list[str] = []

    def _page_link(self, name: str, source: Path) -> str:
        key = normalize(re.sub(r"\.md$", "", name, flags=re.IGNORECASE))
        target = self.pages.get(key)
        if target is None:
            self.errors.append(f"{source.relative_to(ROOT)}: unknown wiki page {name!r}")
            return f"{self.prefix}index.md"
        return f"{self.prefix}{target}"

    def convert(self, text: str, source: Path) -> str:
        def wiki_link(match: re.Match[str]) -> str:
            # GitHub's alias order is [[Text|Page]] — the second group is the target, not the label.
            label, page = match.group(1), match.group(2)
            if page is None:
                label, page = label, label
            return f"[{label}]({self._page_link(page, source)})"

        text = WIKI_LINK.sub(wiki_link, text)
        text = WIKI_URL.sub(lambda m: self._page_link(m.group(1), source), text)
        text = REL_WIKI_LINK.sub(lambda m: self._page_link(m.group(1), source), text)
        text = BLOB_DOCS_URL.sub(lambda m: f"{self.prefix}reference/{m.group(1)}.md", text)
        text = ROOT_FILE_LINK.sub(rf"](https://github.com/{REPO}/blob/master/\1)", text)
        text = RAW_IMG_URL.sub(lambda m: f"{self.prefix}img/{m.group(1)}", text)
        text = DOCS_IMG_LINK.sub(lambda m: f"]({self.prefix}img/{m.group(1)})", text)
        return text


def main() -> int:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    (OUT_DIR / "reference").mkdir(parents=True)

    pages = build_page_index()
    errors: list[str] = []

    root_conv = Converter(pages, prefix="")
    for path in sorted(WIKI_DIR.glob("*.md")):
        if path.name in WIKI_SKIP:
            continue
        out_name = pages[normalize(path.stem)]
        (OUT_DIR / out_name).write_text(root_conv.convert(path.read_text(), path))
    errors += root_conv.errors

    ref_conv = Converter(pages, prefix="../")
    for path in sorted(DOCS_DIR.glob("*.md")):
        (OUT_DIR / "reference" / path.name).write_text(ref_conv.convert(path.read_text(), path))
    errors += ref_conv.errors

    shutil.copytree(DOCS_DIR / "img", OUT_DIR / "img", ignore=shutil.ignore_patterns("*.sh"))

    if errors:
        print("Broken links:", file=sys.stderr)
        for error in errors:
            print(f"  {error}", file=sys.stderr)
        return 1

    written = len(list(OUT_DIR.glob("*.md"))) + len(list((OUT_DIR / "reference").glob("*.md")))
    print(f"{written} pages written to {OUT_DIR.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
