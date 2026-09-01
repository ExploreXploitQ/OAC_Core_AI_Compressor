# NSF Research Portfolio Website Design

**Date:** 2026-08-31  
**Status:** Approved for implementation  
**Repository:** `ExploreXploitQNSF.github.io`

## 1. Purpose

The website presents one NSF award and its two current research projects:

1. DenseTopo-UNet, which studies topology-aware restoration of lossy-decompressed 3D scalar fields; and
2. PTU-Net, which studies temporal neural reconstruction of lossy-decompressed 2D scientific fields.

The award title is **Deep Learning for Artifact Mitigation in Lossy-Compressed Scientific Data**. The listed participants are **Yang Zhang, Xin Liang, and Yujun Feng**. Award number and project period are intentionally omitted because they were not supplied.

The site is an English-only academic project page inspired by the content organization of `https://lxaltria.github.io/crii.html`. It preserves the reference page's award overview and research-output hierarchy while using a more contemporary, responsive visual system.

## 2. Delivery Model

The site is a self-contained static page consisting of semantic HTML and one CSS file. It has no JavaScript runtime, package manager, framework, remote font, analytics script, or build step. GitHub Pages serves `index.html` directly.

Every internal URL is relative so deployment remains correct if the repository is served as a GitHub Pages project site rather than an account root site. Project GitHub URLs are absolute HTTPS links.

## 3. Page Structure

### 3.1 Header and navigation

A compact sticky header contains the site mark and four in-page navigation links:

- Award
- Projects
- Research
- Team

A visible keyboard skip link targets the main content. On narrow screens, navigation wraps without requiring a scripted menu.

### 3.2 Award hero

The hero places the supplied NSF logo beside:

- the eyebrow `NSF Research Award`;
- the award title;
- a concise description of neural artifact mitigation for scientific lossy compression;
- the three participant names; and
- calls to view the projects or the GitHub repositories.

Three factual summary items communicate the portfolio at a glance: two research projects, 2D and 3D scientific fields, and a shared artifact-mitigation objective. These are descriptive labels, not performance metrics.

### 3.3 Award overview

The award overview explains the scientific motivation: error-bounded lossy compression reduces data movement and storage, but decompression artifacts can affect downstream numerical and topological analysis. The program investigates neural post-processing methods that operate on already decompressed fields.

The text must not claim that either method guarantees topology, preserves an original-relative error bound, improves PSNR, or has achieved a target reduction unless a published result supports that claim.

### 3.4 Project overview cards

Two linked cards introduce the projects as complementary directions:

- **DenseTopo-UNet — 3D topology restoration:** one decompressed volume at inference, gated residual 3D U-Net, topology-aware training supervision, and tiled full-volume restoration.
- **PTU-Net — 2D temporal reconstruction:** three adjacent decompressed fields, an adaptive temporal baseline, patch-transformer correction, gated U-Net refinement, and overlapping full-field reconstruction.

Each card includes a project wordmark, dimensionality label, concise verified summary, technology tags, and links to its detail section and GitHub repository.

### 3.5 Detailed project sections

Each project receives a full-width section with:

- a numbered project label;
- verified research question and method summary;
- a compact input/method/output flow;
- three or four implementation-backed capability bullets;
- its existing accessible architecture SVG;
- links to GitHub, architecture documentation, and usage documentation; and
- an `Alpha research software · evaluation pending` evidence note.

The page may say that implementations are available, but it must not call the repositories open source because neither repository contains a license grant.

### 3.6 Shared research vision

A comparison section shows how the projects fit the award:

| Dimension | PTU-Net | DenseTopo-UNet |
| --- | --- | --- |
| Scientific field | 2D | 3D |
| Deployment input | Three adjacent decompressed fields | One decompressed volume |
| Primary artifact focus | Temporal and local reconstruction | False critical-point topology |
| Neural design | Temporal baseline + transformer + gated U-Net | Gated residual 3D U-Net |

