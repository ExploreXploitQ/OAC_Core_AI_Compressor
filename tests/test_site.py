from __future__ import annotations

import contextlib
import functools
import http.server
import posixpath
import re
import subprocess
import struct
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
SCHOLAR_PUBLICATION_URL = (
    "https://scholar.google.com/citations?view_op=view_citation&hl=en&user="
    "egeD-DMAAAAJ&sortby=pubdate&citation_for_view=egeD-DMAAAAJ:4xDN1ZYqzskC"
)
PUBLICATION_DOI_URL = "https://doi.org/10.1109/IPDPS65963.2026.00024"
EXPECTED_PUBLIC_LINKS = {
    "https://github.com/ExploreXploitQ/DenseTopo-UNet",
    "https://github.com/ExploreXploitQ/DenseTopo-UNet/blob/main/docs/architecture.md",
    "https://github.com/ExploreXploitQ/DenseTopo-UNet/blob/main/docs/usage.md",
    "https://github.com/ExploreXploitQ/PTU-Net",
    "https://github.com/ExploreXploitQ/PTU-Net/blob/main/docs/architecture.md",
    "https://github.com/ExploreXploitQ/PTU-Net/blob/main/docs/usage.md",
    SCHOLAR_PUBLICATION_URL,
    PUBLICATION_DOI_URL,
}
EXPECTED_EFFORTS = {
    "DenseTopo-UNet",
    "PTU-Net",
    "Quantization-Aware Interpolation",
}


