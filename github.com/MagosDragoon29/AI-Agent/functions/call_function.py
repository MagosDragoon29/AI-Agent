# functions/call_function.py

import os
import config
from google.genai import types

# Import tools directly from modules (avoid circular imports)
from .get_files_info import get_files_info
from .get_file_content import get_file_content
from .run_python_file import run_python_file
from .write_file import write_file
from .search_code import search_code

FUNCTION_MAP = {
    "get_files_info": get_files_info,
    "get_file_content": get_file_content,
    "run_python_file": run_python_file,
    "write_file": write_file,
    "search_code": search_code,
}

# Cache last search results to resolve basenames in follow-up calls
_LAST_SEARCH_RESULTS: list[dict] = []

def _tool_error(function_name: str, message: str) -> types.Content:
    return types.Content(
        role="tool",
        parts=[types.Part.from_function_response(name=function_name, response={"error": message})],
    )

def _ensure_list(x):
    if x is None:
        return None
    return x if isinstance(x, list) else [x]

def _lower_exts(xs):
    if xs is None:
        return None
    return [e.lower() for e in xs]

def _apply_arg_aliases(func_name: str, func_args: dict) -> dict:
    aliases = {}

    if func_name == "run_python_file":
        if "file_path" not in func_args:
            if "filename" in func_args:
                aliases["file_path"] = func_args.pop("filename")
            elif "path" in func_args:
                aliases["file_path"] = func_args.pop("path")

    elif func_name == "get_file_content":
        if "file_path" not in func_args and "path" in func_args:
            aliases["file_path"] = func_args.pop("path")

    elif func_name == "write_file":
        if "file_path" not in func_args and "path" in func_args:
            aliases["file_path"] = func_args.pop("path")
        if "contents" not in func_args and "content" in func_args:
            aliases["contents"] = func_args.pop("content")

    elif func_name == "search_code":
        for k in ("directory", "dir", "root_directory"):
            if "root" not in func_args and k in func_args:
                aliases["root"] = func_args.pop(k)
        if "name_globs" in func_args:
            func_args["name_globs"] = _ensure_list(func_args["name_globs"])
        if "extensions" in func_args:
            func_args["extensions"] = _lower_exts(_ensure_list(func_args["extensions"]))
        if "content_query" not in func_args:
            if "needle" in func_args:
                aliases["content_query"] = func_args.pop("needle")
            elif "query" in func_args:
                aliases["content_query"] = func_args.pop("query")
        if "case_sensitive" not in func_args and "case" in func_args:
            aliases["case_sensitive"] = bool(func_args.pop("case"))
        if "context_lines" not in func_args and "preview_lines" in func_args:
            aliases["context_lines"] = int(func_args.pop("preview_lines"))

    func_args.update(aliases)
    return func_args

def _resolve_path_if_needed(wd: str, path: str | None, verbose: bool) -> str | None:
    """If the model passed a basename, try to resolve to a unique path within WD."""
    if not path:
        return path

    # Already valid?
    if os.path.exists(os.path.join(wd, path)):
        return path

    base = os.path.basename(path)

    # 1) Try last search results (exact basename matches only)
    candidates = []
    for r in _LAST_SEARCH_RESULTS:
        rp = r.get("path")
        if isinstance(rp, str) and os.path.basename(rp) == base:
            if os.path.exists(os.path.join(wd, rp)):
                candidates.append(rp)
    if len(candidates) == 1:
        if verbose:
            print(f"[resolver] Using search hit for '{path}': {candidates[0]}")
        return candidates[0]

    # 2) Scan WD for a unique basename match
    found = []
    for dirpath, _, files in os.walk(wd):
        for f in files:
            if f == base:
                rel = os.path.relpath(os.path.join(dirpath, f), wd)
                found.append(rel)
    if len(found) == 1:
        if verbose:
            print(f"[resolver] Using unique filesystem match for '{path}': {found[0]}")
        return found[0]

    # Give up; let the tool error out naturally
    return path

def call_function(function_call_part, verbose: bool = False):
    raw_name = getattr(function_call_part, "name", "") or ""
    func_name = raw_name.removeprefix("schema_")

    if not raw_name:
        if verbose:
            print("Error: invalid function call (missing name)")
        return _tool_error("(missing)", "Invalid function call: missing name")

    if func_name not in FUNCTION_MAP:
        if verbose:
            print(f"Error: Unknown function: {raw_name}")
        return _tool_error(raw_name, f"Unknown function: {raw_name}")

    base_args = getattr(function_call_part, "args", {}) or {}
    try:
        func_args = dict(base_args)
    except Exception:
        return _tool_error(raw_name, "Invalid args type; expected an object/dict")

    # Normalize args
    func_args = _apply_arg_aliases(func_name, func_args)

    # Inject working directory
    func_args["working_directory"] = config.default_work_dir  # e.g., "./calculator"

    # Default verbose for search_code to CLI flag if not set
    if func_name == "search_code" and "verbose" not in func_args:
        func_args["verbose"] = verbose

    # Smart path resolution for file ops
    if func_name in ("get_file_content", "write_file"):
        key = "file_path"
        func_args[key] = _resolve_path_if_needed(func_args["working_directory"], func_args.get(key), verbose)

    if verbose:
        print(f" - Calling function: {func_name} ({func_args})")

    try:
        result = FUNCTION_MAP[func_name](**func_args)
        # keep search results for path resolution
        if func_name == "search_code" and isinstance(result, list):
            global _LAST_SEARCH_RESULTS
            _LAST_SEARCH_RESULTS = [r for r in result if isinstance(r, dict) and "path" in r]
    except TypeError as e:
        if verbose:
            print(f"Error calling {func_name}: {e}")
        return _tool_error(raw_name, f"Call error for {func_name}: {e}")
    except Exception as e:
        if verbose:
            print(f"Unhandled error in {func_name}: {e}")
        return _tool_error(raw_name, f"Unhandled error in {func_name}: {e}")

    return types.Content(
        role="tool",
        parts=[types.Part.from_function_response(name=raw_name, response={"result": result})],
    )
