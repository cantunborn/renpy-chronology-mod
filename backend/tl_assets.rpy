## =============================================================================
## CHRONOLOGY MOD — timeline_assets.rpy
## Asset/thumbnail resolution helpers.
## =============================================================================

init -2 python:

    TL_ASSET_THUMB_CACHE_MAX     = 500
    TL_ASSET_THUMB_CACHE_VERSION = 1
    TL_LOG_ASSET_THUMB_HITS      = False

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

    def _tl_capture_thumbnail():
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

    def _tl_normalize_img_name(value):
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

    def _tl_scene_stmt_img_name(stmt):
        """Return a normalized image name from a Scene/Show-like AST node."""
        _sp = getattr(stmt, "imspec", None)
        if _sp:
            _img = _tl_normalize_img_name(_sp)
            if _img:
                return _img
        for _attr in ("img", "image", "name"):
            _img = _tl_normalize_img_name(getattr(stmt, _attr, None))
            if _img:
                return _img
        try:
            _d = getattr(stmt, "__dict__", None) or {}
            for _attr, _val in _d.items():
                _img = _tl_normalize_img_name(_val)
                if _img:
                    _tl_log("TL scene img fallback attr: type={} attr={} img={}".format(
                        type(stmt).__name__, _attr, _img))
                    return _img
        except Exception:
            pass
        return None

    def _tl_stmt_ast_key(stmt):
        """Return a normalized `(file, line)` key for a live AST node when possible."""
        _file = getattr(stmt, "filename", None) or getattr(stmt, "file", None)
        _line = getattr(stmt, "linenumber", None) or getattr(stmt, "line", None)
        if _file and _line:
            return (_file, _line)
        return None

    def _tl_live_scene_entry_img_name(entry):
        """Return a normalized image name from a live scene-list entry when possible."""
        _name = getattr(entry, "name", None)
        if _name and tuple(_name) in renpy.display.image.images:
            return " ".join(_name)
        return None

    def _tl_img_name_is_movie(img_name):
        """Best-effort check for movie/webm-backed registered images."""
        if not img_name:
            return False
        _cache = persistent._tl_img_movie_cache or {}
        if img_name in _cache:
            return bool(_cache[img_name])
        try:
            _key = tuple(img_name.split())
            _disp = renpy.display.image.images.get(_key)
            if _disp is None:
                _cache[img_name] = False
                return False
            _s = repr(_disp)
            if "Movie" in _s or ".webm" in _s.lower():
                _cache[img_name] = True
                return True
            for _attr in ("filename", "files", "_files"):
                _v = getattr(_disp, _attr, None)
                if isinstance(_v, (tuple, list)):
                    if any(isinstance(_x, _tl_text_types) and _x.lower().endswith(".webm") for _x in _v):
                        _cache[img_name] = True
                        return True
                elif isinstance(_v, _tl_text_types) and _v.lower().endswith(".webm"):
                    _cache[img_name] = True
                    return True
        except Exception as e:
            _tl_log("TL img_name_is_movie failed for {}: {}".format(img_name, e))
            _cache[img_name] = False
            return False
        _cache[img_name] = False
        return False

    def _tl_asset_thumb_cache_key(img_name, width=None, height=None, fit_mode="cover"):
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

    def _tl_asset_thumb_display_id(img_name):
        """Return a stable id string for img_name-derived static thumbnails."""
        if not img_name:
            return "asset_thumb"
        return "tl_asset_{}".format(_tl_hashlib.md5(img_name.encode("utf-8")).hexdigest()[:12])

    def _tl_asset_thumb_display_cache_key(img_name, width=None, height=None, fit_mode="cover"):
        """Build a transient cache key for final asset-thumb displayables."""
        if not img_name:
            return None
        return (
            img_name,
            width or TL_THUMB_WIDTH,
            height or TL_THUMB_HEIGHT,
            fit_mode,
        )

    def _tl_is_supported_thumb_file(path):
        if not isinstance(path, _tl_text_types):
            return False
        _p = path.lower()
        return _p.endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp"))

    def _tl_resolve_asset_file(img_name):
        """Resolve a plain file-backed image path for a registered img_name when possible."""
        if not img_name:
            return None
        if img_name in _tl_asset_thumb_file_cache:
            return _tl_asset_thumb_file_cache[img_name]
        try:
            _root = renpy.display.image.images.get(tuple(img_name.split()))
        except Exception:
            _root = None
        if _root is None:
            _tl_asset_thumb_file_cache[img_name] = None
            return None

        _seen = set()

        def _walk(_obj):
            if _obj is None:
                return None
            _oid = _tl_builtin_id(_obj)
            if _oid in _seen:
                return None
            _seen.add(_oid)

            for _attr in ("filename",):
                _val = getattr(_obj, _attr, None)
                if _tl_is_supported_thumb_file(_val) and renpy.loadable(_val):
                    return _val

            try:
                _files = _obj.predict_files() if hasattr(_obj, "predict_files") else []
            except Exception:
                _files = []
            for _path in (_files or []):
                if _tl_is_supported_thumb_file(_path) and renpy.loadable(_path):
                    return _path

            for _attr in ("image", "child", "base", "mask"):
                _path = _walk(getattr(_obj, _attr, None))
                if _path:
                    return _path

            for _attr in ("images", "children"):
                _vals = getattr(_obj, _attr, None)
                if isinstance(_vals, (list, tuple)):
                    for _item in _vals:
                        _path = _walk(_item)
                        if _path:
                            return _path

            ## ATL animation: eval the first image expression from the raw ATL block.
            _atl = getattr(_obj, "atl", None)
            if _atl is not None:
                for _stmt in (getattr(_atl, "statements", None) or []):
                    for _expr_str, _ in (getattr(_stmt, "expressions", None) or []):
                        try:
                            _evaled = renpy.python.py_eval(_expr_str)
                        except Exception:
                            continue
                        if _tl_is_supported_thumb_file(_evaled) and renpy.loadable(_evaled):
                            return _evaled
                        _path = _walk(_evaled)
                        if _path:
                            return _path

            return None

        _path = _walk(_root)
        _tl_asset_thumb_file_cache[img_name] = _path
        return _path

    def _tl_render_asset_thumb_bytes(img_name, width=None, height=None, fit_mode="cover"):
        """Generate thumbnail bytes from a plain file-backed registered image."""
        if not img_name:
            return None
        _w = width or TL_THUMB_WIDTH
        _h = height or TL_THUMB_HEIGHT
        try:
            import tempfile as _tf
            import pygame as _pg
            _path = _tl_resolve_asset_file(img_name)
            if not _path:
                return None

            with renpy.loader.load(_path) as _f:
                _src = renpy.display.pgrender.load_image(_f, _path)

            _sw, _sh = _src.get_size()
            if not _sw or not _sh:
                return None

            if fit_mode == "cover":
                _scale = max(float(_w) / float(_sw), float(_h) / float(_sh))
            else:
                _scale = min(float(_w) / float(_sw), float(_h) / float(_sh))

            _tw = max(1, int(round(_sw * _scale)))
            _th = max(1, int(round(_sh * _scale)))

            try:
                renpy.display.render.blit_lock.acquire()
                _scaled = renpy.display.scale.smoothscale(_src, (_tw, _th))
            finally:
                renpy.display.render.blit_lock.release()

            _surf = renpy.display.pgrender.surface((_w, _h), True)
            if fit_mode == "cover":
                _sx = max(0, int(round((_tw - _w) / 2.0)))
                _sy = max(0, int(round((_th - _h) / 2.0)))
                _crop = _scaled.subsurface((_sx, _sy, min(_w, _tw - _sx), min(_h, _th - _sy)))
                _surf.blit(_crop, (0, 0))
            else:
                _dx = max(0, int(round((_w - _tw) / 2.0)))
                _dy = max(0, int(round((_h - _th) / 2.0)))
                _surf.blit(_scaled, (_dx, _dy))

            if _surf is None:
                return None
            _tmp = _tf.mktemp(suffix=".png")
            try:
                _pg.image.save(_surf, _tmp)
                with open(_tmp, "rb") as _f:
                    return _f.read()
            finally:
                try:
                    os.unlink(_tmp)
                except Exception:
                    pass
        except Exception as e:
            _tl_log("TL asset thumb render failed for {}: {}".format(img_name, e))
            return None

    def _tl_get_asset_thumb_bytes(img_name, generate=False, width=None, height=None, fit_mode="cover"):
        """Return cached static thumbnail bytes for an img_name, optionally generating them."""
        _key = _tl_asset_thumb_cache_key(img_name, width, height, fit_mode)
        if not _key:
            return None
        _cache = getattr(renpy.game, "_tl_asset_thumb_cache", {})
        _bytes = _cache.get(_key)
        if _bytes is not None:
            if TL_LOG_ASSET_THUMB_HITS:
                _tl_log("TL asset thumb hit: img_name={}".format(img_name))
            return _bytes
        if not generate or _tl_img_name_is_movie(img_name):
            return None
        _bytes = _tl_render_asset_thumb_bytes(img_name, width, height, fit_mode)
        if _bytes:
            _cache[_key] = _bytes
            while len(_cache) > TL_ASSET_THUMB_CACHE_MAX:
                _cache.pop(next(iter(_cache)))
            _tl_log("TL asset thumb generated: img_name={}".format(img_name))
        return _bytes

    def _tl_resolve_live_menu_img_name():
        """
        Resolve the best currently displayed gameplay image for a menu.
        Prefer a background-tagged image on master, then fall back to the
        topmost registered image on master.
        """
        try:
            _master = renpy.game.context().scene_lists.layers.get("master", []) or []
        except Exception as e:
            _tl_log("TL live img_name scene_lists failed: {}".format(e))
            return None

        _fallback = None
        for _entry in reversed(_master):
            _img_name = _tl_live_scene_entry_img_name(_entry)
            if not _img_name:
                continue
            if _fallback is None:
                _fallback = _img_name
            if getattr(_entry, "tag", None) == "bg":
                return _img_name
        return _fallback

    def _tl_thumb_displayable(thumb_bytes, index):
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

    def _tl_node_thumb(node):
        """Return thumbnail bytes for a node: from the node itself or the cache."""
        b = node.get("thumb_bytes")
        if b:
            return b
        key = str(node["ast_key"]) if node.get("ast_key") else None
        _tc = getattr(renpy.game, "_tl_thumb_cache", {})
        return _tc.get(key) if key else None

    def _tl_img_thumb_displayable(img_name, width, height, fit_mode="cover"):
        """Return a cached displayable for an asset-backed timeline thumbnail."""
        _cache_key = _tl_asset_thumb_display_cache_key(img_name, width, height, fit_mode)
        if _cache_key and _cache_key in _tl_asset_thumb_displayable_cache:
            return _tl_asset_thumb_displayable_cache[_cache_key]
        _asset_thumb = _tl_get_asset_thumb_bytes(
            img_name,
            generate=True,
            width=TL_THUMB_WIDTH,
            height=TL_THUMB_HEIGHT,
            fit_mode="cover",
        )
        if _asset_thumb:
            _base = _tl_thumb_displayable(_asset_thumb, _tl_asset_thumb_display_id(img_name))
        elif _tl_resolve_asset_file(img_name):
            ## Safe fallback for plain file-backed images when thumb generation misses.
            _base = img_name
        else:
            ## Dynamic images (for example ConditionSwitch / composites) are not safe
            ## to render directly inside the timeline screen.
            return None
        _disp = Transform(
            _base,
            xsize=width,
            ysize=height,
            fit=fit_mode,
            xalign=0.5,
            yalign=0.5,
        )
        if _cache_key:
            _tl_asset_thumb_displayable_cache[_cache_key] = _disp
        return _disp

    def _tl_clear_thumb_cache():
        renpy.game._tl_thumb_cache      = {}
        renpy.game._tl_asset_thumb_cache = {}
        _tl_asset_thumb_displayable_cache.clear()
        _tl_asset_thumb_file_cache.clear()
        renpy.notify("Chronology: thumbnail cache cleared.")

    def _tl_build_menu_scene_index(nodes):
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
        _new_entries = [0]

        def _visitor(_node, _last_img, _label=None):
            _nt = type(_node).__name__
            if _nt in ("Scene", "Show"):
                _img = _tl_scene_stmt_img_name(_node)
                if _img:
                    return _img
            elif _nt == "Menu":
                _mk = _tl_menu_site_key(_node.filename, _node.linenumber)
                if _mk and _mk not in persistent._tl_menu_scene_map:
                    if _last_img:
                        persistent._tl_menu_scene_map[_mk] = _last_img
                        _new_entries[0] += 1
                    else:
                        _tl_log("TL ast-walk miss: menu=({},{}) last_img=None".format(
                            _node.filename, _node.linenumber))
            return _last_img

        _tl_walk_ast_blocks(nodes, _visitor, initial_state=None)
        if _new_entries[0]:
            _tl_log("TL menu_scene_map: {} new entries cached".format(_new_entries[0]))