def contrast_ratio(first: str, second: str) -> float:
    def luminance(color: str) -> float:
        channels = [int(color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
        linear = [channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4 for channel in channels]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]
    lighter, darker = sorted((luminance(first), luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def css_rule(css: str, selector: str) -> str:
    match = re.search(re.escape(selector) + r"\s*\{([^{}]*)\}", css)
    return match.group(1) if match else ""


def css_media(css: str, query: str) -> str:
    start = css.find("@media " + query)
    if start < 0:
        return ""
    opening = css.find("{", start)
    depth = 0
    for index in range(opening, len(css)):
        if css[index] == "{":
            depth += 1
        elif css[index] == "}":
            depth -= 1
            if depth == 0:
                return css[opening + 1:index]
    return ""


def css_variables(css: str) -> dict[str, str]:
    root = css_rule(css, ":root")
    return dict(re.findall(r"(--[\w-]+):\s*(#[0-9a-fA-F]{6})", root))


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
        self.project_details: list[dict[str, str]] = []
        self.team_members: list[str] = []
        self.attribute_text: list[str] = []
        self.all_attributes: list[dict[str, str]] = []
        self.evidence_by_detail: dict[str, list[str]] = {}
        self.figures: list[dict[str, list[str]]] = []
        self.publication_venues: list[str] = []
        self.publication_metadata: list[str] = []
        self.comparison_headers: list[str] = []
        self.comparison_rows: list[list[str]] = []
        self._section_stack: list[str] = []
        self._in_title = False
        self._heading: list[str] | None = None
        self._project_card: dict[str, str] | None = None
        self._project_heading: list[str] | None = None
        self._project_detail: dict[str, str] | None = None
        self._detail_heading: list[str] | None = None
        self._team_member: list[str] | None = None
        self._detail_id: str | None = None
        self._evidence: list[str] | None = None
        self._figure: dict[str, list[str]] | None = None
        self._publication_field: list[str] | None = None
        self._comparison_area = ""
        self._comparison_row: list[str] | None = None
        self._comparison_cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        self.all_attributes.append(values)
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
        if tag == "article" and "project-detail" in values.get("class", "").split():
            self._detail_id = values.get("id", "")
            self.evidence_by_detail.setdefault(self._detail_id, [])
            self._project_detail = {
                "id": self._detail_id,
                "data-project": values.get("data-project", ""),
                "heading": "",
                "has-question": "false",
                "has-evidence": "false",
                "has-links": "false",
            }
            self.project_details.append(self._project_detail)
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"} and self._project_detail is not None:
            self._detail_heading = [""]
        if tag == "p" and "project-question" in values.get("class", "").split() and self._project_detail is not None:
            self._project_detail["has-question"] = "true"
        if tag == "p" and "project-links" in values.get("class", "").split() and self._project_detail is not None:
            self._project_detail["has-links"] = "true"
        if tag == "p" and "evidence-note" in values.get("class", "").split():
            self._evidence = [""]
            if self._project_detail is not None:
                self._project_detail["has-evidence"] = "true"
        if tag == "p" and "publication-venue" in values.get("class", "").split():
            self._publication_field = ["venue", ""]
        if tag == "p" and "publication-meta" in values.get("class", "").split():
            self._publication_field = ["metadata", ""]
        if tag == "figure":
            self._figure = {"images": [], "text": []}
        if tag == "table":
            self._comparison_area = "table"
        elif tag == "thead" and self._comparison_area == "table":
            self._comparison_area = "head"
        elif tag == "tbody" and self._comparison_area == "table":
            self._comparison_area = "body"
        elif tag == "tr" and self._comparison_area == "body":
            self._comparison_row = []
        elif tag in {"th", "td"} and self._comparison_area in {"head", "body"}:
            self._comparison_cell = [""]
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
            if self._figure is not None:
                self._figure["images"].append(values.get("src", ""))

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
            if self._detail_heading is not None:
                self._detail_heading[0] += value
            if self._team_member is not None:
                self._team_member[0] += value
            if self._evidence is not None:
                self._evidence[0] += value
            if self._figure is not None:
                self._figure["text"].append(value)
            if self._publication_field is not None:
                self._publication_field[1] += value
            if self._comparison_cell is not None:
                self._comparison_cell[0] += value
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
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"} and self._detail_heading is not None and self._project_detail is not None:
            self._project_detail["heading"] = self._detail_heading[0].strip()
            self._detail_heading = None
        if tag == "article" and self._project_card is not None:
            self._project_card["text"] = self._project_card["text"].strip()
            self._project_card = None
        if tag == "li" and self._team_member is not None:
            self.team_members.append(self._team_member[0].strip())
            self._team_member = None
        if tag == "p" and self._evidence is not None:
            if self._detail_id:
                self.evidence_by_detail[self._detail_id].append(self._evidence[0].strip())
            self._evidence = None
        if tag == "p" and self._publication_field is not None:
            target, value = self._publication_field
            if target == "venue":
                self.publication_venues.append(value.strip())
            else:
                self.publication_metadata.append(value.strip())
            self._publication_field = None
        if tag == "article" and self._detail_id is not None:
            self._detail_id = None
            self._project_detail = None
        if tag == "figure" and self._figure is not None:
            self.figures.append(self._figure)
            self._figure = None
        if tag in {"th", "td"} and self._comparison_cell is not None:
            value = self._comparison_cell[0].strip()
            if self._comparison_area == "head":
                self.comparison_headers.append(value)
            elif self._comparison_row is not None:
                self._comparison_row.append(value)
            self._comparison_cell = None
        if tag == "tr" and self._comparison_area == "body" and self._comparison_row is not None:
            self.comparison_rows.append(self._comparison_row)
            self._comparison_row = None
        if tag in {"thead", "tbody"} and self._comparison_area in {"head", "body"}:
            self._comparison_area = "table"
        if tag == "table":
            self._comparison_area = ""
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

    def copyfile(self, source, outputfile) -> None:
        try:
            super().copyfile(source, outputfile)
        except (BrokenPipeError, ConnectionResetError):
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
        self.assertTrue({"award", "projects", "research", "quantization-interpolation", "team"} <= parser.ids)
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
            EXPECTED_EFFORTS,
            {card["data-project"] for card in parser.project_cards},
        )
        self.assertEqual(3, len(parser.project_cards))
        self.assertEqual(
            EXPECTED_EFFORTS,
            {card["heading"] for card in parser.project_cards},
        )
        self.assertEqual(
            {(name, name) for name in EXPECTED_EFFORTS},
            {(card["data-project"], card["heading"]) for card in parser.project_cards},
        )

    def test_three_research_efforts_share_equal_structure_and_comparison(self) -> None:
        parser = self.parse_site()
        self.assertEqual(3, len(parser.project_details))
        self.assertEqual(
            {
                ("densetopo", "DenseTopo-UNet", "DenseTopo-UNet"),
                ("ptunet", "PTU-Net", "PTU-Net"),
                (
                    "quantization-interpolation",
                    "Quantization-Aware Interpolation",
                    "Quantization-Aware Interpolation",
                ),
            },
            {
                (detail["id"], detail["data-project"], detail["heading"])
                for detail in parser.project_details
            },
        )
        for detail in parser.project_details:
            self.assertEqual("true", detail["has-question"], detail["id"])
            self.assertEqual("true", detail["has-evidence"], detail["id"])
            self.assertEqual("true", detail["has-links"], detail["id"])
        self.assertEqual(
            [
                "Dimension",
                "DenseTopo-UNet",
                "PTU-Net",
                "Quantization-Aware Interpolation",
            ],
            parser.comparison_headers,
        )
        self.assertGreaterEqual(len(parser.comparison_rows), 4)
        self.assertTrue(all(len(row) == 4 for row in parser.comparison_rows))
        copy = " ".join(parser.text).lower()
        self.assertNotIn("two research projects", copy)
        self.assertNotIn("two paths", copy)

    def test_local_references_are_relative_and_resolve(self) -> None:
        parser = self.parse_site()
        broken: list[str] = []
        for reference in parser.references:
            clean = reference.split("#", maxsplit=1)[0]
            if not clean:
                continue
            if clean in EXPECTED_PUBLIC_LINKS:
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
        self.assertEqual(set(), EXPECTED_PUBLIC_LINKS - set(parser.references))
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

    def test_internal_fragments_resolve_to_ids(self) -> None:
        parser = self.parse_site()
        fragments = {reference.split("#", 1)[1] for reference in parser.references if "#" in reference and reference.split("#", 1)[1]}
        self.assertTrue(fragments)
        self.assertEqual(set(), fragments - parser.ids)

    def test_stylesheet_contains_accessibility_and_responsive_contract(self) -> None:
        self.assert_entry_point()
        css = (ROOT / "assets/css/site.css").read_text(encoding="utf-8")
        self.assertIn("assets/css/site.css", LOCAL_ASSETS)
        for token in (".skip-link", ":focus-visible", "outline", "@media (max-width: 820px)", "@media (max-width: 560px)", "@media (prefers-reduced-motion: reduce)"):
            self.assertIn(token, css)
        tablet, mobile = css_media(css, "(max-width: 820px)"), css_media(css, "(max-width: 560px)")
        card_grid = css_rule(css, ".project-card-grid")
        self.assertIn("grid-template-columns: repeat(3, minmax(0, 1fr))", card_grid)
        responsive_cards = css_rule(tablet, ".project-card-grid")
        self.assertIn("grid-template-columns: 1fr", responsive_cards)
        self.assertIn(".comparison-table tbody tr", tablet)
        self.assertIn("grid-template-columns: repeat(2", tablet)
        self.assertIn(".comparison-table tbody td", tablet)
        self.assertIn(".comparison-table tbody tr", mobile)
        mobile_row = css_rule(mobile, ".comparison-table tbody tr")
        self.assertIn("grid-template-columns: 1fr", mobile_row)
        reduced = css_media(css, "(prefers-reduced-motion: reduce)")
        self.assertIn("scroll-behavior: auto", reduced)
        self.assertIn("transition-duration", reduced)
        self.assertRegex(css, r"--teal-600:\s*#[0-9a-fA-F]{6}")
        teal_rule = css_rule(css, ".densetopo-card .project-dimension")
        teal = re.search(r"color:\s*(#[0-9a-fA-F]{6})", teal_rule)
        self.assertIsNotNone(teal)
        self.assertGreaterEqual(contrast_ratio(teal.group(1), "#ffffff"), 4.5)
        focus = css_rule(css, ":focus-visible")
        self.assertIn("outline", focus)
        self.assertRegex(focus, r"outline:[^;]*var\(--surface\)")
        layered = css_rule(css, ":is(a, [tabindex]):focus-visible")
        self.assertRegex(layered, r"box-shadow:[^;]*var\(--navy-950\)")
        colors = css_variables(css)
        self.assertGreaterEqual(contrast_ratio(colors["--surface"], colors["--navy-950"]), 3.0)

        for selector in (
            ".densetopo-card .project-dimension",
            ".densetopo-detail .project-number",
            ".densetopo-card .tag-list li",
            ".comparison-table tbody td::before",
        ):
            rule = css_rule(css, selector) or css_rule(css_media(css, "(max-width: 820px)"), selector)
            foreground = re.search(r"color:\s*(#[0-9a-fA-F]{6}|var\(--[\w-]+\))", rule)
            self.assertIsNotNone(foreground, selector)
            value = foreground.group(1)
            value = colors.get(value[4:-1], value)
            self.assertGreaterEqual(contrast_ratio(value, "#ffffff"), 4.5, selector)

    def test_wcag_contrast_for_teal_and_focus_indicator(self) -> None:
        css = (ROOT / "assets/css/site.css").read_text(encoding="utf-8")
        teal_rule = css_rule(css, ".densetopo-card .project-dimension")
        teal = re.search(r"color:\s*(#[0-9a-fA-F]{6})", teal_rule).group(1)
        self.assertGreaterEqual(contrast_ratio(teal, "#ffffff"), 4.5)
        self.assertGreaterEqual(contrast_ratio(teal, "#f5f3ed"), 4.5)
        steps = css_rule(css, ".densetopo-detail .method-flow li::before")
        bg_match = re.search(r"background:\s*(#[0-9a-fA-F]{6}|var\(--[\w-]+\))", steps)
        bg = bg_match.group(1)
        bg = css_variables(css).get(bg[4:-1], bg)
        self.assertGreaterEqual(contrast_ratio("#ffffff", bg), 4.5)

    def test_image_dimensions_loading_and_hero_treatment(self) -> None:
        parser = self.parse_site()
        self.assertGreaterEqual(len(parser.images), 5)
        for image in parser.images:
            width, height = image.get("width", ""), image.get("height", "")
            self.assertRegex(width, r"^[1-9][0-9]*$")
            self.assertRegex(height, r"^[1-9][0-9]*$")
            source = ROOT / image["src"]
            if source.suffix == ".png":
                with source.open("rb") as stream:
                    stream.seek(16)
                    source_width, source_height = struct.unpack(">II", stream.read(8))
            else:
                svg_root = element_tree.parse(source).getroot()
                source_width = int(float(svg_root.attrib["width"].replace("px", "")))
                source_height = int(float(svg_root.attrib["height"].replace("px", "")))
            self.assertAlmostEqual(int(width) / int(height), source_width / source_height, places=3)
            if image.get("src") != "assets/images/nsf-logo.png":
                self.assertEqual("lazy", image.get("loading"))
        nsf = next(image for image in parser.images if image.get("src") == "assets/images/nsf-logo.png")
        self.assertNotEqual("lazy", nsf.get("loading"))

    def test_nsf_symbol_is_the_unadorned_supplied_image(self) -> None:
        parser = self.parse_site()
        nsf = next(image for image in parser.images if image.get("src") == "assets/images/nsf-logo.png")
        self.assertIn("nsf-logo", nsf.get("class", "").split())
        self.assertFalse(
            any("assets/images/nsf-logo.png" in figure["images"] for figure in parser.figures),
            "The NSF image must not carry a visible figure caption or badge treatment",
        )
        self.assertNotIn("research award context", " ".join(parser.text).lower())

    def test_all_tracked_public_artifacts_are_english_and_placeholder_free(self) -> None:
        tracked = subprocess.check_output(["git", "ls-files"], text=True, cwd=ROOT).splitlines()
        public = [path for path in tracked if Path(path).suffix.lower() in {".html", ".css", ".svg"} or Path(path).name.lower() == "readme.md"]
        forbidden = re.compile(r"tbd|todo|lorem ipsum|[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]", re.IGNORECASE)
        for path in public:
            self.assertIsNone(forbidden.search((ROOT / path).read_text(encoding="utf-8")), path)

    def test_tracked_files_exclude_model_data_and_generated_artifacts(self) -> None:
        tracked = subprocess.check_output(["git", "ls-files"], text=True, cwd=ROOT).splitlines()
        prohibited = re.compile(r"(?:\.pt|\.pth|\.ckpt|\.f32|\.raw|\.npy|\.npz)$", re.IGNORECASE)
        for path in tracked:
            self.assertFalse(prohibited.search(path), path)
            self.assertNotIn("__pycache__", path)
            self.assertNotIn("Screenshot", path)
            self.assertFalse(path.startswith(".artifacts/"), path)

    def test_site_serves_from_parent_path_with_all_assets(self) -> None:
        self.assert_entry_point()
        handler = functools.partial(QuietHandler, directory=ROOT.parent)
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        prefix = "/ExploreXploitQNSF.github.io/"
        paths = ["", "assets/css/site.css", "assets/images/nsf-logo.png", "assets/images/densetopo-wordmark.svg", "assets/images/densetopo-architecture.svg", "assets/images/ptunet-wordmark.svg", "assets/images/ptunet-architecture.svg"]
        expected = {"": "text/html", "assets/css/site.css": "text/css", "assets/images/nsf-logo.png": "image/png"}
        try:
            for path in paths:
                with urllib.request.urlopen(f"http://127.0.0.1:{server.server_port}{prefix}{path}", timeout=5) as response:
                    self.assertEqual(200, response.status)
                    if path in expected:
                        self.assertEqual(expected[path], response.headers.get_content_type())
                    elif path.endswith(".svg"):
                        self.assertEqual("image/svg+xml", response.headers.get_content_type())
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()

    def test_project_evidence_notes_are_present(self) -> None:
        parser = self.parse_site()
        self.assertEqual(
            {"densetopo", "ptunet", "quantization-interpolation"},
            set(parser.evidence_by_detail),
        )
        for detail in ("densetopo", "ptunet"):
            notes = parser.evidence_by_detail[detail]
            self.assertEqual(1, len(notes), detail)
            self.assertIn("alpha research software", notes[0].lower())
            self.assertIn("evaluation pending", notes[0].lower())
        publication_notes = parser.evidence_by_detail["quantization-interpolation"]
        self.assertEqual(1, len(publication_notes))
        self.assertIn("peer-reviewed publication", publication_notes[0].lower())
        self.assertIn("ipdps 2026", publication_notes[0].lower())
        copy = " ".join(parser.text).lower()
        self.assertIn("training-only reference and topology supervision", copy)
        self.assertIn("temporal reconstruction method", copy)

    def test_publication_identifies_pu_jiao_and_verified_record(self) -> None:
        parser = self.parse_site()
        title = "Mitigating Artifacts in Pre-quantization Based Scientific Data Compressors with Quantization-aware Interpolation"
        copy = re.sub(
            r"\s+([,.;:])",
            r"\1",
            " ".join(parser.text),
        )
        self.assertIn(
            title,
            copy,
        )
        self.assertIn(
            "Pu Jiao, Sheng Di, Jiannan Tian, Mingze Xia, Xuan Wu, Yang Zhang, Xin Liang, and Franck Cappello",
            copy,
        )
        self.assertEqual(["IPDPS 2026 · IEEE"], parser.publication_venues)
        self.assertEqual(
            ["Proceedings of the 40th IEEE International Parallel and Distributed Processing Symposium, pages 144–158, 2026."],
            parser.publication_metadata,
        )
        self.assertIn(SCHOLAR_PUBLICATION_URL, parser.references)
        self.assertIn(PUBLICATION_DOI_URL, parser.references)

    def test_site_has_no_javascript_external_fonts_or_remote_images(self) -> None:
        parser = self.parse_site()
        self.assertNotIn("script", parser.tags)
        css = (ROOT / "assets/css/site.css").read_text(encoding="utf-8")
        self.assertNotRegex(css, r"@import\b|@font-face\b|url\(\s*[\"']?(?:https?:|//|data:)")
        self.assertFalse(any("fonts.googleapis" in value for value in parser.references))
        self.assertFalse(any(key.lower().startswith("on") for attrs in parser.all_attributes for key in attrs))
        self.assertTrue(all(not image.get("src", "").startswith(("http:", "https:", "//", "data:")) for image in parser.images))


if __name__ == "__main__":
    unittest.main()
