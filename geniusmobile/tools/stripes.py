"""Racing stripes for a vehicle model: cut into its own body, painted with colour 3 (the tertiary colour; carcols.dat
car4 section), where colour 1 is (not the bed / colour 2, not the underside). The body's polygons are split along the
stripes' edges; the pieces inside get a copy of their material with colour 3's placeholder. Shapes stay, textures
(dirt) stay, the bonnet's part goes with the bonnet.

    stripes(dff_bytes) -> (dff_bytes, {part: stripe polygons})   (tools/make_img.py uses it for geniusmb.dff)
It also drops the model's extras (the Picador's bed loads) unless no_extras=False.

Stripes run front to back (the model's y) at |x| between INNER and OUTER (car space, metres).
"""
import copy
import math
import struct

import dff

INNER, OUTER = 0.05, 0.29
PARTS = ("chassis", "chassis_vlo", "bonnet_ok", "bonnet_dam", "boot_ok", "boot_dam")
COL1 = bytes((60, 255, 0, 255))
COL3 = bytes((0, 255, 255, 255))
PLANES = (-OUTER, -INNER, INNER, OUTER)


def in_stripe(x):
    return INNER < abs(x) < OUTER


def remove_extras(clump, fr):
    """no optional bed loads etc.: the atomics on extra1, extra2... go (their geometry stays, unused)"""
    keep = []
    for c in clump.children:
        if c.type == 0x14:
            fi = struct.unpack_from("<I", c.children[0].data, 0)[0]
            if (fr[fi][0] or "").lower().startswith("extra"):
                continue
        keep.append(c)
    clump.children = keep
    st = bytearray(clump.children[0].data)
    st[0:4] = struct.pack("<I", len(clump.find(0x14)))
    clump.children[0].data = bytes(st)


def stripes(data, no_extras=True):
    root = dff.load(data)
    clump = root[0]
    fr = dff.frames(clump)
    if no_extras:
        remove_extras(clump, fr)
    geoms = clump.first(0x1A).find(0x0F)
    done = {}
    for atomic in clump.find(0x14):
        fi, gi = struct.unpack_from("<II", atomic.children[0].data, 0)
        if fr[fi][0] in PARTS and gi not in done:
            rot, pos = dff.frame_to_root(fr, fi)
            done[gi] = (fr[fi][0], cut(geoms[gi], rot, pos))
    return dff.write(root), {name: n for name, n in done.values()}


def cut(gnode, rot, pos):
    """split one geometry's colour-1 triangles along the stripes; -> number of stripe triangles"""
    g = dff.Geometry(gnode.children[0].data)
    for ext in gnode.find(3):
        for c in ext.children:
            if c.type == 0x253F2FD:
                assert c.data[:4] == b"\0\0\0\0", "breakable geometry: not handled"
    mlist = gnode.first(0x08)
    mats = mlist.find(0x07)
    col1 = {i for i, m in enumerate(mats) if dff.material_colour(m) == COL1}
    stripe_mat = {}

    def car_x(v):
        return sum(v[k] * rot[k][0] for k in range(3)) + pos[0]

    def car_vec(v):
        return [sum(v[k] * rot[k][j] for k in range(3)) for j in range(3)]

    def vertex(i):
        return {"p": g.pos[i], "n": g.nrm[i] if g.nrm else None, "uv": [s[i] for s in g.uvs],
                "c": g.prelit[i] if g.prelit else None, "x": car_x(g.pos[i])}

    def lerp(a, b, t):
        def l(u, v):
            return tuple(u[k] + (v[k] - u[k]) * t for k in range(len(u)))
        n = None
        if a["n"] is not None:
            n = l(a["n"], b["n"])
            ln = math.sqrt(sum(c * c for c in n)) or 1.0
            n = tuple(c / ln for c in n)
        c = None
        if a["c"] is not None:
            c = bytes(round(a["c"][k] + (b["c"][k] - a["c"][k]) * t) for k in range(4))
        return {"p": l(a["p"], b["p"]), "n": n, "uv": [l(u, v) for u, v in zip(a["uv"], b["uv"])], "c": c,
                "x": a["x"] + (b["x"] - a["x"]) * t}

    def split(poly, plane):
        """-> (part with x < plane, part with x >= plane)"""
        lo, hi = [], []
        for i, a in enumerate(poly):
            b = poly[(i + 1) % len(poly)]
            (lo if a["x"] < plane else hi).append(a)
            if (a["x"] < plane) != (b["x"] < plane):
                m = lerp(a, b, (plane - a["x"]) / (b["x"] - a["x"]))
                lo.append(m)
                hi.append(m)
        return lo, hi

    new_tris, new_verts = [], []

    def add_vertex(v):
        g.pos.append(v["p"])
        if g.nrm is not None:
            g.nrm.append(v["n"])
        for s, uv in zip(g.uvs, v["uv"]):
            s.append(uv)
        if g.prelit is not None:
            g.prelit.append(v["c"])
        return len(g.pos) - 1

    stripe_count = 0
    for a, b, c, m in g.tris:
        if m not in col1:
            new_tris.append((a, b, c, m))
            continue
        pa, pb, pc = (car_vec(g.pos[i]) for i in (a, b, c))
        e1 = [pb[k] - pa[k] for k in range(3)]
        e2 = [pc[k] - pa[k] for k in range(3)]
        nz = e1[0] * e2[1] - e1[1] * e2[0]
        ln = math.sqrt(sum(v * v for v in (e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], nz))) or 1.0
        xs = [car_x(g.pos[i]) for i in (a, b, c)]
        if nz / ln < -0.3 or max(xs) <= -OUTER or min(xs) >= OUTER or all(-INNER <= x <= INNER for x in xs):
            new_tris.append((a, b, c, m))  # facing down, or nowhere near a stripe
            continue
        pieces = [[vertex(a), vertex(b), vertex(c)]]
        for plane in PLANES:
            nxt = []
            for poly in pieces:
                lo, hi = split(poly, plane)
                nxt += [q for q in (lo, hi) if len(q) >= 3]
            pieces = nxt
        for poly in pieces:
            cx = sum(v["x"] for v in poly) / len(poly)
            mat = m
            if in_stripe(cx):
                if m not in stripe_mat:
                    copy_mat = copy.deepcopy(mats[m])
                    dff.set_material_colour(copy_mat, COL3)
                    mlist.children.append(copy_mat)
                    mats.append(copy_mat)
                    stripe_mat[m] = len(mats) - 1
                mat = stripe_mat[m]
                stripe_count += 1
            idx = [add_vertex(v) for v in poly]
            for k in range(1, len(idx) - 1):
                new_tris.append((idx[0], idx[k], idx[k + 1], mat))
    g.tris = new_tris
    # material list struct: count, then -1 (a material of its own) per material
    n = len(mats)
    mlist.children[0].data = struct.pack("<I", n) + b"".join(struct.pack("<i", -1) for _ in range(n))
    gnode.children[0].data = g.pack()
    for ext in gnode.find(3):
        for c in ext.children:
            if c.type == 0x50E:
                c.data = g.bin_mesh()
    assert len(g.pos) < 65536
    return stripe_count
