"""
NYL brand constants.

Shared by core/ui.py's Streamlit CSS injection and styling logic. demo.html
can't import Python, so its <style> block keeps its own manually-mirrored
copy of these same values -- if these ever change, update both places (see
demo.html's CSS variables, same pattern already used for the schema.py
column-candidate lists that are mirrored into demo.html's JS).

No official NYL logo asset file (SVG/PNG) was provided -- the user shared a
reference image instead (blue square, stacked white "NEW YORK LIFE" text).
core/ui.py's _logo_mark_html() and demo.html's .logo-mark recreate that in
plain CSS/HTML rather than embedding a screenshot as a binary asset. Swap
both for a real <img>/<svg> once an actual logo file is available.
"""

from __future__ import annotations

DARK_BLUE = "#000A62"  # primary surfaces, headlines, buttons, most-severe status
BLUE = "#0468FF"  # logo background, eyebrow labels, section markers, manual-review status
GREEN = "#016355"  # PASS / RECONCILED states
GREY = "#E3E0DD"  # the only non-white background color
WHITE = "#FFFFFF"

HEADLINE_FONT = "Georgia, 'Times New Roman', serif"
BODY_FONT = "Arial, Helvetica, sans-serif"

# Maps a ReconStatus value to its brand color. No red/yellow exists in the
# brand palette, so severity is expressed by weight (Dark Blue is the
# heaviest, reserved for the most severe status) rather than a traffic-light
# scheme.
STATUS_COLORS = {
    "RECONCILED": GREEN,
    "DOES NOT RECONCILE": DARK_BLUE,
    "MANUAL REVIEW": BLUE,
}
