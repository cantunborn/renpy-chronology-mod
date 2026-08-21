## =============================================================================
## CHRONOLOGY MOD — tl_assets_ren.py
## Asset/thumbnail resolution helpers.
## =============================================================================

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Optional, Any
    import os
    import hashlib as _tl_hashlib
    import renpy
    from renpy import persistent
    from renpy.display.transform import Transform  # type-check-only; injected into store namespace at runtime
    from tl_menu_location_ren import _tl_menu_site_key  # type-check-only; injected into store namespace at runtime
    from tl_ast_utils_ren import _tl_walk_ast_blocks  # type-check-only; injected into store namespace at runtime
    from timeline_init_ren import _tl_log, TL_THUMB_WIDTH, TL_THUMB_HEIGHT, TL_DEBUG_ASSET, _TL_MIN, _TL_MAX, _tl_builtin_id  # type-check-only; injected into store namespace at runtime

"""renpy
init -2 python:
"""

TL_ASSET_THUMB_CACHE_MAX     = 500
TL_ASSET_THUMB_CACHE_VERSION = 1

_tl_asset_thumb_displayable_cache = {}
_tl_asset_thumb_file_cache        = {}

_tl_im_Data = renpy.display.im.Data   ## canonical path; works RenPy 7 + 8, no deprecation warning

