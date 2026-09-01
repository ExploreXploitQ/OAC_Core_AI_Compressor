# NSF Research Portfolio Website Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a responsive English GitHub Pages site for one NSF award and its two research projects, DenseTopo-UNet and PTU-Net.

**Architecture:** Serve one semantic `index.html` directly from GitHub Pages, with a single local stylesheet and locally copied project graphics. Use relative internal paths, no JavaScript, no framework, and no build step. Verify the deployed artifact with standard-library Python tests, a local HTTP server, XML parsing, link resolution, and Firefox screenshots.

**Tech Stack:** HTML5, CSS3, Python 3 standard library, GitHub Pages, headless Firefox for visual inspection

**Spec:** `docs/superpowers/specs/2026-08-31-nsf-research-portfolio-design.md`

## Global Constraints

- All public website copy and labels are English.
- The award title is `Deep Learning for Artifact Mitigation in Lossy-Compressed Scientific Data`.
- Participants are `Yang Zhang`, `Xin Liang`, and `Yujun Feng`; do not invent roles or affiliations.
- Omit award number and project period.
- Present exactly two current projects: DenseTopo-UNet and PTU-Net.
- Use the user-supplied NSF PNG and the projects' existing wordmark and architecture SVG files.
- Keep every site-local URL relative for GitHub Pages project-site compatibility.
- Do not add JavaScript, remote fonts, analytics, a package manager, or a build framework.
- Do not claim verified performance, open-source licensing, pretrained weights, or generalization.
- State `Alpha research software · evaluation pending` for both projects.
- Do not push, create a pull request, publish a release, or change remote Pages settings.

---

### Task 1: Executable Static-Site Contract

**Files:**
- Create: `tests/test_site.py`

**Interfaces:**
- Consumes: the repository root as a candidate static GitHub Pages artifact.
- Produces: `SiteParser`, `StaticSiteTests`, local-link validation, SVG validation, and HTTP-serving integration checks.

- [ ] **Step 1: Write the failing site contract tests**

Create a standard-library `unittest` suite. The parser must collect start tags, element IDs, link/image attributes, page title, and visible text from the real `index.html`.

