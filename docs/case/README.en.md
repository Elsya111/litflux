# LitFlux case

[litflux-case-en.html](litflux-case-en.html) is a complete LitFlux build, in one file, readable offline. The Chinese version is [litflux-case.html](litflux-case.html), and the Chinese notes are in [README.md](README.md).

## Opening it

- Download the repository and double-click `litflux-case-en.html`.
- On GitHub you get the raw source view first: use **Download** in the top-right corner, then open the file.
- The file is self-contained: maps, node descriptions and source excerpts are all inline. No Python, no Node.js, no target project needed.

## What it explains

The source under explanation is a small "text saving" program (the same sample as [app.py](../../skills/litflux/examples/semantic-source/app.py)): text is normalized, checked for emptiness, and written when non-empty; the batch entry submits items one at a time and accumulates results.

The page contains 3 workflows, 6 views, 51 objects and 45 relations (15 business, 22 data, 9 resource, 2 component, 3 decision).

- **Submit and save text**: raw text → normalize → cleaned text → emptiness check → save; empty text takes the reject branch.
- **Batch submit texts**: loop over the collection, submit one item at a time, accumulate results.
- **Resource types and source mapping**: how data, resource, component and decision objects are drawn.

## Build state

The build report records `checked` for this build:

| Check | Result |
| --- | --- |
| Declaration and source validation | Passed |
| Semantic audit | 0 errors; 4 "business without detail, sources or text" warnings, an authoring trade-off |
| Browser checks (6 views) | Passed; step-by-step reading, entering and returning from a sub-business, and source references were all exercised in a real browser |
| Geometry | Passed, no blocking warnings |
| Independent review | Not requested, so not `reviewed` |

`checked` covers declarations, geometry and the interactions that are implemented. It does not prove every explanation matches the source, and it does not mean a human has judged the visual readability. Both need the reader, or a separate review.

## Notes

- "Gunmetal & Amber" in the page title is the theme this build was drawn with (rounded nodes, icon tiles, pill-shaped data). The viewer shipped in the package shares the same layout, interactions and reading rules; theme details differ.
- The project module and build script behind this page live in the local working directory `.litflux/work/industrial-rounded/` and `.litflux/work/case-en/`; they are not published with the repository.
- The target source is only read statically; none of the sample functions are executed.