This section describes research scope, not comparative performance.

### 3.7 Team and footer

The team section lists Yang Zhang, Xin Liang, and Yujun Feng without invented roles, affiliations, biographies, or contact details. The footer links to both repositories and states that the website is an NSF research portfolio. It does not imply NSF endorsement of specific software outcomes.

## 4. Visual System

The visual language combines NSF-inspired navy and gold with the projects' teal, blue, and amber accents:

- deep navy `#071a2f` for the header and high-emphasis surfaces;
- scientific blue `#075a9c` for links and project accents;
- NSF gold `#d7ae38` for award markers;
- teal `#0d8f83` for topology-oriented accents;
- warm off-white `#f5f3ed` and white for page surfaces;
- slate `#40556b` for supporting text.

Typography uses a local system stack. Large editorial headings, restrained rules, numbered sections, rounded cards, and subtle grid textures produce an academic rather than commercial tone. Shadows and motion remain minimal.

The NSF logo is copied from the supplied PNG to `assets/images/nsf-logo.png`. The original file remains untouched. Each project wordmark and architecture diagram is copied from its repository into a stable local asset path so the site has no runtime dependency on GitHub raw-content delivery.

## 5. Responsive Behavior

The content width is capped near 1180 pixels. The hero uses two columns on large screens and one column below 820 pixels. Project cards use two columns on desktop and one column on mobile. Detailed method flows and comparison rows stack at small sizes. Images use intrinsic dimensions, `max-width: 100%`, and reserved aspect ratios to avoid layout shifts.

The page remains usable at 320 CSS pixels wide without horizontal scrolling.

## 6. Accessibility

The implementation includes:

- semantic landmarks and heading order;
- descriptive image alternative text;
- `<title>` and `<desc>` already embedded in project SVGs;
- a skip link;
- visible `:focus-visible` states;
- adequate text/background contrast;
- link text that makes sense out of context;
- no information communicated by color alone; and
- a `prefers-reduced-motion` rule that disables smooth scrolling and decorative transitions.

The supplied NSF screenshot is used as a logo with descriptive alternative text. It is not treated as textual content.

## 7. Evidence and Attribution Rules

The website may describe behavior verified by the two repositories. It must state that both are alpha research implementations and evaluation is pending. It must not include benchmark numbers, speed claims, generalization claims, pretrained-model claims, or compressor-superiority claims.

SPERR, SZ3, ZFP, MGARD, HPEZ, and other compressors are not listed as validated targets on the landing page. Project documentation remains the source for interface examples and detailed limitations.

The NSF logo is used only to identify the award context supplied by the site owner. The footer includes: `Any opinions, findings, and conclusions presented by these research projects are those of the authors and do not necessarily reflect the views of the National Science Foundation.`

## 8. Files

```text
index.html
assets/css/site.css
assets/images/nsf-logo.png
assets/images/densetopo-wordmark.svg
assets/images/densetopo-architecture.svg
assets/images/ptunet-wordmark.svg
assets/images/ptunet-architecture.svg
tests/test_site.py
.gitignore
.nojekyll
README.md
```

`tests/test_site.py` uses only the Python standard library. It verifies required sections and copy, relative local assets, resolved internal links, accessible image metadata, absence of placeholder text, stylesheet features, and absence of prohibited tracked research artifacts.

## 9. Verification

The final local verification consists of:

1. `python -m unittest discover -s tests -v`;
2. parsing `index.html` with the standard-library HTML parser;
3. parsing copied SVGs as XML;
4. checking every local `href` and `src` target;
5. serving the repository with `python -m http.server` and requesting the page and assets;
6. viewport screenshots at desktop and mobile sizes when a local browser is available;
7. `git diff --check`; and
8. confirming that no model weights, raw scientific volumes, build products, or generated screenshots are tracked.

No remote push, pull request, release, or GitHub Pages configuration change is part of this implementation.