try:
    import base64 as _tl_base64
    _TL_LOCK_B64   = b"iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAD70lEQVR42u1bS2sUQRD+arIbH4lGAyqCekjAcxAkFxFFf4P/Qa85eAnkGLznlKPgWXMPKmJuIXjz5ANRRGJMgi9idubzsFXSDPPoyc4ku7ELhp1Hd1V9X1dV92zvChoQkhEAEZFYr8cAXANwA8AVABMAxgEc1y6/AHwD8BbAGoDnAF6KyLb2HwJAEUnQ76LO2vkUyQWS71hd3mnfqSzd/QhczEGSkyQfkYwdQAnJjt5L9HCfJfqsk3oWq65JI4Gk9Bv4yDm/R3LLAbCbAuQrifY12SJ5L8tmX4AneYTkwxTwusTV9ZDkkb4gwQF/kuRyjyNeJSKWSZ48UBI05yOSx0i+UMf+VABj+e7WBR8xGy/UdrTvNSFV8JY8wdsIxgVtYs8IMltPDqQwOuDnPMF3UtfrJNc0lJf1fL2kTx4Jc/s6RTrgpz1z3oD8ILlI8jbJ8Qy94/psUduWkeDWhOl9I0FzrkVy1cNJe/aY5OUcXVHG/cvax1f/qvoUNQ2+pZ93SpxLnGezbv+8fLW6Yjb03qxjJykh4Y7rY9OVfzUFMs+pGadIRRWjzFJtpoRsI2e10RnBceiqM8pF4Be1fXsvTinZbT1f9Ig4krzaWC1wwn++YKVn8/l7kiO9Tk9OWoyoziRnGjVf5qumQZWiEevndf3MAka9Py8iP/WVmHslQPuK6ppX3Vn6JOVbXHvuO1PVZk4K2PUGydM6elJT3RHVuVFie9OmWF/bvhFgyi4COJUTAfZlxYqIbAKIehn9VBREqnMlZSvt3yn1MS9CeybgfEGIGdhXyn6d1dii6VXKVlaKnm+SgFGPtp/qGPmcSPjk0XS0CQJMjhaMgMnvBtdiRbqZ8hFNEODDKhskgDX5uGcCDp0EAgIB/7l4r5mrrOpsHVDjm5nswX7vBKiiIZuHSfpUYWrbuK71gOmqaN9eigr9aBWB144dXYu3PCOmpW3bJDt1RSrJ3Yr2/wF3sPjNmdaB5DkA9wHc1BXWGIAzzltf1pvgOoDvWl/qWhOIrv9PeNrfBvADwDMAD0TkSx4JWV9NmeOXADxFdyd3kOUNgFsAPuirdVI6CyhTCwp+R9lPPEeUTvu6j6r2dwBMAljwSgGSkYgkJC+gu1c/pG1kQEefesQAJkTko2EsWwecBdAecPBw/G8rJu+FkODwiYSVYCAgEBAICAQEAgIBgYBAQCAgEBAICAQEAgIBgYBAQCAgEBAICAQEAgIBgYBAQIZ8BWB7+xxgfOZ7RzEVE6AboxG6W8kr6G4n7Q4wAbuKYQXAh/TGaFkK3AXwGcDwABMwrBjueqeAMiQi8hrdX4YsofuLCw5Y6G+r7zcVi2T9/f4vvIKpDuXummUAAAAASUVORK5CYII="
    _TL_UNLOCK_B64 = b"iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAEH0lEQVR42u2bTYsUVxSGn9M9JkYmCTIxS0EFITALMRAJEzAYRBeCP8RtVllkEQLBVfBPqIv8A4MEUbKQGTei5HtlhFFwoo6o01VvFn0uXIr66K6eru7We6Domq77cc5zzr333Lo9xpRE0pKZDfy+D6wBp4DPgSPAAWCfF38BPAL+An4FrgO3zCwrtjX3Iqknyfx+RdLXku5ofLnjdVe8LZPUm3fj+9H9BUkPC0YNJGWScr+ChL8zLxPLQ0kXyvqYN+OX/POgpGuRATtu2LiSed0g1yQdjPuaR+NPSHoQGZ5rcskjEA8knZgrCCEkJZ2U9CwyfhTD8pLhUCWhzWeSTs7FcAiTkqRjkraicd7kzbIygxGiJtTbknQs1qGt2ATGm9f/EFgHDgEZUOYVAXnhWQY89/vlkme9Cv1CH/8AnwL/ATIzzSr0rzaEfezRfyVdknRO0lFJB/w66t9d8jJldcuGw9WZDIXI+LMNxmdR6H4f1vSGtle87KDQRhWEs51D8GSnJ2nDvTSoMf6xpK/iFUNSPyRMIcHx75aicqe8bhWEgfe9EfTp2vtnaia9kNRsSTru5feEDLFpbpG0x++PextZxXAIfZ/pLAoiAJcLa3SZ988H41v0EyCcr4mCsGpc7gRAlOMvS9qsmKiCV660Nb4EwpWKaAt9b0pajnWctvfXambpEBWrHs79SfrzNlZrcoTw3VqbKBh34gh0V6M1ubhGG7BuZncBC1vaVknKsK55W+vedlmfsU42TQBBjlQ5zT9vTNh+mY43Cn2MqtNUAHzU8PzPKYzAPxqer3QBINB/r2GIPJ0CgOc13s89na6LkFJpu6VsmmjyXTQ8tPWbA+4Dgwh27nb83uUc0JmYWS6pZ2YbwA9u4JKD6APvALeAH30JzLqIgFlAMDP7RtJPwGEHYcAT4LqZZV5GbxwAh6AoEjbKkrQ2W+KFARAPh8LQFZC3fR+wUAAChN2cZHu85ZIAJABvuYw7CdqI++1Qzqa6P69ZMncVQHjfFp32NnUwcCV2ZuHVSN98YgCefOR+/77Xebeh2geS9nvZro+1X5vZdlH3phccVcabZ2CrwHfAZ74TXPYcvEq2gdezcD7D3xrcBr41s7tNGaI1hJGAT4CbwP4Fm9+eAF8A94ejoTwSevVziQm46Ma/ciAa0ROzvF65zhfdBhsrAqLQ3wf8DXzcZq89QwlO2gQOm9mLqqHQlAfs9bFuLJ6Y6753kkRILL4oZYIJQAKQACQACUACkAAkAAlAApAAJAAJQAKQACQACUACkAAkACMCsDfARpsEwEuGZ3yL+HpcrvvLsQH4qVDfzMJBozGjo+6WsuM63/ZToX7VAemoh6O/MPxv70WSR8CXtD0c9QpmZveA08DPDI+9Nedhv+26nnbdre43Av8DSMhGwPTI6CcAAAAASUVORK5CYII="
    _tl_lock_displayable   = _tl_im_Data(_tl_base64.b64decode(_TL_LOCK_B64),   "tl_icon_lock.png")
    _tl_unlock_displayable = _tl_im_Data(_tl_base64.b64decode(_TL_UNLOCK_B64), "tl_icon_unlock.png")
