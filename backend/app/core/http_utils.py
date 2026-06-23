from urllib.parse import quote


def inline_content_disposition(filename: str) -> str:
    """Build a latin-1-safe Content-Disposition header with UTF-8 filename."""
    ascii_fallback = filename.encode("ascii", "ignore").decode().strip()
    if not ascii_fallback:
        ascii_fallback = "download"
    encoded = quote(filename, safe="")
    return f"inline; filename=\"{ascii_fallback}\"; filename*=UTF-8''{encoded}"