```python
from __future__ import annotations

import contextlib
import functools
import http.server
import re
import threading
import unittest
import urllib.request
import xml.etree.ElementTree as element_tree
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
LOCAL_ASSETS = {
    "assets/css/site.css",
    "assets/images/nsf-logo.png",
    "assets/images/densetopo-wordmark.svg",
    "assets/images/densetopo-architecture.svg",
    "assets/images/ptunet-wordmark.svg",
    "assets/images/ptunet-architecture.svg",
}


class SiteParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[str] = []
        self.ids: set[str] = set()
        self.references: list[str] = []
        self.anchors: list[dict[str, str]] = []
        self.images: list[dict[str, str]] = []
        self.text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        self.tags.append(tag)
        if values.get("id"):
            self.ids.add(values["id"])
        for key in ("href", "src"):
            if values.get(key):
                self.references.append(values[key])
        if tag == "a":
            self.anchors.append(values)
        if tag == "img":
            self.images.append(values)

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.text.append(data.strip())


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


class StaticSiteTests(unittest.TestCase):
    def parse_site(self) -> SiteParser:
        self.assertTrue(INDEX.is_file(), "GitHub Pages entry point is missing")
        parser = SiteParser()
        parser.feed(INDEX.read_text(encoding="utf-8"))
        return parser

    def test_page_exposes_semantic_award_and_project_sections(self) -> None:
        parser = self.parse_site()
        self.assertTrue({"award", "projects", "research", "team"} <= parser.ids)
        self.assertIn("nav", parser.tags)
        self.assertIn("main", parser.tags)
        self.assertIn("footer", parser.tags)
        copy = " ".join(parser.text)
        self.assertIn("Deep Learning for Artifact Mitigation", copy)
        for name in ("Yang Zhang", "Xin Liang", "Yujun Feng"):
            self.assertIn(name, copy)
        for project in ("DenseTopo-UNet", "PTU-Net"):
            self.assertIn(project, copy)

    def test_local_references_are_relative_and_resolve(self) -> None:
        parser = self.parse_site()
        broken: list[str] = []
        for reference in parser.references:
            clean = reference.split("#", maxsplit=1)[0]
            if not clean or clean.startswith(("https://", "http://", "mailto:")):
                continue
            self.assertFalse(clean.startswith("/"), clean)
            if not (ROOT / clean).is_file():
                broken.append(clean)
        self.assertEqual([], broken)
        self.assertEqual(set(), LOCAL_ASSETS - {str(path.relative_to(ROOT)) for path in ROOT.rglob("*") if path.is_file()})

    def test_new_tab_links_do_not_expose_the_opener(self) -> None:
        parser = self.parse_site()
        new_tab_links = [anchor for anchor in parser.anchors if anchor.get("target") == "_blank"]
        self.assertGreaterEqual(len(new_tab_links), 6)
        for anchor in new_tab_links:
            self.assertIn("noreferrer", anchor.get("rel", "").split())

    def test_images_have_alternative_text_and_svg_metadata(self) -> None:
        parser = self.parse_site()
        self.assertGreaterEqual(len(parser.images), 5)
        self.assertTrue(all(image.get("alt", "").strip() for image in parser.images))
        for path in (ROOT / "assets/images").glob("*.svg"):
            root = element_tree.parse(path).getroot()
            names = {child.tag.rsplit("}", maxsplit=1)[-1] for child in root}
            self.assertIn("title", names, path)
            self.assertIn("desc", names, path)

    def test_public_page_has_no_placeholders_or_cjk(self) -> None:
        text = INDEX.read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"TBD|TODO|Lorem ipsum|[\u3400-\u9fff]", text))

    def test_site_is_served_from_the_repository_root(self) -> None:
        handler = functools.partial(QuietHandler, directory=ROOT)
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{server.server_port}/", timeout=5
            ) as response:
                self.assertEqual(200, response.status)
                self.assertIn("text/html", response.headers.get_content_type())
                body = response.read().decode("utf-8")
                self.assertIn("DenseTopo-UNet", body)
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test and verify the correct RED state**

Run:

```bash
python -m unittest discover -s tests -v
```

Expected: tests fail because `index.html` and the canonical local assets do not exist. The failure must name the missing GitHub Pages entry point, not a Python import or syntax error.

- [ ] **Step 3: Commit the red contract**

```bash
git add tests/test_site.py
git commit -m "test: define static research site contract"
```

### Task 2: Canonical Research Assets and Semantic Page

**Files:**
- Create: `index.html`
- Create: `assets/images/nsf-logo.png`
- Create: `assets/images/densetopo-wordmark.svg`
- Create: `assets/images/densetopo-architecture.svg`
- Create: `assets/images/ptunet-wordmark.svg`
- Create: `assets/images/ptunet-architecture.svg`

**Interfaces:**
- Consumes: the supplied NSF image, DenseTopo-UNet assets, PTU-Net assets, and verified project documentation.
- Produces: one complete semantic document and stable local image URLs used by the stylesheet and tests.

- [ ] **Step 1: Copy source-controlled assets to canonical relative paths**

Use exact source and target mappings:

```text
Screenshot 2026-09-01 at 1.30.28 AM.png -> assets/images/nsf-logo.png
../DenseTopo-UNet/assets/densetopo-unet-wordmark.svg -> assets/images/densetopo-wordmark.svg
../DenseTopo-UNet/assets/architecture.svg -> assets/images/densetopo-architecture.svg
../PTU-Net/assets/ptu-net-wordmark.svg -> assets/images/ptunet-wordmark.svg
../PTU-Net/assets/architecture.svg -> assets/images/ptunet-architecture.svg
```

Resolve the actual U+202F character in the supplied screenshot filename from the filesystem rather than typing an approximate ASCII filename. Preserve the original file.

- [ ] **Step 2: Write the semantic document**

Create `index.html` with:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="NSF research portfolio for deep-learning methods that mitigate artifacts in lossy-compressed scientific data.">
  <title>Deep Learning for Artifact Mitigation | NSF Research Portfolio</title>
  <link rel="stylesheet" href="assets/css/site.css">
</head>
<body>
  <a class="skip-link" href="#main-content">Skip to main content</a>
  <header class="site-header">...</header>
  <main id="main-content">
    <section class="hero" id="award">...</section>
    <section class="section" aria-labelledby="award-overview-title">...</section>
    <section class="section" id="projects" aria-labelledby="projects-title">...</section>
    <article class="project-detail" id="densetopo">...</article>
    <article class="project-detail" id="ptunet">...</article>
    <section class="section" id="research" aria-labelledby="research-title">...</section>
    <section class="section" id="team" aria-labelledby="team-title">...</section>
  </main>
  <footer class="site-footer">...</footer>
</body>
</html>
```

