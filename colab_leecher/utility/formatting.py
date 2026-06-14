import math

_BINARY_UNITS = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]

def format_bytes(num, precision: int = 2) -> str:
    """Single human-readable byte formatter (IEC base-1024)."""
    try:
        num = float(num)
    except (TypeError, ValueError):
        return "N/A"
    if num <= 0:
        return "0 B"
    i = min(int(math.log(num, 1024)), len(_BINARY_UNITS) - 1)
    return f"{num / (1024 ** i):.{precision}f} {_BINARY_UNITS[i]}"

def format_speed(bytes_per_second) -> str:
    try:
        bps = float(bytes_per_second)
    except (TypeError, ValueError):
        return "N/A"
    if bps <= 0:
        return "N/A"
    return f"{format_bytes(bps)}/s"

def format_eta(seconds) -> str:
    try:
        seconds = float(seconds)
    except (TypeError, ValueError):
        return "N/A"
    if seconds <= 0 or seconds > 86400 * 7:
        return "N/A"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    if d:
        return f"{d}d {h}h {m}m"
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"
