"""
Identicon generator — GitHub-style 5×5 symmetric grid avatar.

Usage:
    from apps.core.identicon import generate_svg
    svg_string = generate_svg("My Team")
"""
import hashlib


def _hash_bytes(text: str) -> bytes:
    return hashlib.sha256(text.lower().encode('utf-8')).digest()


def _hsl_to_hex(h: float, s: float, l: float) -> str:
    """Convert HSL (0-360, 0-1, 0-1) to #RRGGBB hex."""
    s_frac = s
    l_frac = l
    c = (1 - abs(2 * l_frac - 1)) * s_frac
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = l_frac - c / 2
    if h < 60:
        r, g, b = c, x, 0
    elif h < 120:
        r, g, b = x, c, 0
    elif h < 180:
        r, g, b = 0, c, x
    elif h < 240:
        r, g, b = 0, x, c
    elif h < 300:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x
    ri, gi, bi = int((r + m) * 255), int((g + m) * 255), int((b + m) * 255)
    return f'#{ri:02x}{gi:02x}{bi:02x}'


def generate_svg(name: str, size: int = 80) -> str:
    """
    Generate a deterministic 5×5 identicon SVG from *name*.

    The grid is horizontally symmetric: columns 0–1 mirror columns 4–3, column 2 is center.
    Color is derived from the hash hue; saturation and lightness are fixed for legibility.
    """
    h = _hash_bytes(name)

    # Derive foreground color from first two hash bytes → hue 0-360
    hue = ((h[0] << 8 | h[1]) % 360)
    fg = _hsl_to_hex(hue, 0.60, 0.45)
    bg = '#f0f0f0'

    # Build 5×5 boolean grid from hash bits (bytes 2+)
    # Only 15 bits needed for unique pattern due to symmetry (3 cols × 5 rows)
    grid: list[list[bool]] = [[False] * 5 for _ in range(5)]
    bit_idx = 0
    for row in range(5):
        for col in range(3):   # left half + center
            byte_i = 2 + bit_idx // 8
            bit_i  = 7 - (bit_idx % 8)
            filled = bool(h[byte_i] & (1 << bit_i))
            grid[row][col] = filled
            # mirror: col 0→4, col 1→3, col 2 stays
            if col < 2:
                grid[row][4 - col] = filled
            bit_idx += 1

    cell = size // 5
    rects = []
    for row in range(5):
        for col in range(5):
            if grid[row][col]:
                x = col * cell
                y = row * cell
                rects.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" fill="{fg}"/>')

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 {size} {size}">'
        f'<rect width="{size}" height="{size}" fill="{bg}"/>'
        + ''.join(rects) +
        '</svg>'
    )


def generate_data_uri(name: str, size: int = 80) -> str:
    """Return the SVG as a data: URI for embedding in <img src="...">."""
    import base64
    svg = generate_svg(name, size)
    b64 = base64.b64encode(svg.encode('utf-8')).decode('ascii')
    return f'data:image/svg+xml;base64,{b64}'
