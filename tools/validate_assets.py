"""Structural and asset-budget checks for the delivered game files.

python tools/validate_assets.py [--dragonff /path/to/DragonFF]
This validates file structure, not GTA's runtime behaviour.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import struct
import sys
from collections import Counter

import rw_dff as rw
from txd_textures import read_txd, chunks

ROOT=Path(__file__).resolve().parents[1]
REF=ROOT/'reference/gtasa_vehicle_reference/models'
OUT=ROOT/'dist/modloader/linden'


def names(clump): return [frame[0] for frame in rw.frames(clump)]


def collision(clump):
    return [p.data for e in clump.find(3) for p in e.children if p.type==0x253f2fa]


def validate(dragonff=None):
    checks=[]
    def check(condition, text):
        if not condition: raise AssertionError(text)
        checks.append(text)

    old=rw.load((REF/'premier.dff').read_bytes())[0]
    raw=(OUT/'premier.dff').read_bytes()
    cl=rw.load(raw)[0]
    check(rw.write([cl])==raw, 'DFF byte-exact round trip')
    check(names(old)==names(cl), 'All 51 original frame names and ordering preserved')
    frames=rw.frames(cl)
    old_frames=rw.frames(old)
    check(all(a[1]==b[1] and a[3]==b[3] for a,b in zip(frames,old_frames)), 'Frame rotations and parent hierarchy preserved')
    for i,f in enumerate(frames):
        if f[0].startswith('wheel_'):
            check(math.dist(rw.frame_to_root(frames,i)[1],rw.frame_to_root(old_frames,i)[1])<1e-5,f'{f[0]} position preserved')
    check(collision(cl)==collision(old) and bool(collision(cl)), 'Embedded COL3 preserved byte for byte')
    geoms=cl.first(26).find(15)
    original_geoms=old.first(26).find(15)
    check(len(geoms)==len(original_geoms)==22,'All 22 geometry parts retained')
    check([a.children[0].data for a in cl.find(20)]==[a.children[0].data for a in old.find(20)], 'All 22 atomic-to-frame bindings preserved')
    dependencies=set()
    total=0
    for gi,node in enumerate(geoms):
        g=rw.Geometry(node.children[0].data)
        mats=node.first(8).find(7)
        check(len(g.pos)<65536 and all(math.isfinite(c) for v in g.pos for c in v),f'Geometry {gi}: finite vertices within 16-bit index limit')
        check(all(0<=m<len(mats) and all(0<=i<len(g.pos) for i in (a,b,c)) for a,b,c,m in g.tris),f'Geometry {gi}: triangle and material indices valid')
        check(struct.unpack_from('<I',node.first(8).children[0].data)[0]==len(mats),f'Geometry {gi}: material-list count valid')
        check(all(len(layer)==len(g.pos) for layer in g.uvs) and (g.prelit is None or len(g.prelit)==len(g.pos)),f'Geometry {gi}: UV and vertex-colour lengths valid')
        if g.nrm:
            check(len(g.nrm)==len(g.pos) and all(abs(math.sqrt(sum(c*c for c in v))-1)<0.015 for v in g.nrm),f'Geometry {gi}: normal lengths valid')
        x,y,z,radius=struct.unpack('<4f',g.sphere)
        check(all(math.dist(v,(x,y,z))<=radius+1e-5 for v in g.pos),f'Geometry {gi}: bounding sphere encloses vertices')
        binmeshes=[p for e in node.find(3) for p in e.children if p.type==0x50e]
        check(len(binmeshes)==1 and binmeshes[0].data==g.bin_mesh(),f'Geometry {gi}: bin-mesh indices match triangle list')
        for mat in mats:
            if mat.find(6): dependencies.add(mat.first(6).find(2)[0].data.rstrip(b'\0').decode('ascii'))
        total+=len(g.tris)
    # Engine-controlled paint/lamp tags must remain in the corresponding body
    # and door materials. Bumpers intentionally become unpainted plastic.
    tags=[bytes(t) for t in [(255,175,0),(0,255,200),(185,255,0),(255,60,0)]]
    for gi,(a,b) in enumerate(zip(original_geoms,geoms)):
        before=Counter(rw.material_colour(m)[:3] for m in a.first(8).find(7) if rw.material_colour(m)[:3] in tags)
        after=Counter(rw.material_colour(m)[:3] for m in b.first(8).find(7) if rw.material_colour(m)[:3] in tags)
        check(before==after,f'Geometry {gi}: engine lamp-control tags preserved')
    local=read_txd(OUT/'premier.txd')
    generic=read_txd(REF/'generic/vehicle.txd')
    check(dependencies<=set(local)|set(generic),'Every texture dependency resolves locally or in stock vehicle.txd')
    check(local['linden128'][0].size==(128,128) and len(local['linden128'])==8,'Custom diffuse is 128x128 with eight valid mip levels')
    check([i.size for i in local['linden128']]==[(max(1,128>>j),max(1,128>>j)) for j in range(8)],'Mip chain reaches 1x1')
    # Retain the original native texture chunks without recompression.
    def native(path):
        return [data for kind,data in chunks(next(chunks(path.read_bytes()))[1]) if kind==0x15]
    check(native(OUT/'premier.txd')[:2]==native(REF/'premier.txd'),'Both donor texture rasters retained byte for byte')
    check(total<=3200, 'All model parts together remain within the supplied stock-sedan budget')
    visible=0
    for at in cl.find(20):
        fi,gi=struct.unpack_from('<II',at.children[0].data)
        name=frames[fi][0]
        if name=='chassis_vlo' or name.endswith('_dam'): continue
        visible+=len(rw.Geometry(geoms[gi].children[0].data).tris)*(4 if name=='wheel' else 1)
    independent=None
    if dragonff:
        sys.path.insert(0,str(Path(dragonff).resolve()))
        from gtaLib import dff,txd
        parsed=dff.dff();parsed.load_file(str(OUT/'premier.dff'))
        check(len(parsed.clumps)==1 and len(parsed.clumps[0].geometry_list)==22,'Independent DragonFF DFF parser accepts all model parts')
        decoded=txd.txd();decoded.load_file(str(OUT/'premier.txd'))
        check(len(decoded.native_textures)==3,'Independent DragonFF TXD parser accepts all textures')
        for tex in decoded.native_textures:
            for i in range(tex.num_levels):
                actual=bytes(tex.to_rgba(i)); expected=local[tex.name][i].tobytes()
                # DXT1 implementations differ by one level in RGB565 rounding.
                # Authored RGB888 pixels must agree exactly, at every mip.
                tolerance=0 if tex.name=='linden128' else 1
                check(len(actual)==len(expected) and max(abs(a-b) for a,b in zip(actual,expected))<=tolerance,
                      f'DragonFF pixel decode agrees within {tolerance}/255: {tex.name}, mip {i}')
        independent='DragonFF 54baca8ea2ed95fe5a86917f44399ce677379c59'
    report={'checks_passed':len(checks),'all_parts_triangles':total,
            'intact_visible_triangles_including_four_wheels':visible,
            'texture_dependencies':sorted(dependencies),
            'independent_parser':independent,
            'dff_sha256':hashlib.sha256(raw).hexdigest(),
            'txd_sha256':hashlib.sha256((OUT/'premier.txd').read_bytes()).hexdigest(),
            'game_test':'Not run: GTA SA runtime is not present in this environment',
            'checks':checks}
    (ROOT/'assets/validation_report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'{len(checks)} asset checks passed; {total} total triangles, {visible} intact visible triangles with four wheels.')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--dragonff')
    validate(parser.parse_args().dragonff)
