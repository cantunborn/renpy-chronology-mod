## =============================================================================
## CHRONOLOGY MOD — tl_theme.rpy
## Design tokens, styles, and hover gradients.
## =============================================================================

## =============================================================================
## Design tokens — all colours and sizes in one place
## =============================================================================

init python:
    # ── Contrast helpers ───────────────────────────────────────────────────
    def hex_to_rgb(hex_color):
        """Convert #rrggbb to (r,g,b) 0–255."""
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def relative_luminance(rgb):
        """Return relative luminance for contrast calculation (0–1)."""
        def channel(c):
            c = c / 255.0
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        r, g, b = rgb
        return 0.2126*channel(r) + 0.7152*channel(g) + 0.0722*channel(b)

    def contrast_ratio(rgb1, rgb2):
        """Contrast ratio as per WCAG (1–21)."""
        l1, l2 = relative_luminance(rgb1), relative_luminance(rgb2)
        if l1 < l2: l1, l2 = l2, l1
        return (l1 + 0.05) / (l2 + 0.05)

    def pick_accent_color(bg_colors, fallback="#e8c97e"):
        """Choose a readable accent color over given bg_colors."""
        candidates = [
            getattr(gui, "accent_color", None),
            getattr(gui, "choice_button_text_hover_color", None),
            getattr(gui, "hover_color", None),
            getattr(gui, "selected_color", None),
        ]

        for c in candidates:
            if not c:
                continue
            rgb = hex_to_rgb(c)
            if rgb == (255,255,255):  # skip pure white
                continue

            # check contrast against all backgrounds
            ok = all(contrast_ratio(rgb, hex_to_rgb(bg)) >= 3.0 for bg in bg_colors)
            if ok:
                return c

        return fallback  # nothing suitable found

    # ── Backgrounds to contrast against ──────────────────────────────────
    header_bg = "#000000bb"   # same as TL["header_bg"]
    footer_bg = "#00000055"   # same as TL["footer_bg"]
    accent_color = pick_accent_color([header_bg, footer_bg])

    # ── Timeline mod colors ──────────────────────────────────────────────
    TL = {
        ## Accent color
        "accent": accent_color,

        ## Overlay
        "overlay_bg"    : "#00000099",   ## 60% black base
        "noise_alpha"   : "#ffffff0c",   ## subtle noise tint

        ## Header
        "header_bg"     : header_bg,
        "header_text"   : "#f0ece4",
        "header_sub"    : "#9a9183",
        "new_dot"       : accent_color,     ## warm gold for new-content dot

        ## Card
        "card_bg"       : "#00000000",   ## transparent — no card bg
        "thumb_bg"      : "#0a0a0a",
        "divider"       : accent_color + "55",  ## semi-transparent

        ## Option rows
        "opt_chosen_fg" : "#f0ece4",     ## chosen this run — kept for arrow colour
        "opt_fg"        : "#f0ece4",     ## all option text — uniform, no muting
        "opt_new_dot"   : accent_color,     ## gold dot for unseen options

        ## Footer row
        "footer_bg"     : footer_bg,
        "footer_text"   : "#9a9183",
        "btn_bg"        : "#ffffff14",
        "btn_hover_bg"  : "#ffffff28",
        "hover_bg"      : accent_color + "30",  ## shared hover bg for all interactive rows/buttons
        "btn_text"      : "#c8c0b4",

        ## Modal
        "modal_bg"      : "#1a1814ee",
        "modal_header"  : "#f0ece4",
    }

    def _tl_make_hover_gradient(color_hex, center_w=100, edge_w=50, base_hex=None):
        ## Horizontal gradient: edge_w px fade-in, center_w solid, edge_w px fade-out.
        ## Frame(..., edge_w, 0) keeps the fade zones fixed and stretches the center
        ## to any button width.
        ## base_hex: if given, edges are pre-blended (Porter-Duff hover-over-base) so
        ## they exactly match the button's normal background instead of going transparent.
        import io as _io
        import pygame as _pg

        h      = color_hex.lstrip("#")
        hr, hg, hb = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        ha     = int(h[6:8], 16) if len(h) >= 8 else 255

        if base_hex is not None:
            bh = base_hex.lstrip("#")
            br, bg_, bb = int(bh[0:2], 16), int(bh[2:4], 16), int(bh[4:6], 16)
            ba = int(bh[6:8], 16) if len(bh) >= 8 else 255
        else:
            br = bg_ = bb = ba = 0

        def _pixel(t):
            if base_hex is None:
                return (hr, hg, hb, int(ha * t))
            ## Porter-Duff "over": hover (at effective alpha ha*t) over base
            eff_h = (ha / 255.0) * t
            eff_b = ba / 255.0
            out_f = eff_h + eff_b * (1.0 - eff_h)
            if out_f > 0:
                pr = int((hr * eff_h + br * eff_b * (1.0 - eff_h)) / out_f)
                pg = int((hg * eff_h + bg_ * eff_b * (1.0 - eff_h)) / out_f)
                pb = int((hb * eff_h + bb * eff_b * (1.0 - eff_h)) / out_f)
            else:
                pr = pg = pb = 0
            return (pr, pg, pb, int(out_f * 255))

        total_w = edge_w + center_w + edge_w
        surf    = renpy.display.pgrender.surface((total_w, 1), True)

        for x in range(edge_w):
            t = x / float(edge_w)
            t = t * t * (3.0 - 2.0 * t)
            surf.set_at((x, 0), _pixel(t))
        for x in range(edge_w, edge_w + center_w):
            surf.set_at((x, 0), _pixel(1.0))
        for x in range(edge_w + center_w, total_w):
            t = (total_w - 1 - x) / float(edge_w)
            t = t * t * (3.0 - 2.0 * t)
            surf.set_at((x, 0), _pixel(t))

        import tempfile as _tf, os as _os
        tmp = _tf.mktemp(suffix=".png")
        try:
            _pg.image.save(surf, tmp)
            with open(tmp, "rb") as _f:
                png_bytes = _f.read()
        finally:
            try: _os.unlink(tmp)
            except: pass

        return Frame(_tl_im_Data(png_bytes, "tl_hg.png"), edge_w, 0)

    _tl_hover_gradient      = _tl_make_hover_gradient(TL["hover_bg"])
    _tl_hover_gradient_wide = _tl_make_hover_gradient(TL["hover_bg"], center_w=60, edge_w=22, base_hex=TL["footer_bg"])


