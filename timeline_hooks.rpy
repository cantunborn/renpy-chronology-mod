## =============================================================================
## CHRONOLOGY MOD — timeline_hooks.rpy
##
## Wraps two RenPy menu functions to record choices:
##
##   renpy.exports.menu  — called with raw 3-tuple (label, condition, value)
##                         items before any filtering. We capture the option
##                         list and thumbnail here.
##
##   renpy.store.menu    — called after exports.menu filters items to 2-tuples
##                         (label, value). On RenPy 8 with menu_actions=True,
##                         value is a ChoiceReturn object. We capture these for
##                         seen-checking and match rv back to a label after the
##                         player chooses.
##
## Guard pattern: _tl_wrapped attribute instead of __name__ assignment, because
## __name__ is read-only on functions in Python 2 (RenPy 7.5).
## =============================================================================

init -1 python:

    def _tl_record_before(items):
        global _tl_branch_id, _tl_node_count, _tl_history, _tl_context

        if not _tl_branch_id:
            _tl_branch_id  = _tl_new_branch_id()
            _tl_node_count = 0

        prompt      = ""
        valid_items = []
        for entry in items:
            label = entry[0]
            value = entry[2] if len(entry) > 2 else None
            if value is None:
                if not prompt:
                    prompt = label
            else:
                valid_items.append(label)

        if not valid_items:
            return None

        location = None
        ast_key  = None
        try:
            current = renpy.game.context().current
            if current is not None:
                location = current
                node_obj = renpy.game.script.namemap.get(current)
                if node_obj is not None:
                    ast_key = (node_obj.filename, node_obj.linenumber)
        except Exception as e:
            renpy.log("TL location lookup failed: {}".format(e))

        node = {
            "index"          : _tl_node_count,
            "prompt"         : prompt,
            "options"        : valid_items,
            "chosen_index"   : None,
            "thumb_bytes"    : _tl_capture_thumbnail(),
            "ast_key"        : ast_key,
            "_location"      : location,
            "_choice_returns": [None] * len(valid_items),
        }

        _tl_history.append(node)
        _tl_node_count += 1
        return node


    def _tl_record_after(node, chosen_label):
        global _tl_context

        if node is None:
            return

        for i, label in enumerate(node["options"]):
            if label == chosen_label:
                node["chosen_index"] = i
                _tl_context.append((node["prompt"], i))
                renpy.log("TL recorded: node={} option={}".format(node["index"], i))
                return

        renpy.log("TL NO MATCH: chosen_label={}".format(repr(chosen_label)))


    _tl_pending = [None]

    if not getattr(renpy.exports.menu, "_tl_wrapped", False):
        _tl_original_exports_menu = renpy.exports.menu

        def _tl_exports_wrapper(items, set=None, args=None, kwargs=None, item_arguments=None):
            _tl_pending[0] = _tl_record_before(items)
            return _tl_original_exports_menu(items, set, args, kwargs, item_arguments)

        _tl_exports_wrapper._tl_wrapped = True
        renpy.exports.menu = _tl_exports_wrapper
        renpy.log("TL: exports.menu wrapped")
    else:
        renpy.log("TL: exports.menu already wrapped")

    if not getattr(renpy.store.menu, "_tl_wrapped", False):
        _tl_original_store_menu = renpy.store.menu

        def _tl_store_wrapper(items):
            ## Capture ChoiceReturn objects (RenPy 8) before the choice is made.
            ## Align to node["options"] by label so index matches.
            node = _tl_pending[0]
            if node is not None:
                for i, opt_label in enumerate(node["options"]):
                    for label, value in items:
                        if label == opt_label and value is not None and hasattr(value, "get_chosen"):
                            node["_choice_returns"][i] = value
                            break

            rv = _tl_original_store_menu(items)

            node = _tl_pending[0]
            if node is not None and rv is not None:
                chosen_label = None
                for label, value in items:
                    if value is None:
                        continue
                    if value is rv or value == rv:
                        chosen_label = label
                        break
                    try:
                        if value.value == rv:
                            chosen_label = label
                            break
                    except AttributeError:
                        pass

                if chosen_label is not None:
                    _tl_record_after(node, chosen_label)
                else:
                    renpy.log("TL: no label match for rv={} type={}".format(
                        repr(rv)[:60], type(rv).__name__))

                _tl_pending[0] = None

            return rv

        _tl_store_wrapper._tl_wrapped = True
        renpy.store.menu = _tl_store_wrapper
        renpy.log("TL: store.menu wrapped (RenPy {}.{})".format(
            renpy.version_tuple[0], renpy.version_tuple[1]))
    else:
        renpy.log("TL: store.menu already wrapped")


## Run AST map build synchronously at init 0 (not in a thread — store writes
## from background threads are silently discarded in RenPy 8).
## Only meaningfully used on RenPy 7; RenPy 8 uses ChoiceReturn.get_chosen().

init 0 python:
    try:
        _tl_build_ast_map()
    except Exception as e:
        renpy.log("TL AST error: {}".format(e))
        store._tl_ast_ready = True
