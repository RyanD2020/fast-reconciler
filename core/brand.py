"""
NYL brand constants.

The single source of truth for colors, fonts, status styling and credits.
core/theme.py builds the app's CSS from these, core/components.py builds the
HTML pieces, and demo.html (which can't import Python) keeps a manually
mirrored copy of the colors in its <style> block -- update both if these
change, same pattern as the schema.py column-candidate lists.

No official NYL logo asset file (SVG/PNG) was provided -- the user shared a
reference image instead (blue square, stacked white "NEW YORK LIFE" text).
components.logo_mark() and demo.html's .logo-mark recreate that in plain
HTML/CSS rather than embedding a screenshot as a binary asset. Swap both for
a real <img>/<svg> once an actual logo file is available.

Contrast, measured (WCAG 2.x): white text clears 4.5:1 on all three status
fills (green 7.2, dark blue 17.2, blue 4.7). Blue text does NOT clear 4.5:1
on the dark blue or grey surfaces (3.6 on both) -- so on those surfaces Blue
is used only as a marker (square bullets, accent bars), never for small text.
"""

from __future__ import annotations

DARK_BLUE = "#000A62"  # primary surfaces, headlines, buttons, most-severe status
BLUE = "#0468FF"  # logo background, section markers, manual-review status
GREEN = "#016355"  # PASS / RECONCILED states
GREY = "#E3E0DD"  # the only non-white background color
WHITE = "#FFFFFF"

# Text-only tokens (never backgrounds): secondary ink on white/grey, and the
# light ink used for secondary text on the dark blue surfaces.
INK_MUTED = "#55597F"
INK_ON_DARK = "#B9BCE0"

HEADLINE_FONT = "Georgia, 'Times New Roman', serif"
BODY_FONT = "Arial, Helvetica, sans-serif"

# ReconStatus value -> brand color. No red/yellow exists in the palette, so
# severity is carried by weight (Dark Blue, the heaviest, for the most severe
# status) and always paired with a glyph + label, never color alone.
STATUS_COLORS = {
    "RECONCILED": GREEN,
    "DOES NOT RECONCILE": DARK_BLUE,
    "MANUAL REVIEW": BLUE,
}
STATUS_GLYPHS = {
    "RECONCILED": "✓",  # check mark
    "DOES NOT RECONCILE": "✕",  # multiplication x
    "MANUAL REVIEW": "◆",  # diamond
}
STATUS_CSS = {
    "RECONCILED": "ok",
    "DOES NOT RECONCILE": "bad",
    "MANUAL REVIEW": "manual",
}

BUILT_BY = "Ryan Doswell"
