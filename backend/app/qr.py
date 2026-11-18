"""Minimal pure-Python QR Code encoder (byte mode, ECC level M, versions 1-10).

No external dependency: the display and ticket pages render the returned SVG locally,
which keeps the system fully offline.
"""

# version: (total data codewords, [data codewords per block], ecc codewords per block)
BLOCKS_M = {
    1: (16, [16], 10),
    2: (28, [28], 16),
    3: (44, [44], 26),
    4: (64, [32, 32], 18),
    5: (86, [43, 43], 24),
    6: (108, [27, 27, 27, 27], 16),
    7: (124, [31, 31, 31, 31], 18),
    8: (154, [38, 38, 39, 39], 22),
    9: (182, [36, 36, 36, 37, 37], 22),
    10: (216, [43, 43, 43, 43, 44], 26),
}
ALIGN = {
    1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34],
    7: [6, 22, 38], 8: [6, 24, 42], 9: [6, 26, 46], 10: [6, 28, 50],
}
CAPACITY = {v: BLOCKS_M[v][0] - (2 if v < 10 else 3) for v in BLOCKS_M}

# --- GF(256) arithmetic ---------------------------------------------------

_EXP = [0] * 512
_LOG = [0] * 256
_x = 1
for _i in range(255):
    _EXP[_i] = _x
    _LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
for _i in range(255, 512):
    _EXP[_i] = _EXP[_i - 255]


def _mul(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    return _EXP[_LOG[a] + _LOG[b]]


def _rs_generator(degree: int) -> list[int]:
    poly = [1]
    for i in range(degree):
        nxt = [0] * (len(poly) + 1)
        for j, coef in enumerate(poly):
            nxt[j] ^= coef
            nxt[j + 1] ^= _mul(coef, _EXP[i])
        poly = nxt
    return poly


def _rs_ecc(data: list[int], degree: int) -> list[int]:
    gen = _rs_generator(degree)
    rem = [0] * degree
    for byte in data:
        factor = byte ^ rem[0]
        rem = rem[1:] + [0]
        for i, coef in enumerate(gen[1:]):
            rem[i] ^= _mul(coef, factor)
    return rem


# --- bit stream -----------------------------------------------------------

def _encode_data(payload: bytes, version: int) -> list[int]:
    total_data = BLOCKS_M[version][0]
    bits = []

    def push(value: int, length: int):
        for i in range(length - 1, -1, -1):
            bits.append((value >> i) & 1)

    push(0b0100, 4)
    push(len(payload), 8 if version < 10 else 16)
    for byte in payload:
        push(byte, 8)
    push(0, min(4, total_data * 8 - len(bits)))
    while len(bits) % 8:
        bits.append(0)
    codewords = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]
    pads = [0xEC, 0x11]
    data_len = len(codewords)
    while len(codewords) < total_data:
        codewords.append(pads[(len(codewords) - data_len) % 2])
    return codewords


def _interleave(codewords: list[int], version: int) -> list[int]:
    sizes, ecc_len = BLOCKS_M[version][1], BLOCKS_M[version][2]
    blocks, pos = [], 0
    for size in sizes:
        chunk = codewords[pos:pos + size]
        pos += size
        blocks.append((chunk, _rs_ecc(chunk, ecc_len)))
    out = []
    for i in range(max(sizes)):
        for chunk, _ in blocks:
            if i < len(chunk):
                out.append(chunk[i])
    for i in range(ecc_len):
        for _, ecc in blocks:
            out.append(ecc[i])
    return out


# --- matrix ---------------------------------------------------------------

def _bit(value: int, index: int) -> bool:
    return ((value >> index) & 1) != 0