## =============================================================================
## Styles — fully explicit, no inheritance from game or mod style chains
## =============================================================================

init python:
    import os as _os

    default_font = None
    default_bold  = None

    try:
        default_font = getattr(gui, "text_font", None)
    except Exception:
        default_font = None

    try:
        default_bold = getattr(gui, "name_text_font", None) or getattr(gui, "interface_text_font", None)
    except Exception:
        default_bold = None

    if default_font:
        _tl_font_reg = default_font
    else:
        _tl_font_reg = "renpy-chronology-mod/fonts/Inter-Regular.ttf"

    if default_bold:
        _tl_font_bold = default_bold
    else:
        _tl_font_bold = "renpy-chronology-mod/fonts/Inter-Bold.ttf"

    _tl_mod_abs = _os.path.join(renpy.config.gamedir, "renpy-chronology-mod", "fonts")
    if not _tl_font_reg or not _tl_font_bold:
        if not _os.path.exists(_os.path.join(_tl_mod_abs, "Inter-Regular.ttf")):
            if _os.path.exists(_os.path.join(_tl_mod_abs, "InterVariable.ttf")):
                _tl_font_reg  = "renpy-chronology-mod/fonts/InterVariable.ttf"
                _tl_font_bold = "renpy-chronology-mod/fonts/InterVariable.ttf"
            else:
                _tl_font_reg  = "DejaVuSans.ttf"
                _tl_font_bold = "DejaVuSans-Bold.ttf"


style tl_base is text:
    font _tl_font_reg
    size TL_SIZE_BODY
    color "#f0ece4"
    italic False
    bold False
    underline False
    strikethrough False
    outlines []
    drop_shadow None
    kerning 0.0
    layout "tex"

style tl_base_bold is text:
    font _tl_font_bold
    size TL_SIZE_BODY
    color "#f0ece4"
    italic False
    bold False
    underline False
    strikethrough False
    outlines []
    drop_shadow None
    kerning 0.0

style tl_icon is text:
    font "DejaVuSans.ttf"
    size TL_SIZE_DOT
    color "#f0ece4"
    italic False
    bold False
    outlines []
    drop_shadow None

style tl_frame_base is _default:
    background None
    padding (0, 0, 0, 0)

init python:
    def _tl_noise_bg():
        return Solid(TL["noise_alpha"])