Fill every section with the exact award title, participant names, verified summaries from the design spec, project method flows, evidence notes, and these public links:

```text
https://github.com/ExploreXploitQ/DenseTopo-UNet
https://github.com/ExploreXploitQ/DenseTopo-UNet/blob/main/docs/architecture.md
https://github.com/ExploreXploitQ/DenseTopo-UNet/blob/main/docs/usage.md
https://github.com/ExploreXploitQ/PTU-Net
https://github.com/ExploreXploitQ/PTU-Net/blob/main/docs/architecture.md
https://github.com/ExploreXploitQ/PTU-Net/blob/main/docs/usage.md
```

Every external link opened in a new tab must include `rel="noreferrer"`. Image elements use width and height attributes matching source aspect ratios, `loading="lazy"` below the hero, and descriptive alternative text.

- [ ] **Step 3: Run the tests and verify the expected intermediate failure**

Run:

```bash
python -m unittest discover -s tests -v
```

Expected: semantic, content, link, and image tests pass; the local-reference test still fails only because `assets/css/site.css` is missing.

### Task 3: Responsive Academic Visual System

**Files:**
- Create: `assets/css/site.css`

**Interfaces:**
- Consumes: semantic class names and component hierarchy from `index.html`.
- Produces: responsive, accessible, self-contained presentation for desktop and mobile GitHub Pages rendering.

- [ ] **Step 1: Implement design tokens and global behavior**

Define exact custom properties:

```css
:root {
  --navy-950: #071a2f;
  --navy-900: #0b223d;
  --blue-700: #075a9c;
  --blue-500: #1887c7;
  --gold-500: #d7ae38;
  --teal-600: #0d8f83;
  --paper: #f5f3ed;
  --surface: #ffffff;
  --slate-700: #40556b;
  --slate-500: #687d91;
  --rule: #d8e0e7;
  --content: 73.75rem;
  --radius-lg: 1.5rem;
  --radius-md: 1rem;
  --shadow: 0 1.25rem 3.5rem rgb(7 26 47 / 0.10);
}
```

Add border-box sizing, system typography, readable line height, responsive images, anchor offset for the sticky header, a visible skip link, and strong `:focus-visible` outlines.

- [ ] **Step 2: Implement component layout**

Style the sticky translucent header, two-column hero, NSF seal container, summary strip, award narrative, two project cards, detailed project layouts, flow chips, architecture figures, comparison grid, team list, and dark footer. Use navy/gold for award-level elements, teal for DenseTopo-UNet, and blue/amber for PTU-Net.

Project cards must not use hover-only content. Hover may translate a card by no more than two pixels and must not alter document flow.

- [ ] **Step 3: Add responsive and reduced-motion rules**

