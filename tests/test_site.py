from __future__ import annotations

import contextlib
import functools
import http.server
import posixpath
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
EXPECTED_PROJECT_LINKS = {
    "https://github.com/ExploreXploitQ/DenseTopo-UNet",
    "https://github.com/ExploreXploitQ/DenseTopo-UNet/blob/main/docs/architecture.md",
    "https://github.com/ExploreXploitQ/DenseTopo-UNet/blob/main/docs/usage.md",
    "https://github.com/ExploreXploitQ/PTU-Net",
    "https://github.com/ExploreXploitQ/PTU-Net/blob/main/docs/architecture.md",
    "https://github.com/ExploreXploitQ/PTU-Net/blob/main/docs/usage.md",
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
        self.title = ""
        self.html_lang = ""
        self.section_text: dict[str, list[str]] = {}
        self.section_headings: dict[str, list[str]] = {}
        self.project_cards: list[dict[str, str]] = []
        self.team_members: list[str] = []
        self.attribute_text: list[str] = []
        self._section_stack: list[str] = []
        self._in_title = False
        self._heading: list[str] | None = None
        self._project_card: dict[str, str] | None = None
        self._project_heading: list[str] | None = None
        self._team_member: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        self.tags.append(tag)
        if tag == "title":
            self._in_title = True
        if any(values.get(key) for key in ("alt", "aria-label", "title", "placeholder")):
            self.attribute_text.extend(values[key] for key in ("alt", "aria-label", "title", "placeholder") if values.get(key))
        if tag == "html":
            self.html_lang = values.get("lang", "")
        if tag == "section" and values.get("id"):
            self._section_stack.append(values["id"])
            self.section_text.setdefault(values["id"], [])
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"} and self._section_stack:
            self._heading = [self._section_stack[-1], ""]
        if tag == "h3" and self._project_card is not None:
            self._project_heading = [""]
        if tag == "article" and "project-card" in values.get("class", "").split():
            self._project_card = {"data-project": values.get("data-project", ""), "text": ""}
            self.project_cards.append(self._project_card)
        if tag == "li" and "team-member" in values.get("class", "").split():
            self._team_member = [""]
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
            value = data.strip()
            self.text.append(value)
            if self._in_title:
                self.title += value
            if self._heading is not None:
                self._heading[1] += value
            if self._project_card is not None:
                self._project_card["text"] += value
            if self._project_heading is not None:
                self._project_heading[0] += value
            if self._team_member is not None:
                self._team_member[0] += value
            if self._section_stack:
                self.section_text[self._section_stack[-1]].append(value)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"} and self._heading is not None:
            section, heading = self._heading
            self.section_headings.setdefault(section, []).append(heading.strip())
            self._heading = None
        if tag == "h3" and self._project_heading is not None and self._project_card is not None:
            self._project_card["heading"] = self._project_heading[0].strip()
            self._project_heading = None
        if tag == "article" and self._project_card is not None:
            self._project_card["text"] = self._project_card["text"].strip()
            self._project_card = None
        if tag == "li" and self._team_member is not None:
            self.team_members.append(self._team_member[0].strip())
            self._team_member = None
        if tag == "section" and self._section_stack:
            self._section_stack.pop()

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_entityref(self, name: str) -> None:
        self.handle_data(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.handle_data(f"&#{name};")

    def handle_comment(self, data: str) -> None:
        pass

    def handle_decl(self, decl: str) -> None:
        pass

    def handle_pi(self, data: str) -> None:
        pass



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
        self.assertEqual("en", parser.html_lang)
        self.assertEqual("Deep Learning for Artifact Mitigation | NSF Research Portfolio", parser.title)
        self.assertIn("nav", parser.tags)
        self.assertIn("main", parser.tags)
        self.assertIn("footer", parser.tags)
        self.assertEqual(
            ["Deep Learning for Artifact Mitigation in Lossy-Compressed Scientific Data"],
            parser.section_headings.get("award", []),
        )
        self.assertEqual(["Yang Zhang", "Xin Liang", "Yujun Feng"], parser.team_members)
        self.assertEqual(
            {"DenseTopo-UNet", "PTU-Net"},
            {card["data-project"] for card in parser.project_cards},
        )
        self.assertEqual(2, len(parser.project_cards))
        self.assertEqual(
            {"DenseTopo-UNet", "PTU-Net"},
            {card["heading"] for card in parser.project_cards},
        )
        self.assertEqual(
            {("DenseTopo-UNet", "DenseTopo-UNet"), ("PTU-Net", "PTU-Net")},
            {(card["data-project"], card["heading"]) for card in parser.project_cards},
        )

    def test_local_references_are_relative_and_resolve(self) -> None:
        parser = self.parse_site()
        broken: list[str] = []
        for reference in parser.references:
            clean = reference.split("#", maxsplit=1)[0]
            if not clean:
                continue
            if clean in EXPECTED_PROJECT_LINKS:
                continue
            self.assertFalse(
                clean.startswith(("/", "//", "http://", "https://", "mailto:", "data:")),
                clean,
            )
            self.assertFalse(posixpath.normpath(clean).startswith(".."), clean)
            if not (ROOT / clean).is_file():
                broken.append(clean)
        self.assertEqual([], broken)
        self.assertEqual(set(), LOCAL_ASSETS - set(parser.references))
        self.assertEqual(set(), EXPECTED_PROJECT_LINKS - set(parser.references))
        for image in parser.images:
            self.assertIn(image.get("src", ""), LOCAL_ASSETS)

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
        parser = self.parse_site()
        visible_text = " ".join(parser.text + parser.attribute_text)
        self.assertIsNone(
            re.search(r"tbd|todo|lorem ipsum|[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]", visible_text, re.IGNORECASE)
        )

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
