# functions/search_code.py
import os
import re
import fnmatch
# functions/schema_search_code.py
from google.genai import types

DEFAULT_IGNORES = {
    ".git", ".venv", "__pycache__", "node_modules", ".mypy_cache", ".pytest_cache", ".idea", ".vscode", "dist", "build"
}
TEXT_EXT_HINT = {
    ".py", ".go", ".c", ".h", ".cpp", ".hpp", ".rs", ".java", ".js", ".ts", ".tsx", ".jsx",
    ".json", ".toml", ".yaml", ".yml", ".md", ".txt", ".ini", ".cfg", ".sh", ".ps1", ".bat",
}

def _is_binary_guess(path, max_bytes=4096):
    try:
        with open(path, "rb") as f:
            chunk = f.read(max_bytes)
        if not chunk:
            return False
        # Heuristic: if there are null bytes, likely binary
        return b"\x00" in chunk
    except Exception:
        return True  # be conservative

def _read_lines_safe(path, max_bytes=2_000_000):
    size = os.path.getsize(path)
    if size > max_bytes:
        return None  # too big to scan
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.readlines()
    except Exception:
        return None

def _match_any_glob(name, patterns):
    return any(fnmatch.fnmatch(name, p) for p in patterns)

def _ext(name):
    return os.path.splitext(name)[1].lower()

def search_code(
    working_directory: str,
    root: str = ".",
    name_globs: list[str] | None = None,      # e.g. ["*.py", "*test*"]
    extensions: list[str] | None = None,      # e.g. [".py", ".go"]
    content_query: str | None = None,         # plain text OR regex (see use_regex)
    use_regex: bool = False,
    case_sensitive: bool = False,
    max_results: int = 50,
    context_lines: int = 2,
    extra_ignores: list[str] | None = None,   # folder basenames to ignore
    verbose: bool=False
):
    """
    Returns list of dicts:
      {
        "path": "relative/path/to/file.py",
        "score": float,
        "matches": [
           {"line_no": 42, "line": "print('hi')", "preview": ["context above", "...", "context below"]}
        ]
      }
    If no content_query, 'matches' will be empty and files are ranked by filename match strength.
    """
    # --- Safety: resolve paths inside working dir
    wd = os.path.abspath(working_directory)
    base = os.path.abspath(os.path.join(wd, root))
    if os.path.commonpath([wd, base]) != wd:
        print(f'Error: Cannot search "{root}" as it is outside the permitted working directory')
        return None

    if not os.path.exists(base):
        print(f'Error: Directory "{root}" does not exist')
        return None

    if not os.path.isdir(base):
        print(f'Error: "{root}" is not a directory')
        return None

    # --- Build config
    ignored = set(DEFAULT_IGNORES)
    if extra_ignores:
        ignored.update(extra_ignores)

    name_globs = name_globs or []
    extensions = [e.lower() for e in (extensions or [])]
    do_content = content_query is not None and content_query != ""

    if do_content:
        flags = 0 if case_sensitive else re.IGNORECASE
        pattern = re.compile(content_query, flags) if use_regex else None
        needle = content_query if case_sensitive else (content_query or "").lower()

    results = []

    for dirpath, dirnames, filenames in os.walk(base):
        # prune ignored folders in-place
        dirnames[:] = [d for d in dirnames if d not in ignored]

        for fname in filenames:
            rel = os.path.relpath(os.path.join(dirpath, fname), wd)
            # filter by extension if provided
            if extensions and _ext(fname) not in extensions:
                continue
            # filter by name globs if provided
            if name_globs and not _match_any_glob(fname, name_globs):
                # allow content search to still find it if no name match specified? Keep strict:
                continue

            file_score = 0.0
            # simple filename scoring
            base_lower = fname.lower()
            for g in name_globs:
                if fnmatch.fnmatch(base_lower, g.lower()):
                    file_score += 1.0
            if extensions and _ext(fname) in extensions:
                file_score += 0.5

            matches = []
            if do_content:
                # skip likely binaries if not a known text ext
                if (_ext(fname) not in TEXT_EXT_HINT) and _is_binary_guess(os.path.join(dirpath, fname)):
                    continue
                lines = _read_lines_safe(os.path.join(dirpath, fname))
                if lines is None:
                    continue

                for idx, line in enumerate(lines, start=1):
                    hit = False
                    if use_regex:
                        if pattern.search(line):
                            hit = True
                    else:
                        src = line if case_sensitive else line.lower()
                        if needle in src:
                            hit = True
                    if hit:
                        start = max(1, idx - context_lines)
                        end = min(len(lines), idx + context_lines)
                        preview = [l.rstrip("\n") for l in lines[start-1:end]]
                        matches.append({
                            "line_no": idx,
                            "line": line.rstrip("\n"),
                            "preview": preview
                        })

                if matches:
                    # content hits give a bigger bump
                    file_score += 2.0 + min(1.0, len(matches) * 0.1)

            if (name_globs or extensions or do_content) and (matches or not do_content):
                results.append({
                    "path": rel,
                    "score": file_score,
                    "matches": matches
                })

    # rank + trim
    results.sort(key=lambda r: r["score"], reverse=True)
    trimmed = results[:max_results]

    # Human-readable stdout for Boot.dev checks
    if verbose:
        print("Search Results:")
        for r in trimmed:
            print(f'- {r["path"]} (score={r["score"]:.2f})')
            for m in r["matches"][:3]:  # cap previews per file for readability
                pv = " ⏤ ".join(m["preview"])
                print(f'  L{m["line_no"]}: {m["line"]}')
                print(f'    … {pv}')

    return trimmed




schema_search_code = types.FunctionDeclaration(
    name="search_code",
    description="Search for source files by name/extension and optional content, returning ranked matches and code previews.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "root": types.Schema(type=types.Type.STRING, description="Directory to search, relative to working directory (default '.')"),
            "name_globs": types.Schema(type=types.Type.ARRAY, items=types.Schema(type=types.Type.STRING), description="Filename patterns, e.g. ['*.py','*test*']"),
            "extensions": types.Schema(type=types.Type.ARRAY, items=types.Schema(type=types.Type.STRING), description="File extensions, e.g. ['.py','.go']"),
            "content_query": types.Schema(type=types.Type.STRING, description="Plain text or regex pattern to search within files"),
            "use_regex": types.Schema(type=types.Type.BOOLEAN, description="Treat content_query as a regex"),
            "case_sensitive": types.Schema(type=types.Type.BOOLEAN, description="Case-sensitive search"),
            "max_results": types.Schema(type=types.Type.INTEGER, description="Max results to return"),
            "context_lines": types.Schema(type=types.Type.INTEGER, description="Lines of context around each match"),
            "extra_ignores": types.Schema(type=types.Type.ARRAY, items=types.Schema(type=types.Type.STRING), description="Extra folder basenames to ignore"),
            "verbose": types.Schema(type=types.Type.BOOLEAN, description="If verbose, prints all data, if not verbose, returns a succinct summary")
        },
        required=[],
    )
)
