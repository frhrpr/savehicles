"""Independent exported-file and fit checks. GTA runtime validation is separate."""
from pathlib import Path
from collections import Counter
import argparse
import hashlib
import json
import math
import re
import struct
import sys
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE.parent/'tools'))
import rw_dff as rw
from txd_textures import read_txd


def batches(node):
    plugin=next(p for ext in node.find(3) for p in ext.children if p.type==0x50e)
    raw=plugin.data;flags,n,total=struct.unpack_from('<III',raw);offset=12;rows=[]
    if flags!=0:raise ValueError('Expected triangle lists')
    for _ in range(n):
        count,material=struct.unpack_from('<II',raw,offset);offset+=8
        values=struct.unpack_from('<'+'I'*count,raw,offset);offset+=count*4
        rows.append((material,values))
    if offset!=len(raw) or sum(len(v) for m,v in rows)!=total:raise ValueError('BinMesh count mismatch')
    return rows


def validate(dragonff):
    checks=[]
    def check(value,label):
        if not value:raise AssertionError(label)
        checks.append(label)
    sys.path.insert(0,str(Path(dragonff).resolve()))
    from gtaLib import dff,txd,col
    model=BASE/'dist/pip660.dff';texture=BASE/'dist/pip660.txd'
    raw=model.read_bytes();c=rw.load(raw)[0];donor=rw.load((BASE/'donor/manana.dff').read_bytes())[0]
    fs=rw.frames(c);oldfs=rw.frames(donor);nodes=c.first(26).find(15)
    check(rw.write([c])==raw,'Lossless DFF chunk round trip')
    check(len(fs)==46 and len(nodes)==len(c.find(20))==18,'All 46 rig frames and 18 atomics retained')
    check(fs[0][0]=='pip660','Independent model root name')
    check(all(a[1]==b[1] and a[3]==b[3] for a,b in zip(fs,oldfs)),'Original rig bases and parent indices retained')
    check([a.children[0].data for a in c.find(20)]==[a.children[0].data for a in donor.find(20)],'Original atomic/frame bindings and render flags retained')
    attached={struct.unpack_from('<I',a.children[0].data)[0] for a in c.find(20)}
    check(all(i in attached for i,f in enumerate(fs) if re.fullmatch(r'extra\d+',f[0],re.I)),'No atomic-less extraN frames for SA preprocessing')
    check(not any(f[0].startswith('ug_') for f in fs),'Old Manana upgrades cannot attach at incompatible mounts')
    parts={};dependencies=set();visible=0;stored=0;global_points=[]
    for atomic in c.find(20):
        fi,gi=struct.unpack_from('<II',atomic.children[0].data);name=fs[fi][0]
        node=nodes[gi];g=rw.Geometry(node.children[0].data);materials=node.first(8).find(7)
        r,p=rw.frame_to_root(fs,fi)
        points=[tuple(sum(v[k]*r[k][j] for k in range(3))+p[j] for j in range(3)) for v in g.pos]
        parts[name]=(g,node,points,fi)
        check(rw.write([node])!=rw.write([donor.first(26).find(15)[gi]]),name+': independently authored geometry replaces reference mesh')
        check(0<len(g.pos)<65536 and all(math.isfinite(v) for p in g.pos for v in p),name+': finite indexable positions')
        check(all(0<=m<len(materials) and all(0<=i<len(g.pos) for i in (a,b,d)) for a,b,d,m in g.tris),name+': valid vertex/material indices')
        check(len(g.nrm)==len(g.pos) and all(abs(math.sqrt(sum(x*x for x in n))-1)<.015 for n in g.nrm),name+': complete normalized normals')
        check(len(g.uvs)==1 and len(g.uvs[0])==len(g.pos) and len(g.prelit)==len(g.pos),name+': complete UV and prelight arrays')
        check(all(math.isfinite(v) for uv in g.uvs[0] for v in uv),name+': finite UV coordinates')
        def area(t):
            a,b,d=[g.pos[i] for i in t[:3]];u=[b[j]-a[j] for j in range(3)];v=[d[j]-a[j] for j in range(3)]
            return sum(x*x for x in (u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]))
        check(all(area(t)>1e-14 for t in g.tris),name+': no degenerate triangles')
        x,y,z,radius=struct.unpack('<4f',g.sphere)
        check(all(math.dist((x,y,z),p)<=radius+1e-5 for p in g.pos),name+': sphere encloses geometry')
        check(bool(g.flags&0x40),name+': material colour modulation enabled')
        expected=Counter(g.tris);actual=Counter();transparent=False
        for mi,values in batches(node):
            alpha=rw.material_colour(materials[mi])[3]
            check(not transparent or alpha<255,name+': no opaque batch after transparency')
            transparent|=alpha<255
            check(len(values)%3==0,name+': BinMesh triangle-list count')
            actual.update(tuple(values[k:k+3])+(mi,) for k in range(0,len(values),3))
        check(actual==expected,name+': independently parsed draw batches match faces')
        for a,b,d,mi in g.tris:
            if rw.material_colour(materials[mi])[3]>=255:continue
            normal=g.nrm[a]
            center=tuple((points[a][j]+points[b][j]+points[d][j])/3 for j in range(3))
            check(normal[0]*center[0]+normal[1]*center[1]>.01,
                  name+': transparent exterior faces outward for game backface culling')
        for mat in materials:
            if mat.find(6):dependencies.add(mat.first(6).find(2)[0].data.rstrip(b'\0').decode())
        stored+=len(g.tris)
        if not name.endswith('_dam') and name!='chassis_vlo':
            visible+=len(g.tris)*(4 if name=='wheel' else 1);global_points.extend(points)
    check(stored<3500 and visible<2600,'Stock-scale city-car polygon budget')
    names={f[0]:i for i,f in enumerate(fs)}
    for name,target in [('wheel_rf_dummy',(.625,.96,-.32)),('wheel_rb_dummy',(.625,-.96,-.32)),('ped_frontseat',(.32,-.14,-.065)),('boot_dummy',(0,-.92,.98)),('bonnet_dummy',(0,.665,.335))]:
        check(math.dist(rw.frame_to_root(fs,names[name])[1],target)<1e-5,name+': mount matches new city-car dimensions')
    wheel=parts['wheel'][0]
    check(abs(max(math.hypot(p[1],p[2]) for p in wheel.pos)-.29)<1e-5,'Wheel diameter matches the 0.58 IDE scale')
    check(abs(max(p[2] for p in global_points)-min(p[2] for p in global_points)-1.715)<.005,'New tall cabin has the intended height')
    check(max(p[1] for p in global_points)-min(p[1] for p in global_points)<3.15,'Short body has under 3.15m overall length')
    # Hinge clearance uses the EXPORTED sill, not the builder control points.
    chassis=parts['chassis'][2]
    sill=max(p[2] for p in chassis if -.61<p[1]<.61 and .68<abs(p[0])<.69 and p[2]<-.42)
    for name in ['door_lf_ok','door_rf_ok','door_lf_dam','door_rf_dam']:
        points=parts[name][2]
        check(min(p[2] for p in points)>sill+.006,name+': clears sill throughout vertical-axis swing')
        hinge=rw.frame_to_root(fs,parts[name][3])[1]
        check(max(p[1] for p in points)<=hinge[1]+.001,name+': all door skin lies behind its front hinge')
    for name in ['bonnet','boot','bump_front','bump_rear','door_lf','door_rf']:
        check(parts[name+'_ok'][0].pos!=parts[name+'_dam'][0].pos,name+': real damaged geometry differs from intact part')
    # Cast through both bonnet skins: an undeformed flat liner can otherwise
    # protrude through the dent while remaining a perfectly valid DFF.
    for name in ['bonnet_ok','bonnet_dam']:
        g,n,points,_=parts[name];mats=n.first(8).find(7)
        for x,y in [(0,1.20),(.20,1.10),(-.20,1.10)]:
            paint=[];lining=[]
            for a,b,d,mi in g.tris:
                p,q,r=[points[i] for i in (a,b,d)]
                den=(q[1]-r[1])*(p[0]-r[0])+(r[0]-q[0])*(p[1]-r[1])
                if abs(den)<1e-10:continue
                u=((q[1]-r[1])*(x-r[0])+(r[0]-q[0])*(y-r[1]))/den
                v=((r[1]-p[1])*(x-r[0])+(p[0]-r[0])*(y-r[1]))/den
                if min(u,v,1-u-v)<-1e-6:continue
                z=u*p[2]+v*q[2]+(1-u-v)*r[2]
                (paint if rw.material_colour(mats[mi])[:3]==bytes((60,255,0)) else lining).append(z)
            check(paint and lining and .020<max(paint)-max(lining)<.030,
                  f'{name}: inner lining stays below paint at {x}, {y}')
    # Four exact engine lamp tags, separated left/right, with stock shared map.
    lights={(255,175,0):-1,(0,255,200):1,(185,255,0):-1,(255,60,0):1}
    g,n,points,_=parts['chassis'];mats=n.first(8).find(7)
    for rgb,sign in lights.items():
        indices=[i for i,m in enumerate(mats) if rw.material_colour(m)[:3]==bytes(rgb)]
        check(len(indices)==1,'Unique engine lamp tag '+str(rgb))
        mi=indices[0];mat=mats[mi];vertices={v for t in g.tris if t[3]==mi for v in t[:3]}
        check(vertices and all(points[i][0]*sign>0 for i in vertices),'Lamp control tag lies on correct side '+str(rgb))
        check(rw.material_colour(mat)[3]==255 and mat.first(6).find(2)[0].data.rstrip(b'\0')==b'vehiclelights128','Opaque backed lens uses stock switchable light map '+str(rgb))
    # A lit headlamp lens must face OUTWARD, irrespective of preview backfaces.
    for a,b,d,mi in g.tris:
        color=rw.material_colour(mats[mi])[:3]
        if color not in [bytes(t) for t in lights]:continue
        p,q,r=[points[i] for i in (a,b,d)];u=[q[j]-p[j] for j in range(3)];v=[r[j]-p[j] for j in range(3)]
        normal_y=u[2]*v[0]-u[0]*v[2]
        check(normal_y*(1 if color in [bytes((255,175,0)),bytes((0,255,200))] else -1)>0,'Lamp lens triangle faces outside the car')
    local=read_txd(texture);shared=read_txd(BASE/'donor/vehicle.txd')
    check(dependencies<=set(local)|set(shared),'All texture dependencies resolve in local/shared dictionaries')
    check(set(local)=={'pip_detail128'} and local['pip_detail128'][0].size==(128,128) and len(local['pip_detail128'])==8,'One custom 128px texture with eight mips')
    native=txd.txd();native.load_file(str(texture));tex=native.native_textures[0]
    for i in range(tex.num_levels):check(bytes(tex.to_rgba(i))==local[tex.name][i].tobytes(),f'Independent texture decode agrees at mip {i}')
    parsed=dff.dff();parsed.load_file(str(model))
    check(len(parsed.clumps)==1 and len(parsed.clumps[0].geometry_list)==18,'DragonFF independently reads all 18 game geometries')
    coll=col.coll();coll.load_memory(parsed.clumps[0].collisions[0].data);cm=coll.models[0]
    check(cm.version==3 and cm.model_name=='pip660','New embedded COL3 matches model name')
    check(len(cm.mesh_faces)==36 and len(cm.shadow_faces)==36,'New collider and shadow use the compact car profile')
    check({s.surface.flags for s in cm.spheres}=={1,2,3,4,5,6},'All six moving body damage regions have component spheres')
    for points,faces,label in [(cm.mesh_verts,cm.mesh_faces,'collision'),(cm.shadow_verts,cm.shadow_faces,'shadow')]:
        edges=Counter()
        check(all(0<=i<len(points) for f in faces for i in f[:3]),label+': valid triangle indices')
        for a,b,d,*_ in faces:
            for i,j in [(a,b),(b,d),(d,a)]:edges[tuple(sorted((i,j)))]+=1
        check(all(count==2 for count in edges.values()),label+': watertight closed shell')
        check(all(cm.bounds.min[j]-.009<=p[j]<=cm.bounds.max[j]+.009 for p in points for j in range(3)),label+': all vertices inside bounds')
    check(all(cm.bounds.min[j]-.001<=s.center[j]-s.radius and s.center[j]+s.radius<=cm.bounds.max[j]+.001 for s in cm.spheres for j in range(3)),'Collision bounds include every damage sphere')
    check(all(math.dist(p,cm.bounds.center)<=cm.bounds.radius+.001 for p in [cm.bounds.min,cm.bounds.max]),'Collision bounding sphere includes full bounding box')
    report={'model':'pip660','checks_passed':len(checks),'stored_triangles':stored,'visible_triangles_four_wheels':visible,
            'dff_sha256':hashlib.sha256(raw).hexdigest(),'txd_sha256':hashlib.sha256(texture.read_bytes()).hexdigest(),
            'runtime':'Not tested in GTA; user runtime checks remain pending','checks':checks}
    (BASE/'assets/validation_report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'PASS: {len(checks)} asset checks; {visible} visible / {stored} stored triangles.')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--dragonff',required=True);validate(p.parse_args().dragonff)
