"""Flat UI Colors — US palette. All charts and UI elements use this dict exclusively."""

COLORS: dict[str, str] = {
    "mint":        "#00b894",   # Mint Leaf          — FIRE achieved / success
    "teal":        "#00cec9",   # Robin's Egg Blue   — secondary accent
    "blue":        "#0984e3",   # Electron Blue      — primary accent / DCA lines
    "light_blue":  "#74b9ff",   # Green Darner Tail  — strategy 1
    "purple":      "#6c5ce7",   # Exodus Fruit       — strategy 2 / scenarios
    "lavender":    "#a29bfe",   # Shy Moment         — strategy 3
    "green":       "#55efc4",   # Light Greenish Blue — growth bars
    "cyan":        "#81ecec",   # Faded Poster       — strategy 4
    "yellow":      "#fdcb6e",   # Sour Lemon         — salary / warning
    "soft_yellow": "#ffeaa7",   # First Date         — DCA line
    "orange":      "#e17055",   # Orangeville        — drawdown / risk
    "red":         "#d63031",   # Chi-Gong           — danger / depletion
    "pink":        "#fd79a8",   # Pink Glamour       — special highlight
    "muted":       "#636e72",   # American River     — secondary text
    "light_grey":  "#b2bec3",   # Soothing Breeze    — axis labels
    "near_white":  "#dfe6e9",   # City Lights        — titles on dark bg
    "dark":        "#2d3436",   # Dracula Orchid     — card backgrounds
}

STRATEGY_COLORS: list[str] = [
    COLORS["light_blue"],
    COLORS["purple"],
    COLORS["mint"],
    COLORS["cyan"],
    COLORS["pink"],
]
