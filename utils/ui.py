"""
Shared UI primitives — calm, palette-aligned components per Agents/webPro.md.

Centralises the visual language used across the planner pages so that:
- spacing, type scale, and colour tokens live in one place
- callouts use the warm palette from utils/colors.py instead of Streamlit's
  loud default info/warning/error boxes
- pages stop reinventing section headers and metric rows

Public API
----------
inject_base_styles()         Inject the shared <style> block. Call once near
                             the top of every page (idempotent in a session).
section_header(title, ...)   H2 with optional muted subtitle. Replaces ad-hoc
                             st.subheader + st.caption pairs.
metric_row(items)            Render a row of KPI metrics with consistent
                             spacing. Each item is a (label, value) tuple or
                             a dict with label/value/delta/help keys.
callout(kind, body, ...)     Soft, palette-aware alternative to st.info /
                             st.warning / st.error / st.success.
spacer(rem)                  Vertical breathing room — prefer this to a chain
                             of st.divider() calls.

The CSS uses CSS custom properties so that future palette tweaks happen in
one place (utils/colors.py + this file).
"""
from __future__ import annotations

from typing import Iterable, Literal, Mapping, Sequence

import streamlit as st

from utils.colors import COLORS

# ── Tokens (kept in sync with utils/colors.py) ─────────────────────────────────
_PALETTE = {
    "bg":            COLORS["near_white"],   # warm white app background
    "bg_card":       "#FFFFFF",
    "bg_subtle":     "#EDEBE5",              # cream
    "border":        "#E8E4DC",
    "text":          COLORS["dark"],         # warm charcoal
    "text_body":     "#5A5048",              # softened charcoal
    "text_muted":    "#6E6862",              # AA-passing muted (#8A8480 fails)
    "accent_olive":  "#5A7250",
    "accent_sage":   COLORS["mint"],         # success
    "accent_amber":  COLORS["yellow"],       # warning
    "accent_terra":  COLORS["orange"],       # caution / risk
    "accent_brick":  COLORS["red"],          # error / danger
    "accent_dust":   COLORS["blue"],         # info / neutral accent
}

CalloutKind = Literal["info", "success", "warning", "caution", "danger"]

_CALLOUT_TOKENS: dict[str, dict[str, str]] = {
    "info":    {"accent": _PALETTE["accent_dust"],  "icon": "i"},
    "success": {"accent": _PALETTE["accent_sage"],  "icon": "✓"},
    "warning": {"accent": _PALETTE["accent_amber"], "icon": "!"},
    "caution": {"accent": _PALETTE["accent_terra"], "icon": "!"},
    "danger":  {"accent": _PALETTE["accent_brick"], "icon": "!"},
}


# ── Base styles ────────────────────────────────────────────────────────────────
_BASE_STYLES = f"""
<style>
:root {{
    --afp-bg:           {_PALETTE["bg"]};
    --afp-bg-card:      {_PALETTE["bg_card"]};
    --afp-bg-subtle:    {_PALETTE["bg_subtle"]};
    --afp-border:       {_PALETTE["border"]};
    --afp-text:         {_PALETTE["text"]};
    --afp-text-body:    {_PALETTE["text_body"]};
    --afp-text-muted:   {_PALETTE["text_muted"]};
    --afp-accent-olive: {_PALETTE["accent_olive"]};
    --afp-radius-sm:    6px;
    --afp-radius-md:    10px;
    --afp-shadow-sm:    0 1px 4px rgba(44,37,32,0.06);
    --afp-space-1:      4px;
    --afp-space-2:      8px;
    --afp-space-3:      12px;
    --afp-space-4:      16px;
    --afp-space-5:      20px;
    --afp-space-6:      24px;
}}

.afp-section-header {{
    margin-top:    var(--afp-space-5);
    margin-bottom: var(--afp-space-3);
}}
.afp-section-header__title {{
    font-size:   18px;
    font-weight: 700;
    color:       var(--afp-text);
    line-height: 1.3;
    margin:      0;
}}
.afp-section-header__subtitle {{
    font-size:   13px;
    color:       var(--afp-text-muted);
    line-height: 1.55;
    margin:      var(--afp-space-1) 0 0 0;
    max-width:   72ch;
}}

.afp-callout {{
    background:      var(--afp-bg-card);
    border:          1px solid var(--afp-border);
    border-left:     4px solid var(--afp-text-muted);
    border-radius:   var(--afp-radius-md);
    padding:         var(--afp-space-4) var(--afp-space-5);
    margin:          var(--afp-space-3) 0;
    box-shadow:      var(--afp-shadow-sm);
    display:         flex;
    gap:             var(--afp-space-4);
    align-items:     flex-start;
}}
.afp-callout__icon {{
    flex:           0 0 28px;
    height:         28px;
    width:          28px;
    border-radius:  50%;
    display:        inline-flex;
    align-items:    center;
    justify-content: center;
    font-size:      14px;
    font-weight:    700;
    color:          var(--afp-bg-card);
    font-family:    system-ui, -apple-system, sans-serif;
}}
.afp-callout__title {{
    font-size:    14px;
    font-weight:  700;
    color:        var(--afp-text);
    margin:       0 0 var(--afp-space-1) 0;
    line-height:  1.3;
}}
.afp-callout__body {{
    font-size:    13px;
    color:        var(--afp-text-body);
    line-height:  1.6;
    margin:       0;
}}
.afp-callout__body p {{ margin: 0; }}

.afp-spacer-1 {{ height: var(--afp-space-3); }}
.afp-spacer-2 {{ height: var(--afp-space-5); }}
.afp-spacer-3 {{ height: var(--afp-space-6); }}
</style>
"""


