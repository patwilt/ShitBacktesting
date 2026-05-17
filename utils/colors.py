"""
Warm, muted colour palette for a calm, premium light-mode interface.

webPro.md aesthetic: soft, warm, minimal. Modern beige/neutral palette.
Avoid: saturated hues, neon tones, harsh blacks, visual noise.
"""

# ── Semantic colour palette ────────────────────────────────────────────────────
COLORS: dict[str, str] = {
    "mint":        "#4E9A72",   # Sage green        - FIRE achieved / success
    "teal":        "#3D8888",   # Sea green          - secondary accent
    "blue":        "#4275A0",   # Dusty blue         - primary accent / DCA lines
    "light_blue":  "#6A9EC0",   # Powder blue        - strategy 1
    "purple":      "#7060A8",   # Dusty purple       - strategy 2 / scenarios
    "lavender":    "#9080C0",   # Soft lavender      - strategy 3
    "green":       "#5EA880",   # Muted sage         - growth bars
    "cyan":        "#5A9EA8",   # Dusty cyan         - strategy 4
    "yellow":      "#C08A38",   # Warm amber         - salary / warning
    "soft_yellow": "#C8A860",   # Muted gold         - DCA line
    "orange":      "#B86238",   # Warm terracotta    - drawdown / risk
    "red":         "#A84848",   # Muted brick red    - danger / depletion
    "pink":        "#B07888",   # Dusty rose         - special highlight
    "muted":       "#8A8480",   # Stone grey         - secondary text / annotations
    "light_grey":  "#B8B4B0",   # Warm light grey    - axis labels
    "near_white":  "#F7F5F0",   # Warm white         - backgrounds
    "dark":        "#2C2520",   # Warm charcoal      - text / annotations on light bg
}

# ── Strategy line colours (5 distinct warm/muted tones) ───────────────────────
STRATEGY_COLORS: list[str] = [
    COLORS["light_blue"],   # Powder blue
    COLORS["purple"],       # Dusty purple
    COLORS["mint"],         # Sage green
    COLORS["cyan"],         # Dusty cyan
    COLORS["pink"],         # Dusty rose
]

# ── Chart theme ────────────────────────────────────────────────────────────────
# Spread into every fig.update_layout() call:  fig.update_layout(**CHART_LAYOUT, ...)
CHART_BG   = "#F7F5F0"   # warm off-white, matches the app background
CHART_TEXT = "#2C2520"   # warm charcoal, readable without harshness

CHART_LAYOUT: dict = {
    "template":      "plotly_white",
    "paper_bgcolor": CHART_BG,
    "plot_bgcolor":  CHART_BG,
    "font":          {"color": CHART_TEXT, "family": "system-ui, -apple-system, sans-serif"},
}