def _mask_condition(mask: int, x: int, y: int) -> bool:
    if mask == 0:
        return (x + y) % 2 == 0
    if mask == 1:
        return y % 2 == 0
    if mask == 2:
        return x % 3 == 0
    if mask == 3:
        return (x + y) % 3 == 0
    if mask == 4:
        return (x // 3 + y // 2) % 2 == 0
    if mask == 5:
        return (x * y) % 2 + (x * y) % 3 == 0
    if mask == 6:
        return ((x * y) % 2 + (x * y) % 3) % 2 == 0
    return ((x + y) % 2 + (x * y) % 3) % 2 == 0


class _Matrix:
    def __init__(self, version: int):
        self.version = version
        self.size = 17 + 4 * version
        self.modules = [[False] * self.size for _ in range(self.size)]
        self.func = [[False] * self.size for _ in range(self.size)]

    def set(self, x: int, y: int, dark: bool, is_func: bool = True) -> None:
        if 0 <= x < self.size and 0 <= y < self.size:
            self.modules[y][x] = dark
            if is_func:
                self.func[y][x] = True

    def draw_function_patterns(self) -> None:
        size = self.size
        for i in range(size):
            self.set(6, i, i % 2 == 0)
            self.set(i, 6, i % 2 == 0)
        for cx, cy in ((3, 3), (size - 4, 3), (3, size - 4)):
            for dy in range(-4, 5):
                for dx in range(-4, 5):
                    dist = max(abs(dx), abs(dy))
                    self.set(cx + dx, cy + dy, dist not in (2, 4))
        coords = ALIGN[self.version]
        last = len(coords) - 1
        for i, ax in enumerate(coords):
            for j, ay in enumerate(coords):
                if (i == 0 and j == 0) or (i == 0 and j == last) or (i == last and j == 0):
                    continue
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        self.set(ax + dx, ay + dy, max(abs(dx), abs(dy)) != 1)
        if self.version >= 7:
            rem = self.version
            for _ in range(12):
                rem = (rem << 1) ^ ((rem >> 11) * 0x1F25)
            bits = self.version << 12 | rem
            for i in range(18):
                a, b = size - 11 + i % 3, i // 3
                self.set(a, b, _bit(bits, i))
                self.set(b, a, _bit(bits, i))

    def draw_format(self, mask: int) -> None:
        data = mask  # ECC level M = 00
        rem = data
        for _ in range(10):
            rem = (rem << 1) ^ ((rem >> 9) * 0x537)
        bits = (data << 10 | rem) ^ 0x5412
        size = self.size
        for i in range(6):
            self.set(8, i, _bit(bits, i))
        self.set(8, 7, _bit(bits, 6))
        self.set(8, 8, _bit(bits, 7))
        self.set(7, 8, _bit(bits, 8))
        for i in range(9, 15):
            self.set(14 - i, 8, _bit(bits, i))
        for i in range(8):
            self.set(size - 1 - i, 8, _bit(bits, i))
        for i in range(8, 15):
            self.set(8, size - 15 + i, _bit(bits, i))
        self.set(8, size - 8, True)

    def draw_codewords(self, codewords: list[int]) -> None:
        size = self.size
        i = 0
        for right in range(size - 1, 0, -2):
            if right == 6:
                right = 5
            for vert in range(size):
                for j in range(2):
                    x = right - j
                    upward = ((right + 1) & 2) == 0
                    y = (size - 1 - vert) if upward else vert
                    if not self.func[y][x] and i < len(codewords) * 8:
                        index = i >> 3
                        bit = _bit(codewords[index], 7 - (i & 7))
                        self.modules[y][x] = bit
                        i += 1

    def apply_mask(self, mask: int) -> None:
        for y in range(self.size):
            for x in range(self.size):
                if not self.func[y][x] and _mask_condition(mask, x, y):
                    self.modules[y][x] = not self.modules[y][x]

    def penalty(self) -> int:
        size, score = self.size, 0
        rows = self.modules
        cols = [[rows[y][x] for y in range(size)] for x in range(size)]
        lines = rows + cols
        for line in lines:
            run, prev = 1, line[0]
            for value in line[1:]:
                if value == prev:
                    run += 1
                    if run == 5:
                        score += 3
                    elif run > 5:
                        score += 1
                else:
                    run, prev = 1, value
            for i in range(size - 10):
                if line[i] and not line[i + 1] and line[i + 2] and line[i + 3] and line[i + 4] \
                        and not line[i + 5] and line[i + 6] and not line[i + 7] \
                        and not line[i + 8] and not line[i + 9] and not line[i + 10]:
                    score += 40
                if not line[i] and not line[i + 1] and not line[i + 2] and not line[i + 3] \
                        and line[i + 4] and not line[i + 5] and line[i + 6] and line[i + 7] \
                        and line[i + 8] and not line[i + 9] and line[i + 10]:
                    score += 40
        for y in range(size - 1):
            for x in range(size - 1):
                block = rows[y][x] + rows[y][x + 1] + rows[y + 1][x] + rows[y + 1][x + 1]
                if block in (0, 4):
                    score += 3
        dark = sum(sum(1 for v in row if v) for row in rows)
        total = size * size
        k = abs(dark * 20 - total * 10) // total
        score += k * 10
        return score


def matrix_for(payload: bytes):
    version = next((v for v in range(1, 11) if len(payload) <= CAPACITY[v]), None)
    if version is None:
        raise ValueError("qr_payload_too_long")
    codewords = _interleave(_encode_data(payload, version), version)
    best = None
    for mask in range(8):
        m = _Matrix(version)
        m.draw_function_patterns()
        m.draw_format(mask)
        m.draw_codewords(codewords)
        m.apply_mask(mask)
        m.draw_format(mask)
        p = m.penalty()
        if best is None or p < best[0]:
            best = (p, m)
    return best[1]


def qr_svg(data: str, scale: int = 4, quiet: int = 4, dark: str = "#000000", light: str = "#ffffff") -> str:
    """Return a standalone SVG string for the given data."""
    m = matrix_for(data.encode("utf-8"))
    size = m.size
    dim = (size + quiet * 2) * scale
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{dim}" height="{dim}" '
        f'viewBox="0 0 {dim} {dim}" shape-rendering="crispEdges">',
        f'<rect width="{dim}" height="{dim}" fill="{light}"/>',
        f'<path fill="{dark}" d="',
    ]
    path = []
    for y in range(size):
        for x in range(size):
            if m.modules[y][x]:
                path.append(f"M{(x + quiet) * scale} {(y + quiet) * scale}h{scale}v{scale}h-{scale}z")
    parts.append("".join(path))
    parts.append('"/></svg>')
    return "".join(parts)