def inject_base_styles() -> None:
    """Inject the shared <style> block. Safe to call multiple times per run."""
    if st.session_state.get("_afp_ui_styles_injected"):
        return
    st.markdown(_BASE_STYLES, unsafe_allow_html=True)
    st.session_state["_afp_ui_styles_injected"] = True


# ── Section header ─────────────────────────────────────────────────────────────
def section_header(title: str, subtitle: str | None = None) -> None:
    """Render a calm H2-style section header with an optional muted subtitle.

    Replaces the ad-hoc ``st.subheader(...) + st.caption(...)`` pairing so
    every page shares the same type scale, spacing, and muted-grey value.
    """
    inject_base_styles()
    sub_html = (
        f'<p class="afp-section-header__subtitle">{subtitle}</p>'
        if subtitle else ""
    )
    st.markdown(
        f'<div class="afp-section-header">'
        f'<h2 class="afp-section-header__title">{title}</h2>'
        f"{sub_html}"
        "</div>",
        unsafe_allow_html=True,
    )


# ── Metric row ─────────────────────────────────────────────────────────────────
MetricItem = Mapping[str, object]


def metric_row(items: Sequence[MetricItem | tuple]) -> None:
    """Render a row of KPI metrics with uniform spacing.

    Each item is either a ``(label, value)`` tuple or a dict with keys
    ``label``, ``value``, and optionally ``delta``, ``delta_color``, ``help``.
    """
    if not items:
        return
    cols = st.columns(len(items))
    for col, raw in zip(cols, items):
        if isinstance(raw, tuple):
            label, value = raw[0], raw[1]
            delta = raw[2] if len(raw) > 2 else None
            col.metric(label, value, delta=delta)
        else:
            col.metric(
                raw["label"],                            # type: ignore[index]
                raw["value"],                            # type: ignore[index]
                delta=raw.get("delta"),                  # type: ignore[union-attr]
                delta_color=raw.get("delta_color", "normal"),  # type: ignore[union-attr]
                help=raw.get("help"),                    # type: ignore[union-attr]
            )


# ── Callout ────────────────────────────────────────────────────────────────────
def callout(
    kind: CalloutKind,
    body: str,
    title: str | None = None,
) -> None:
    """A soft, palette-aware callout. Calmer than ``st.info`` / ``st.warning``.

    ``kind`` is one of ``info``, ``success``, ``warning``, ``caution``, ``danger``.
    ``body`` may contain Markdown-style ``**bold**`` and ``*italic*``; it is
    rendered inside a ``<p>`` so keep it short.
    """
    inject_base_styles()
    tokens = _CALLOUT_TOKENS.get(kind, _CALLOUT_TOKENS["info"])
    accent = tokens["accent"]
    icon = tokens["icon"]
    title_html = (
        f'<p class="afp-callout__title">{title}</p>' if title else ""
    )
    body_html = _markdown_lite(body)
    st.markdown(
        f'<div class="afp-callout" style="border-left-color:{accent};">'
        f'<span class="afp-callout__icon" style="background:{accent};">{icon}</span>'
        '<div>'
        f"{title_html}"
        f'<p class="afp-callout__body">{body_html}</p>'
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )


# ── Spacer ─────────────────────────────────────────────────────────────────────
def spacer(size: Literal[1, 2, 3] = 2) -> None:
    """Render vertical whitespace. Prefer this over decorative ``st.divider``.

    ``size`` maps to a small (12 px), medium (20 px), or large (24 px) gap.
    """
    inject_base_styles()
    st.markdown(f'<div class="afp-spacer-{size}"></div>', unsafe_allow_html=True)


# ── Internal helpers ───────────────────────────────────────────────────────────
def _markdown_lite(text: str) -> str:
    """Render a tiny subset of Markdown (**bold**, *italic*) safely.

    We avoid pulling in a full Markdown parser because the callout body is
    intentionally short. Streamlit's own markdown could be used, but it
    introduces its own wrapping <div>s that fight the callout layout.
    """
    import html
    import re

    escaped = html.escape(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"(?<!\*)\*(?!\*)([^*]+?)\*(?!\*)", r"<em>\1</em>", escaped)
    escaped = re.sub(r"`([^`]+?)`", r"<code>\1</code>", escaped)
    return escaped
