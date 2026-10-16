"""Inspect the exported files with a separate batch parser and DragonFF.

This checks game-specific draw order rather than reproducing the builder's
serialization. It also exercises the new bed-cover collision with a ray probe.
"""
from pathlib import Path
import argparse
from collections import Counter
import hashlib
import json
import math
import re
import struct
import sys

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE.parent/'tools'))
import rw_dff as rw
from txd_textures import read_txd, chunks


def batch_order(node):
    mats=node.first(8).find(7)
    rows=[]
    for ext in node.find(3):
        for plugin in ext.children:
            if plugin.type!=0x50e: continue
            kind,count,total=struct.unpack_from('<III',plugin.data)
            pos=12;read=0
            for _ in range(count):
                n,mi=struct.unpack_from('<II',plugin.data,pos);pos+=8
                indices=struct.unpack_from('<'+'I'*n,plugin.data,pos);pos+=4*n
                rows.append((mi,rw.material_colour(mats[mi])[3],indices));read+=n
            if read!=total or pos!=len(plugin.data):raise ValueError('BinMesh length/count mismatch')
    return rows


def alpha_order_valid(rows):
    seen_transparent=False
    for material,alpha,indices in rows:
        if alpha<255: seen_transparent=True
        elif seen_transparent:return False
    return True


def load(path):return rw.load(path.read_bytes())[0]


def extras_have_atomics(clump):
    attached={struct.unpack_from('<I',atomic.children[0].data)[0] for atomic in clump.find(20)}
    return all(i in attached for i,frame in enumerate(rw.frames(clump))
               if re.fullmatch(r'extra\d+',frame[0],re.IGNORECASE))


