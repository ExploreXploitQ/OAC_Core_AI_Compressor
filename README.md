# NSF Research Portfolio

This repository contains a self-contained, English GitHub Pages site for the NSF research award **Deep Learning for Artifact Mitigation in Lossy-Compressed Scientific Data**. It presents three research efforts at the same portfolio level: DenseTopo-UNet for topology-oriented restoration of lossy-decompressed 3D scalar fields, PTU-Net for temporal reconstruction of lossy-decompressed 2D scientific fields, and a publication record with Pu Jiao as first author on quantization-aware interpolation for pre-quantization-based scientific data compressors.

## Site structure

The static page is served from `index.html` and uses one local stylesheet at `assets/css/site.css`. It includes an award overview, three equal research cards, three detailed research sections, a shared comparison, and the participant list. There is no JavaScript runtime, build step, framework, package manager, remote font, or analytics dependency.

## Local preview and tests

From the repository root, preview the site locally:

```bash
python -m http.server 8000
```

Then open `http://127.0.0.1:8000/` in a browser. Run the static-site verification suite with:

```bash
python -m unittest discover -s tests -v
```

## Asset provenance

The canonical award logo is stored at `assets/images/nsf-logo.png`, copied from the site owner-supplied NSF PNG. The original supplied screenshot is retained locally but ignored. Each project wordmark and architecture SVG is a stable local copy of the corresponding project asset, so the page has no runtime dependency on GitHub raw-content delivery.

The publication metadata is linked to its Google Scholar record and the canonical DOI, `10.1109/IPDPS65963.2026.00024`.

## Evidence policy

The page distinguishes evidence types explicitly. DenseTopo-UNet and PTU-Net are identified as **Alpha research software · evaluation pending**. Quantization-Aware Interpolation is represented by its peer-reviewed IPDPS 2026 publication record and is not described as a neural model, software release, or repository-backed implementation. The site does not infer shared benchmark performance, speed, generalization, pretrained weights, compressor superiority, open-source licensing, or NSF endorsement of research outcomes.

## Deployment

Deployment is intentionally outside this local implementation. This repository includes the static entry point and `.nojekyll` marker for GitHub Pages-compatible serving, but it does not change Pages settings, publish a release, open a pull request, or push commits.