except Exception:
    _tl_lock_displayable   = None
    _tl_unlock_displayable = None

try:
    _tl_text_types = (basestring,)
except NameError:
    _tl_text_types = (str,)

def _tl_capture_thumbnail():  # type: () -> Optional[bytes]
    ## screenshot_to_bytes was added in RenPy 7.5. Older versions lack a
    ## supported API for in-memory screenshot capture — the internal fallback
    ## (draw.screenshot) produces black images on 7.4.x due to a flip-ordering
    ## bug in the GL2 renderer. Thumbnails are silently skipped on < 7.5;
    ## the rest of the mod (choice tracking, dots, jump-back) still works.
    if not hasattr(renpy, "screenshot_to_bytes"):
        return None
    try:
        return renpy.screenshot_to_bytes((TL_THUMB_WIDTH, TL_THUMB_HEIGHT))
    except Exception as e:
        _tl_log("TL screenshot failed: {}".format(e))
        return None

def _tl_normalize_img_name(value):  # type: (Any) -> Optional[str]
    """Normalize tuple/list/string image identifiers to the timeline string form."""
    if not value:
        return None
    if isinstance(value, (tuple, list)):
        if value and isinstance(value[0], (tuple, list)):
            value = value[0]
        if value and all(isinstance(x, _tl_text_types) for x in value):
            return " ".join(value)
        return None
    if isinstance(value, _tl_text_types):
        return value
    return None

def _tl_scene_stmt_img_name(stmt):  # type: (Any) -> Optional[str]
    """Return a normalized image name from a Scene/Show-like AST node."""
    imspec = getattr(stmt, "imspec", None)
    if imspec:
        img = _tl_normalize_img_name(imspec)
        if img:
            return img
    for attr in ("img", "image", "name"):
        img = _tl_normalize_img_name(getattr(stmt, attr, None))
        if img:
            return img
    try:
        attrs = getattr(stmt, "__dict__", None) or {}
        for attr, val in attrs.items():
            img = _tl_normalize_img_name(val)
            if img:
                if TL_DEBUG_ASSET:
                    _tl_log("TL scene img fallback attr: type={} attr={} img={}".format(
                        type(stmt).__name__, attr, img))
                return img
    except Exception as e:
        _tl_log("TL scene_stmt_img_name failed: {}".format(e))
    return None

def _tl_stmt_ast_key(stmt):  # type: (Any) -> Optional[tuple]
    """Return a normalized `(file, line)` key for a live AST node when possible."""
    fname = getattr(stmt, "filename", None) or getattr(stmt, "file", None)
    lineno = getattr(stmt, "linenumber", None) or getattr(stmt, "line", None)
    if fname and lineno:
        return (fname, lineno)
    return None

def _tl_live_scene_entry_img_name(entry):  # type: (Any) -> Optional[str]
    """Return a normalized image name from a live scene-list entry when possible."""
    name = getattr(entry, "name", None)
    if name and tuple(name) in renpy.display.image.images:
        return " ".join(name)
    return None

def _tl_img_name_is_movie(img_name):  # type: (Optional[str]) -> bool
    """Best-effort check for movie/webm-backed registered images."""
    if not img_name:
        return False
    cache = persistent._tl_img_movie_cache or {}
    if img_name in cache:
        return bool(cache[img_name])
    try:
        img_key = tuple(img_name.split())
        disp = renpy.display.image.images.get(img_key)
        if disp is None:
            cache[img_name] = False
            return False
        disp_repr = repr(disp)
        if "Movie" in disp_repr or ".webm" in disp_repr.lower():
            cache[img_name] = True
            return True
        for attr in ("filename", "files", "_files"):
            val = getattr(disp, attr, None)
            if isinstance(val, (tuple, list)):
                if any(isinstance(item, _tl_text_types) and item.lower().endswith(".webm") for item in val):
                    cache[img_name] = True
                    return True
            elif isinstance(val, _tl_text_types) and val.lower().endswith(".webm"):
                cache[img_name] = True
                return True
    except Exception as e:
        _tl_log("TL img_name_is_movie failed for {}: {}".format(img_name, e))
        cache[img_name] = False
        return False
    cache[img_name] = False
    return False