def validate(dragonff):
    checks=[]
    def check(value,label):
        if not value:raise AssertionError(label)
        checks.append(label)
    sys.path.insert(0,str(Path(dragonff).resolve()))
    from gtaLib import dff,txd,col
    model=BASE/'dist/geniusmb.dff';texture=BASE/'dist/geniusmb.txd'
    c=load(model);old=load(BASE/'donor/picador.dff')
    frames=rw.frames(c);original_frames=rw.frames(old)
    check(frames[0][0]=='geniusmb','Root frame uses the new model name')
    check(len(frames)==len(original_frames)==53,'All 53 donor frames retained')
    check(extras_have_atomics(c),'Every retained extraN frame has an attached atomic for SA loading')
    # The original donor is valid; detaching one of its extra atomics must
    # make the check fail. This models PreprocessHierarchy's null-atomic case.
    import copy
    regression=copy.deepcopy(old)
    extra_index=next(i for i,f in enumerate(original_frames) if f[0]=='extra1')
    regression.children=[a for a in regression.children if not
                         (a.type==20 and struct.unpack_from('<I',a.children[0].data)[0]==extra_index)]
    check(extras_have_atomics(old) and not extras_have_atomics(regression),
          'Extras regression accepts stock Picador and rejects an extra frame with its atomic removed')
    for i,(a,b) in enumerate(zip(frames,original_frames)):
        check(a[3]==b[3] and a[1]==b[1],f'{a[0]}: original parent and basis retained')
        if i and a[0] not in ['exhaust','ug_nitro']:
            expected_name=('cargo_removed_'+str(i)) if b[0] in ['extra1','extra2'] else b[0]
            check(a[0]==expected_name and a[2]==b[2],f'{a[0]}: safe name and original position retained')
    nodes=c.first(26).find(15)
    check(len(nodes)==22 and len(c.find(20))==22,'Only 22 used geometries and atomics, no bed-clutter atomics')
    parts={}
    all_triangles=0;visible=0;dependencies=set();transparent_count=0
    light_tags=[bytes(v) for v in [(255,175,0),(0,255,200),(185,255,0),(255,60,0)]]
    paint_tags=[bytes(v) for v in [(60,255,0),(255,0,175),(0,255,255)]]
    for atomic in c.find(20):
        fi,gi=struct.unpack_from('<II',atomic.children[0].data)
        name=frames[fi][0];node=nodes[gi];g=rw.Geometry(node.children[0].data);mats=node.first(8).find(7)
        parts[name]=(g,node,fi)
        check(not name.startswith('extra'),'No visible optional cargo load: '+name)
        check(0<len(g.pos)<65536 and all(math.isfinite(v) for p in g.pos for v in p),name+': finite, indexable positions')
        check(all(0<=m<len(mats) and all(0<=i<len(g.pos) for i in [a,b,cc]) for a,b,cc,m in g.tris),name+': valid triangle/material indices')
        check(g.nrm is not None and len(g.nrm)==len(g.pos),name+': normal attribute count')
        check(all(abs(math.sqrt(sum(v*v for v in n))-1)<.02 for n in g.nrm),name+': normalized surface normals')
        check(all(len(u)==len(g.pos) for u in g.uvs) and bool(g.uvs),name+': complete UV attributes')
        if g.prelit:check(len(g.prelit)==len(g.pos),name+': complete vertex colours')
        x,y,z,r=struct.unpack('<4f',g.sphere)
        check(all(math.dist(p,(x,y,z))<=r+1e-5 for p in g.pos),name+': bounding sphere includes all vertices')
        batches=batch_order(node)
        check(alpha_order_valid(batches),name+': opaque batches precede every transparent batch')
        transparent_count+=any(a<255 for m,a,ids in batches)
        expected=Counter((a,b,cc,m) for a,b,cc,m in g.tris)
        actual=Counter()
        for mi,alpha,indices in batches:
            check(len(indices)%3==0,name+': triangle-list batch index count')
            for k in range(0,len(indices),3):actual[tuple(indices[k:k+3])+(mi,)]+=1
        check(actual==expected,name+': independently parsed BinMesh matches geometry triangles')
        if any(rw.material_colour(m)[:3] in paint_tags for m in mats):
            check(bool(g.flags&0x40),name+': material colour modulation enabled for paint')
        for mat in mats:
            if mat.find(6):dependencies.add(mat.first(6).find(2)[0].data.rstrip(b'\0').decode())
        all_triangles+=len(g.tris)
        if not name.endswith('_dam') and name!='chassis_vlo':visible+=len(g.tris)*(4 if name=='wheel' else 1)
    check({'bonnet_ok','bonnet_dam','boot_ok','boot_dam','door_lf_ok','door_lf_dam','door_rf_ok','door_rf_dam','chassis_vlo'}<=set(parts),'Required moving/damage/LOD parts present')
    for name in ['chassis','chassis_vlo','bonnet_ok','bonnet_dam','boot_ok','boot_dam']:
        g,n,fi=parts[name];mats=n.first(8).find(7)
        colors={rw.material_colour(m)[:3] for m in mats}
        check(bytes((0,255,255)) in colors,name+': colour-3 racing stripes retained')
    for name in ['chassis','chassis_vlo']:
        g,n,fi=parts[name]
        colors={rw.material_colour(m)[:3] for m in n.first(8).find(7)}
        check(bytes((255,0,175)) in colors,name+': colour-2 bed cover retained')
    check(max(p[2] for p in parts['chassis_vlo'][0].pos)<.82,'LOD has no tall optional bed clutter')
    original_chassis=next((rw.Geometry(old.first(26).find(15)[struct.unpack_from('<II',a.children[0].data)[1]].children[0].data),old.first(26).find(15)[struct.unpack_from('<II',a.children[0].data)[1]]) for a in old.find(20) if original_frames[struct.unpack_from('<II',a.children[0].data)[0]][0]=='chassis')
    def tagged_materials(node):
        return [(rw.material_colour(m),m.first(6).find(2)[0].data) for m in node.first(8).find(7) if rw.material_colour(m)[:3] in light_tags]
    check(tagged_materials(parts['chassis'][1])==tagged_materials(original_chassis[1]),'All four original lamp materials, alpha values and texture names retained')
    # The original geometry/material vertices of the lamps are untouched. They
    # may be reindexed by compaction; compare by their attribute tuples instead.
    def lamp_faces(g,node):
        tags={i for i,m in enumerate(node.first(8).find(7)) if rw.material_colour(m)[:3] in light_tags}
        return Counter(tuple((g.pos[i],g.nrm[i],tuple(u[i] for u in g.uvs)) for i in t[:3])+(t[3],) for t in g.tris if t[3] in tags)
    check(lamp_faces(parts['chassis'][0],parts['chassis'][1])==lamp_faces(*original_chassis),'Lamp faces, UVs and normals unchanged from the stock Picador')
    local=read_txd(texture);shared=read_txd(BASE/'donor/vehicle.txd')
    check(dependencies<=set(local)|set(shared),'Every texture dependency resolves')
    check(local['genius_detail128'][0].size==(128,128) and len(local['genius_detail128'])==8,'Custom 128px atlas has eight mip levels')
    parsed=dff.dff();parsed.load_file(str(model))
    check(len(parsed.clumps)==1 and len(parsed.clumps[0].geometry_list)==22,'Independent DragonFF import accepts all game model parts')
    tex=txd.txd();tex.load_file(str(texture))
    check(len(tex.native_textures)==3,'Independent DragonFF import accepts all three textures')
    for teximage in tex.native_textures:
        for i in range(teximage.num_levels):
            a=bytes(teximage.to_rgba(i));b=local[teximage.name][i].tobytes()
            tolerance=0 if teximage.name=='genius_detail128' else 1
            check(len(a)==len(b) and max(abs(x-y) for x,y in zip(a,b))<=tolerance,teximage.name+f': mip {i} independently decoded')
    coll=col.coll();coll.load_memory(parsed.clumps[0].collisions[0].data)
    cm=coll.models[0]
    check(cm.version==3 and cm.model_name=='geniusmb','Embedded COL3 has the new model name')
    check(len(cm.spheres)==32 and len(cm.boxes)==6 and len(cm.mesh_faces)==72,'Original component spheres plus fitted new physical volumes')
    check(len(cm.shadow_faces)==296,'Shadow mesh includes the five new closed volumes')
    check(all(0<=i<len(cm.mesh_verts) for f in cm.mesh_faces for i in f[:3]),'Collision mesh indices valid')
    check(all(0<=i<len(cm.shadow_verts) for f in cm.shadow_faces for i in f[:3]),'Shadow mesh indices valid')
    check(all(all(cm.bounds.min[j]-.009<=p[j]<=cm.bounds.max[j]+.009 for j in range(3)) for p in cm.mesh_verts),'Rebuilt collision bounds include the collision mesh')
    # A vertical point probe through the closed bed must hit the new lid.
    hits=[]
    for face in cm.mesh_faces:
        a,b,cc=[cm.mesh_verts[i] for i in face[:3]]
        x,y=0,-1.5
        den=(b[1]-cc[1])*(a[0]-cc[0])+(cc[0]-b[0])*(a[1]-cc[1])
        if abs(den)<1e-10:continue
        u=((b[1]-cc[1])*(x-cc[0])+(cc[0]-b[0])*(y-cc[1]))/den
        v=((cc[1]-a[1])*(x-cc[0])+(a[0]-cc[0])*(y-cc[1]))/den
        if min(u,v,1-u-v)>=-1e-6:hits.append(u*a[2]+v*b[2]+(1-u-v)*cc[2])
    check(any(abs(z-.333)<.009 for z in hits),'Vertical bed probe hits the new cover at its visible height')
    for box in cm.boxes:
        check(all(a<b for a,b in zip(box.min,box.max)),'Collision box has positive dimensions')
    # Each authored shadow box is closed after the exported quantization.
    for start in range(236,296,12):
        edges=Counter()
        for face in cm.shadow_faces[start:start+12]:
            a,b,cc=face[:3]
            for p,q in [(a,b),(b,cc),(cc,a)]:edges[tuple(sorted((p,q)))]+=1
        check(all(n==2 for n in edges.values()),f'New shadow component at face {start} is closed')
    previous=BASE.parent/'dist/modloader/linden/premier.dff'
    if previous.exists():
        broken=load(previous).first(26).find(15)[1]
        check(not alpha_order_valid(batch_order(broken)),'Draw-order regression check rejects the old Linden chassis')
    from fit_checks import check_fit
    check_fit(c,old,check)
    check(all_triangles<=5400 and visible<=4300,'Geometry stays within the chosen tuned-Picador budget')
    report={'revision':2,'checks_passed':len(checks),'stored_triangles':all_triangles,'intact_visible_triangles_four_stock_wheels':visible,
            'transparent_geometries':transparent_count,'draw_order':'all opaque batches before transparent batches',
            'dff_sha256':hashlib.sha256(model.read_bytes()).hexdigest(),'txd_sha256':hashlib.sha256(texture.read_bytes()).hexdigest(),
            'runtime_tests':'Pending: user tests in GTA SA 1.0 US / SilentPatch',
            'checks':checks}
    (BASE/'assets/validation_report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'PASS: {len(checks)} checks; {all_triangles} stored triangles; {visible} intact visible triangles including four stock wheels.')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--dragonff',required=True)
    validate(p.parse_args().dragonff)