Use breakpoints at 820 and 560 CSS pixels. Below 820 pixels, stack the hero, project cards, project detail grids, and research comparison. Below 560 pixels, reduce heading sizes, wrap navigation, and make calls to action full-width where useful.

```css
@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
  *, *::before, *::after {
    scroll-behavior: auto !important;
    transition-duration: 0.01ms !important;
  }
}
```

- [ ] **Step 4: Run the complete test suite**

Run:

```bash
python -m unittest discover -s tests -v
```

Expected: all tests pass with no warnings or server tracebacks.

- [ ] **Step 5: Commit the deployable site**

```bash
git add index.html assets tests/test_site.py
git commit -m "feat: build NSF research portfolio site"
```

### Task 4: Repository Handoff and Visual Verification

**Files:**
- Modify: `README.md`
- Create: `.gitignore`
- Create: `.nojekyll`

**Interfaces:**
- Consumes: the complete static site.
- Produces: contributor-facing local preview instructions, clean repository state, and GitHub Pages static-serving marker.

- [ ] **Step 1: Write the repository handoff**

Replace the one-line README with an English project summary, page structure, local preview command, test command, asset provenance, evidence policy, and deployment note:

```bash
python -m http.server 8000
python -m unittest discover -s tests -v
```

State that deployment is intentionally outside this local implementation.

- [ ] **Step 2: Add static-hosting and ignore rules**

Create an empty `.nojekyll`. Add `.gitignore` entries for Python caches, local screenshots, headless-browser artifacts, and the original screenshot filename pattern while retaining the canonical `assets/images/nsf-logo.png`:

```gitignore
__pycache__/
*.py[cod]
.artifacts/
Screenshot*.png
```

- [ ] **Step 3: Run automated verification**

```bash
python -m unittest discover -s tests -v
git diff --check
```

Expected: all tests pass and no whitespace errors are reported.

- [ ] **Step 4: Run the site through a real local HTTP server**

Start `python -m http.server` on a free loopback port, request `/`, `assets/css/site.css`, the NSF PNG, and all four SVGs, and verify HTTP 200 for each target. Stop the server after verification.

- [ ] **Step 5: Capture and inspect responsive screenshots**

Using `/usr/bin/firefox --headless`, capture:

```text
.artifacts/site-desktop.png at 1440x1200
.artifacts/site-mobile.png at 390x844
```

Inspect both images for clipped text, horizontal overflow, missing assets, unreadable contrast, broken grids, and misleading hierarchy. If a visual defect is found, add a failing structural or browser-observable test when practical, fix the CSS or markup, rerun tests, and recapture both screenshots.

- [ ] **Step 6: Audit tracked files and repository state**

Confirm that tracked content contains no `.pt`, `.pth`, `.ckpt`, `.f32`, `.raw`, `.npy`, `.npz`, generated screenshot, or source data artifact. Confirm that the original NSF screenshot remains locally available but ignored, the canonical asset is tracked, and no remote operation occurred.

- [ ] **Step 7: Commit the handoff**

```bash
git add README.md .gitignore .nojekyll
git commit -m "docs: document local site workflow"
```

### Task 5: Final Completion Gate

**Files:**
- Modify only files required by a discovered verification failure.

**Interfaces:**
- Verifies the exact committed tree that will remain local.

- [ ] **Step 1: Run fresh full verification**

```bash
python -m unittest discover -s tests -v
git diff --check
git status --short --branch
```

Expected: all tests pass, no whitespace error is present, and the only ignored non-source artifacts are local screenshots/caches.

- [ ] **Step 2: Verify GitHub Pages paths and English-only output**

Repeat the local HTTP requests and confirm no internal URL begins with `/`. Scan public HTML, CSS, README, and SVG text for CJK characters and placeholder markers. Confirm the six external project/document links use HTTPS.

- [ ] **Step 3: Report local branch preservation**

Report the local path, commit state, test count, screenshot results, and exact major files. Explicitly state that no push, pull request, release, or Pages configuration change was performed.
