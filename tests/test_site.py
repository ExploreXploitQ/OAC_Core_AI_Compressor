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
    def assert_entry_point(self) -> None:
        self.assertTrue(INDEX.is_file(), "GitHub Pages entry point is missing")

    def parse_site(self) -> SiteParser:
        self.assert_entry_point()
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
        self.assert_entry_point()
        text = INDEX.read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"TBD|TODO|Lorem ipsum|[\u3400-\u9fff]", text))

    def test_site_is_served_from_the_repository_root(self) -> None:
        self.assert_entry_point()
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