def _tl_asset_thumb_cache_key(img_name, width=None, height=None, fit_mode="cover"):  # type: (Optional[str], Optional[int], Optional[int], str) -> Optional[tuple]
    """Build a persistent cache key for a static thumbnail derived from an asset image."""
    if not img_name:
        return None
    return (
        TL_ASSET_THUMB_CACHE_VERSION,
        img_name,
        width or TL_THUMB_WIDTH,
        height or TL_THUMB_HEIGHT,
        fit_mode,
    )

def _tl_asset_thumb_display_id(img_name):  # type: (Optional[str]) -> str
    """Return a stable id string for img_name-derived static thumbnails."""
    if not img_name:
        return "asset_thumb"
    return "tl_asset_{}".format(_tl_hashlib.md5(img_name.encode("utf-8")).hexdigest()[:12])

def _tl_asset_thumb_display_cache_key(img_name, width=None, height=None, fit_mode="cover"):  # type: (Optional[str], Optional[int], Optional[int], str) -> Optional[tuple]
    """Build a transient cache key for final asset-thumb displayables."""
    if not img_name:
        return None
    return (
        img_name,
        width or TL_THUMB_WIDTH,
        height or TL_THUMB_HEIGHT,
        fit_mode,
    )

def _tl_is_supported_thumb_file(path):  # type: (Any) -> bool
    if not isinstance(path, _tl_text_types):
        return False
    path_lower = path.lower()
    return path_lower.endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp"))

def _tl_resolve_asset_file(img_name):  # type: (Optional[str]) -> Optional[str]
    """Resolve a plain file-backed image path for a registered img_name when possible."""
    if not img_name:
        return None
    if img_name in _tl_asset_thumb_file_cache:
        return _tl_asset_thumb_file_cache[img_name]
    try:
        root = renpy.display.image.images.get(tuple(img_name.split()))
    except Exception as e:
        _tl_log("TL resolve_asset_file root failed: {}".format(e))
        root = None
    if root is None:
        _tl_asset_thumb_file_cache[img_name] = None
        return None

    seen = set()

    def _walk(obj):
        if obj is None:
            return None
        obj_id = _tl_builtin_id(obj)
        if obj_id in seen:
            return None
        seen.add(obj_id)

        for attr in ("filename",):
            val = getattr(obj, attr, None)
            if _tl_is_supported_thumb_file(val) and renpy.loadable(val):
                return val

        try:
            files = obj.predict_files() if hasattr(obj, "predict_files") else []
        except Exception as e:
            _tl_log("TL resolve_asset_file walk failed: {}".format(e))
            files = []
        for path in (files or []):
            if _tl_is_supported_thumb_file(path) and renpy.loadable(path):
                return path

        for attr in ("image", "child", "base", "mask"):
            path = _walk(getattr(obj, attr, None))
            if path:
                return path

        for attr in ("images", "children"):
            vals = getattr(obj, attr, None)
            if isinstance(vals, (list, tuple)):
                for item in vals:
                    path = _walk(item)
                    if path:
                        return path

        ## ATL animation: eval the first image expression from the raw ATL block.
        atl = getattr(obj, "atl", None)
        if atl is not None:
            for stmt in (getattr(atl, "statements", None) or []):
                for expr_str, _ in (getattr(stmt, "expressions", None) or []):
                    try:
                        evaled = renpy.python.py_eval(expr_str)
                    except Exception:
                        continue
                    if _tl_is_supported_thumb_file(evaled) and renpy.loadable(evaled):
                        return evaled
                    path = _walk(evaled)
                    if path:
                        return path

        return None

    result = _walk(root)
    _tl_asset_thumb_file_cache[img_name] = result
    return result

