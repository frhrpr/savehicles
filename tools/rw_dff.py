"""From the user's reference ZIP, savibe_example/dff.py.

Minimal RenderWare DFF (clump) reader / writer: a chunk tree whose containers are parsed and whose other chunks are
kept as raw bytes, so a file written back unchanged is byte-identical. Geometry helpers for editing vehicle models.
"""
import struct

CONTAINERS = {0x10, 0x0E, 0x1A, 0x0F, 0x08, 0x07, 0x06, 0x03, 0x14}  # clump, frame list, geometry list, geometry,
# material list, material, texture, extension, atomic


class Chunk:
    def __init__(self, type, version, data=None, children=None):
        self.type, self.version, self.data, self.children = type, version, data, children

    def find(self, type):
        return [c for c in self.children if c.type == type]

    def first(self, type):
        return self.find(type)[0]


def parse(buf, off=0, end=None, parent_type=None):
    end = len(buf) if end is None else end
    out = []
    while off + 12 <= end:
        t, size, ver = struct.unpack_from("<III", buf, off)
        a, b = off + 12, off + 12 + size
        # a struct chunk (1) is always raw; containers are parsed (an extension's contents too)
        if t in CONTAINERS and t != 1:
            out.append(Chunk(t, ver, children=parse(buf, a, b, t)))
        else:
            out.append(Chunk(t, ver, data=bytes(buf[a:b])))
        off = b
    return out


def write(chunks):
    out = b""
    for c in chunks:
        body = c.data if c.children is None else write(c.children)
        out += struct.pack("<III", c.type, len(body), c.version) + body
    return out


def load(data):
    return parse(data)


# --- frames ---
def frames(clump):
    """-> [(name, matrix 3x3 rows, position, parent)] in file order"""
    fl = clump.first(0x0E)
    st = fl.children[0].data
    n = struct.unpack_from("<I", st, 0)[0]
    out = []
    for i in range(n):
        v = struct.unpack_from("<12fiI", st, 4 + 56 * i)
        out.append([None, [v[0:3], v[3:6], v[6:9]], v[9:12], v[12]])
    for i, ext in enumerate(fl.find(3)):
        for c in ext.children:
            if c.type == 0x253F2FE:
                out[i][0] = c.data.decode("latin-1")
    return out


def frame_to_root(fr, i):
    """-> (3x3 rows, translation) of frame i in clump space (RW matrices: rows are right / up / at, p = position)"""
    rot = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    pos = [0.0, 0.0, 0.0]
    chain = []
    while i >= 0:
        chain.append(i)
        i = fr[i][3]
    for j in chain:  # child first: v_parent = v * R + p
        r, p = fr[j][1], fr[j][2]
        rot = [[sum(rot[a][k] * r[k][b] for k in range(3)) for b in range(3)] for a in range(3)]
        pos = [sum(pos[k] * r[k][b] for k in range(3)) + p[b] for b in range(3)]
    return rot, pos


# --- geometry ---
class Geometry:
    """the struct of a (non-native) geometry with one morph target"""

    def __init__(self, data):
        self.flags, ntri, nvert, nmorph = struct.unpack_from("<IIII", data, 0)
        assert nmorph == 1, "one morph target only"
        p = 16
        self.prelit = None
        if self.flags & 8:
            self.prelit = [data[p + 4 * i:p + 4 * i + 4] for i in range(nvert)]
            p += 4 * nvert
        nsets = (self.flags >> 16) & 0xFF or (2 if self.flags & 0x80 else (1 if self.flags & 4 else 0))
        self.uvs = []
        for s in range(nsets):
            self.uvs.append([struct.unpack_from("<2f", data, p + 8 * i) for i in range(nvert)])
            p += 8 * nvert
        self.tris = []  # (v0, v1, v2, material)
        for i in range(ntri):
            b, a, m, c = struct.unpack_from("<4H", data, p + 8 * i)
            self.tris.append((a, b, c, m))
        p += 8 * ntri
        self.sphere = data[p:p + 16]
        has_v, has_n = struct.unpack_from("<II", data, p + 16)
        p += 24
        assert has_v
        self.pos = [struct.unpack_from("<3f", data, p + 12 * i) for i in range(nvert)]
        p += 12 * nvert
        self.nrm = None
        if has_n:
            self.nrm = [struct.unpack_from("<3f", data, p + 12 * i) for i in range(nvert)]
            p += 12 * nvert
        assert p == len(data), (p, len(data))

    def pack(self):
        nvert, ntri = len(self.pos), len(self.tris)
        flags = self.flags & ~1  # triangle lists, not strips (the bin mesh is rebuilt as lists)
        out = struct.pack("<IIII", flags, ntri, nvert, 1)
        if self.prelit is not None:
            out += b"".join(self.prelit)
        for s in self.uvs:
            out += b"".join(struct.pack("<2f", *uv) for uv in s)
        out += b"".join(struct.pack("<4H", b, a, m, c) for a, b, c, m in self.tris)
        out += self.sphere + struct.pack("<II", 1, 1 if self.nrm is not None else 0)
        out += b"".join(struct.pack("<3f", *v) for v in self.pos)
        if self.nrm is not None:
            out += b"".join(struct.pack("<3f", *v) for v in self.nrm)
        return out

    def bin_mesh(self):
        """a bin mesh PLG (0x50E) body: triangle lists split by material"""
        by = {}
        for a, b, c, m in self.tris:
            by.setdefault(m, []).extend((a, b, c))
        body = struct.pack("<III", 0, len(by), sum(len(v) for v in by.values()))
        for m in sorted(by):
            body += struct.pack("<II", len(by[m]), m) + b"".join(struct.pack("<I", i) for i in by[m])
        return body


def material_colour(mat):
    return mat.children[0].data[4:8]


def set_material_colour(mat, rgba):
    d = bytearray(mat.children[0].data)
    d[4:8] = rgba
    mat.children[0].data = bytes(d)
