# Motorcycle controls deck package

This directory is the portable source package for the motorcycle-controls
presentation. The application loads `slide-breakdown.json`, the validated
runtime manifest that owns slide order, narration beats, grounding evidence,
and visual descriptions. The browser requests the matching image from
`renders/`; `deck.pptx` remains the preserved authoring/interchange source.

The intended package shape is:

```text
assets/motorcycle-controls/
  slide-breakdown.json    # normalized runtime contract (required)
  deck.pptx               # preserved user-authored source
  renders/<slide-id>.png  # browser-ready slide images
  additional-context.json # reserved; deliberately not loaded yet
```

The current PPTX has six slides in the same order as the six manifest slides.
Each PowerPoint slide contains one full-slide 1376x768 raster image, so the
checked-in renders are byte-identical extractions rather than reconstructed
screenshots. This preserves the authored appearance, but it also means the PPTX
does not expose editable text/shapes or semantic speaker notes. Automatic
ingestion of this kind of deck will therefore need OCR/VLM plus a validated
handout in a later slice.

PPTX is an authoring and interchange source, not a runtime state model. A future
import command may render and normalize a supplied deck plus handout into this
package, but the domain and provider adapters will continue to consume only the
normalized manifest. This keeps navigation, playout verification, and question
grounding independent of PowerPoint libraries or provider SDKs.