def _tl_render_asset_thumb_bytes(img_name, width=None, height=None, fit_mode="cover"):  # type: (Optional[str], Optional[int], Optional[int], str) -> Optional[bytes]
    """Generate thumbnail bytes from a plain file-backed registered image."""
    if not img_name:
        return None
    thumb_w = width or TL_THUMB_WIDTH
    thumb_h = height or TL_THUMB_HEIGHT
    try:
        import tempfile
        import pygame
        asset_path = _tl_resolve_asset_file(img_name)
        if not asset_path:
            return None

        with renpy.loader.load(asset_path) as f:
            src_surf = renpy.display.pgrender.load_image(f, asset_path)

        src_w, src_h = src_surf.get_size()
        if not src_w or not src_h:
            return None

        if fit_mode == "cover":
            scale = _TL_MAX(float(thumb_w) / float(src_w), float(thumb_h) / float(src_h))
        else:
            scale = _TL_MIN(float(thumb_w) / float(src_w), float(thumb_h) / float(src_h))

        scaled_w = _TL_MAX(1, int(round(src_w * scale)))
        scaled_h = _TL_MAX(1, int(round(src_h * scale)))

        try:
            renpy.display.render.blit_lock.acquire()
            scaled = renpy.display.scale.smoothscale(src_surf, (scaled_w, scaled_h))
        finally:
            renpy.display.render.blit_lock.release()

        surf = renpy.display.pgrender.surface((thumb_w, thumb_h), True)
        if fit_mode == "cover":
            crop_x = _TL_MAX(0, int(round((scaled_w - thumb_w) / 2.0)))
            crop_y = _TL_MAX(0, int(round((scaled_h - thumb_h) / 2.0)))
            crop = scaled.subsurface((crop_x, crop_y, _TL_MIN(thumb_w, scaled_w - crop_x), _TL_MIN(thumb_h, scaled_h - crop_y)))
            surf.blit(crop, (0, 0))
        else:
            dst_x = _TL_MAX(0, int(round((thumb_w - scaled_w) / 2.0)))
            dst_y = _TL_MAX(0, int(round((thumb_h - scaled_h) / 2.0)))
            surf.blit(scaled, (dst_x, dst_y))

        if surf is None:
            return None
        tmp_path = tempfile.mktemp(suffix=".png")
        try:
            pygame.image.save(surf, tmp_path)
            with open(tmp_path, "rb") as f:
                return f.read()
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
    except Exception as e:
        _tl_log("TL asset thumb render failed for {}: {}".format(img_name, e))
        return None

def _tl_get_asset_thumb_bytes(img_name, generate=False, width=None, height=None, fit_mode="cover"):  # type: (Optional[str], bool, Optional[int], Optional[int], str) -> Optional[bytes]
    """Return cached static thumbnail bytes for an img_name, optionally generating them."""
    cache_key = _tl_asset_thumb_cache_key(img_name, width, height, fit_mode)
    if not cache_key:
        return None
    cache = getattr(renpy.game, "_tl_asset_thumb_cache", {})
    thumb_bytes = cache.get(cache_key)
    if thumb_bytes is not None:
        if TL_DEBUG_ASSET:
            _tl_log("TL asset thumb hit: img_name={}".format(img_name))
        return thumb_bytes
    if not generate or _tl_img_name_is_movie(img_name):
        return None
    thumb_bytes = _tl_render_asset_thumb_bytes(img_name, width, height, fit_mode)
    if thumb_bytes:
        cache[cache_key] = thumb_bytes
        persistent._tl_asset_thumb_dirty = True
        if TL_DEBUG_ASSET:
            _tl_log("TL asset thumb generated: img_name={}".format(img_name))
    return thumb_bytes

def _tl_resolve_live_menu_img_name():  # type: () -> Optional[str]
    """
    Resolve the best currently displayed gameplay image for a menu.
    Prefer a background-tagged image on master, then fall back to the
    topmost registered image on master.
    """
    try:
        master = renpy.game.context().scene_lists.layers.get("master", []) or []
    except Exception as e:
        _tl_log("TL live img_name scene_lists failed: {}".format(e))
        return None

    fallback = None
    for entry in reversed(master):
        img_name = _tl_live_scene_entry_img_name(entry)
        if not img_name:
            continue
        if fallback is None:
            fallback = img_name
        if getattr(entry, "tag", None) == "bg":
            return img_name
    return fallback

