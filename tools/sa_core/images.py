"""PNG -> RGBA cru de 50x50, o formato que o Ultrahand e o overlay desenham.

Só biblioteca padrão: lê PNG de 8 bits por canal, sem entrelaçamento
(cinza, cinza+alfa, RGB, RGBA, paleta) e reduz por média de área.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}


class ImageError(ValueError):
    pass


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def read_png(path: Path) -> tuple[int, int, bytes]:
    """Devolve (largura, altura, pixels RGBA8888)."""
    data = path.read_bytes()
    if not data.startswith(_SIGNATURE):
        raise ImageError(f"{path.name}: não é PNG")
    pos = len(_SIGNATURE)
    width = height = depth = color = interlace = None
    palette = b""
    alpha_table = b""
    idat = bytearray()
    while pos + 8 <= len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            width, height, depth, color, _, _, interlace = struct.unpack(">IIBBBBB", body)
        elif kind == b"PLTE":
            palette = body
        elif kind == b"tRNS":
            alpha_table = body
        elif kind == b"IDAT":
            idat += body
        elif kind == b"IEND":
            break
    if width is None or color not in _CHANNELS:
        raise ImageError(f"{path.name}: PNG sem cabeçalho válido")
    if depth != 8 or interlace:
        raise ImageError(f"{path.name}: use PNG de 8 bits por canal, sem entrelaçamento")

    channels = _CHANNELS[color]
    stride = width * channels
    raw = zlib.decompress(bytes(idat))
    rows: list[bytearray] = []
    previous = bytearray(stride)
    offset = 0
    for _ in range(height):
        kind = raw[offset]
        line = bytearray(raw[offset + 1:offset + 1 + stride])
        offset += 1 + stride
        for i in range(stride):
            left = line[i - channels] if i >= channels else 0
            up = previous[i]
            corner = previous[i - channels] if i >= channels else 0
            if kind == 1:
                line[i] = (line[i] + left) & 0xFF
            elif kind == 2:
                line[i] = (line[i] + up) & 0xFF
            elif kind == 3:
                line[i] = (line[i] + ((left + up) >> 1)) & 0xFF
            elif kind == 4:
                line[i] = (line[i] + _paeth(left, up, corner)) & 0xFF
            elif kind != 0:
                raise ImageError(f"{path.name}: filtro PNG desconhecido {kind}")
        rows.append(line)
        previous = line

    out = bytearray(width * height * 4)
    k = 0
    for line in rows:
        for x in range(width):
            px = line[x * channels:(x + 1) * channels]
            if color == 6:
                r, g, b, a = px
            elif color == 2:
                r, g, b = px
                a = 255
            elif color == 4:
                r = g = b = px[0]
                a = px[1]
            elif color == 0:
                r = g = b = px[0]
                a = 255
            else:
                idx = px[0]
                r, g, b = palette[idx * 3:idx * 3 + 3]
                a = alpha_table[idx] if idx < len(alpha_table) else 255
            out[k:k + 4] = bytes((r, g, b, a))
            k += 4
    return width, height, bytes(out)


def resize_rgba(width: int, height: int, pixels: bytes, size: int) -> bytes:
    """Média de área com alfa pré-multiplicado, para não escurecer bordas transparentes."""
    if (width, height) == (size, size):
        return pixels
    out = bytearray(size * size * 4)
    for oy in range(size):
        y0, y1 = oy * height / size, (oy + 1) * height / size
        for ox in range(size):
            x0, x1 = ox * width / size, (ox + 1) * width / size
            acc = [0.0, 0.0, 0.0, 0.0]
            total = 0.0
            for sy in range(int(y0), min(height, int(y1 + 0.999999))):
                wy = min(y1, sy + 1) - max(y0, sy)
                if wy <= 0:
                    continue
                for sx in range(int(x0), min(width, int(x1 + 0.999999))):
                    wx = min(x1, sx + 1) - max(x0, sx)
                    if wx <= 0:
                        continue
                    weight = wx * wy
                    i = (sy * width + sx) * 4
                    alpha = pixels[i + 3] / 255
                    acc[0] += pixels[i] * alpha * weight
                    acc[1] += pixels[i + 1] * alpha * weight
                    acc[2] += pixels[i + 2] * alpha * weight
                    acc[3] += alpha * weight
                    total += weight
            j = (oy * size + ox) * 4
            alpha = acc[3] / total if total else 0
            if alpha > 0:
                out[j:j + 3] = bytes(min(255, round(c / acc[3])) for c in acc[:3])
            out[j + 3] = round(alpha * 255)
    return bytes(out)


def png_to_rgba(path: Path, size: int) -> bytes:
    width, height, pixels = read_png(path)
    return resize_rgba(width, height, pixels, size)