def _tl_thumb_displayable(thumb_bytes, index):  # type: (bytes, Any) -> Optional[Any]
    try:
        ## Detect image format from magic bytes so im.Data decodes correctly
        ## regardless of what screenshot_to_bytes returns (JPEG on older RenPy,
        ## PNG or WebP on newer).
        if thumb_bytes[:4] == b"RIFF" and thumb_bytes[8:12] == b"WEBP":
            ext = "webp"
        elif thumb_bytes[:2] == b"\xff\xd8":
            ext = "jpg"
        else:
            ext = "png"
        return _tl_im_Data(thumb_bytes, "tl_t_{}.{}".format(index, ext))
    except Exception as e:
        _tl_log("TL thumb displayable failed: {}".format(e))
        return None

def _tl_node_thumb(node):  # type: (dict) -> Optional[bytes]
    """Return thumbnail bytes for a node: from the node itself or the cache."""
    b = node.get("thumb_bytes")
    if b:
        return b
    key = str(node["ast_key"]) if node.get("ast_key") else None
    thumb_cache = getattr(renpy.game, "_tl_thumb_cache", {})
    return thumb_cache.get(key) if key else None

def _tl_img_thumb_displayable(img_name, width, height, fit_mode="cover"):  # type: (Optional[str], int, int, str) -> Optional[Any]
    """Return a cached displayable for an asset-backed timeline thumbnail."""
    cache_key = _tl_asset_thumb_display_cache_key(img_name, width, height, fit_mode)
    if cache_key and cache_key in _tl_asset_thumb_displayable_cache:
        return _tl_asset_thumb_displayable_cache[cache_key]
    asset_thumb = _tl_get_asset_thumb_bytes(
        img_name,
        generate=True,
        width=TL_THUMB_WIDTH,
        height=TL_THUMB_HEIGHT,
        fit_mode="cover",
    )
    if asset_thumb:
        base = _tl_thumb_displayable(asset_thumb, _tl_asset_thumb_display_id(img_name))
    elif _tl_resolve_asset_file(img_name):
        ## Safe fallback for plain file-backed images when thumb generation misses.
        base = img_name
    else:
        ## Dynamic images (for example ConditionSwitch / composites) are not safe
        ## to render directly inside the timeline screen.
        return None
    disp = Transform(
        base,
        xsize=width,
        ysize=height,
        fit=fit_mode,
        xalign=0.5,
        yalign=0.5,
    )
    if cache_key:
        _tl_asset_thumb_displayable_cache[cache_key] = disp
    return disp

def _tl_clear_thumb_cache():  # type: () -> None
    renpy.game._tl_thumb_cache      = {}
    renpy.game._tl_asset_thumb_cache = {}
    _tl_asset_thumb_displayable_cache.clear()
    _tl_asset_thumb_file_cache.clear()
    renpy.notify("Chronology: thumbnail cache cleared.")

def _tl_build_menu_scene_index(nodes):  # type: (list) -> None
    """
    Walk all Label blocks and populate persistent._tl_menu_scene_map with
    the scene image showing just before each menu. Backfill only — existing
    entries (runtime-captured) are not overwritten.

    Uses _tl_walk_ast_blocks with last_img as state. Scene/Show nodes update
    state; Menu nodes record the current state for their site key. Jumps are
    not followed — gaps are covered by runtime capture and screenshot fallback.
    """
    if persistent._tl_menu_scene_map is None:
        persistent._tl_menu_scene_map = {}
    new_entries = [0]

    def visitor(node, last_img, _label=None):
        node_type = type(node).__name__
        if node_type in ("Scene", "Show"):
            img = _tl_scene_stmt_img_name(node)
            if img:
                return img
        elif node_type == "Menu":
            menu_key = _tl_menu_site_key(node.filename, node.linenumber)
            if menu_key and menu_key not in persistent._tl_menu_scene_map:
                if last_img:
                    persistent._tl_menu_scene_map[menu_key] = last_img
                    new_entries[0] += 1
                else:
                    if TL_DEBUG_ASSET:
                        _tl_log("TL ast-walk miss: menu=({},{}) last_img=None".format(
                            node.filename, node.linenumber))
        return last_img

    _tl_walk_ast_blocks(nodes, visitor, initial_state=None)
    if new_entries[0] and TL_DEBUG_ASSET:
        _tl_log("TL menu_scene_map: {} new entries cached".format(new_entries[0]))