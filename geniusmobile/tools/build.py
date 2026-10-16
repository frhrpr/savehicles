"""Build the Geniusmobile from the supplied stock Picador.

python geniusmobile/tools/build.py --dragonff /tmp/savehicles-dragonff
Pillow and DragonFF's standalone COL module are the only dependencies.
"""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import math
import struct
import sys

from PIL import Image, ImageDraw

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parent
sys.path.insert(0, str(REPO / 'tools'))
import rw_dff as rw
sys.modules['dff'] = rw  # The user's original stripe helper imports this name.
sys.path.insert(0, str(BASE / 'tools'))
import stripes

VERSION = 0x1803FFFF
PAINT = bytes((60, 255, 0, 255))
BED = bytes((255, 0, 175, 255))
STRIPE = bytes((0, 255, 255, 255))
WHITE = bytes((255, 255, 255, 255))


def chunk(kind, data):
    return struct.pack('<III', kind, len(data), VERSION) + data


def set_texture(material, name):
    material.first(6).find(2)[0].data = name.encode().ljust(((len(name) + 4) // 4) * 4, b'\0')


def make_atlas():
    image = Image.new('RGB', (128, 128), (232, 232, 227))
    d = ImageDraw.Draw(image)
    # Top strip: recessed scoop mouth, coarse slats intentionally at SA scale.
    d.rectangle((0, 0, 127, 31), fill=(24, 26, 25))
    for y in range(3, 30, 5):
        d.line((3, y, 124, y), fill=(76, 79, 73))
        d.line((3, y + 1, 124, y + 1), fill=(38, 41, 38))
    for x in range(7, 126, 13):
        d.line((x, 2, x, 29), fill=(23, 27, 24))
    # Four swatches: clean paint modulation, brushed metal, rubber and tonneau.
    for y in range(36, 128):
        for x in range(128):
            n = ((x * 17 + y * 31) % 5) - 2
            if x < 32: color = (238+n, 238+n, 232+n)
            elif x < 64: color = (156+(y % 3)*8+n, 163+(y % 3)*8+n, 164+(y % 3)*8+n)
            elif x < 96: color = (38+n, 40+n, 39+n)
            else: color = (202+n, 204+n, 201+n)
            d.point((x, y), fill=color)
    # A small embossed detail for the cover latch, not a large badge panel.
    d.rectangle((100, 41, 122, 48), fill=(130, 136, 131))
    d.line((107, 45, 115, 45), fill=(33, 37, 34))
    (BASE / 'assets').mkdir(exist_ok=True)
    image.save(BASE / 'assets/genius_detail128.png')
    levels=[]
    level=image.convert('RGBA')
    while True:
        levels.append(level.tobytes('raw', 'BGRA'))
        if level.width == 1: break
        level=level.resize((level.width//2, level.height//2), Image.Resampling.BOX)
    native = struct.pack('<IHH32s32s', 9, 0x1106, 0, b'genius_detail128', b'')
    native += struct.pack('<IIHHBBBB', 0x8600, 22, 128, 128, 32, len(levels), 4, 0)
    native += b''.join(struct.pack('<I', len(p)) + p for p in levels)
    return chunk(0x15, chunk(1, native) + chunk(3, b''))


def make_txd(extra):
    original=(BASE / 'donor/picador.txd').read_bytes()
    end=12+struct.unpack_from('<I',original,4)[0]
    blocks=[]
    offset=12
    while offset<end:
        kind,size,version=struct.unpack_from('<III',original,offset)
        raw=original[offset:offset+12+size]
        if kind==1:
            n,device=struct.unpack_from('<HH',original,offset+12)
            raw=chunk(1,struct.pack('<HH',n+1,device))
        if kind==3: blocks.append(extra)
        blocks.append(raw);offset+=12+size
    return chunk(0x16,b''.join(blocks))


def normalized(v):
    length=math.sqrt(sum(c*c for c in v)) or 1
    return tuple(c/length for c in v)


def cross(a,b):
    return a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]


def opaque_first_binmesh(g, materials):
    """Serialize independently ordered batches; never sort only by material ID."""
    batches={}
    for a,b,c,m in g.tris: batches.setdefault(m,[]).extend((a,b,c))
    order=sorted(batches,key=lambda m:(rw.material_colour(materials[m])[3]<255,m))
    output=struct.pack('<III',0,len(order),sum(len(v) for v in batches.values()))
    for m in order:
        values=batches[m]
        output+=struct.pack('<II',len(values),m)+struct.pack('<'+'I'*len(values),*values)
    return output


class Part:
    def __init__(self, name, node, rotation, translation):
        self.name,self.node,self.rotation,self.translation=name,node,rotation,translation
        self.g=rw.Geometry(node.children[0].data)
        self.materials=node.first(8).find(7)
        self.original_vertices=len(self.g.pos)
        self.added_triangles=0
        self.cache={}
        self.deform=None

    def mat(self, kind):
        if kind in self.cache: return self.cache[kind]
        # Get a textured donor material, preserving vehicle paint effects for
        # paint channels while using plain surfaces for trim and intake recess.
        source=next(m for m in self.materials if m.find(6))
        mat=copy.deepcopy(source)
        color={'paint':PAINT,'bed':BED,'stripe':STRIPE,'chrome':WHITE,'rubber':WHITE,'intake':WHITE}[kind]
        rw.set_material_colour(mat,color)
        set_texture(mat,'genius_detail128')
        if kind in ['chrome','rubber','intake']:
            mat.children=[c for c in mat.children if c.type!=3]
            mat.children.append(rw.Chunk(3,VERSION,children=[]))
        self.node.first(8).children.append(mat)
        self.materials.append(mat)
        index=len(self.materials)-1
        self.cache[kind]=index
        return index

    def local(self, point):
        delta=tuple(a-b for a,b in zip(point,self.translation))
        return tuple(sum(delta[k]*self.rotation[j][k] for k in range(3)) for j in range(3))

    def world(self, point):
        return tuple(sum(point[k]*self.rotation[k][j] for k in range(3))+self.translation[j] for j in range(3))

    def normal_local(self, n):
        return tuple(sum(n[k]*self.rotation[j][k] for k in range(3)) for j in range(3))

    def face(self, points, kind, uvs=None, normal=None):
        if self.deform:
            points=[self.deform(p) for p in points]
        if normal is None:
            normal=normalized(cross(tuple(b-a for a,b in zip(points[0],points[1])),tuple(b-a for a,b in zip(points[0],points[2]))))
        if uvs is None:
            rect={'paint':(3,44,28,120),'stripe':(3,44,28,120),'chrome':(36,40,60,119),
                  'rubber':(70,44,88,120),'bed':(99,65,125,123),'intake':(2,2,125,30)}[kind]
            u0,v0,u1,v1=(a/128 for a in rect)
            uvs=[(u0,v1),(u1,v1),(u1,v0),(u0,v0)][:len(points)]
        ids=[]
        for p,uv in zip(points,uvs):
            ids.append(len(self.g.pos))
            self.g.pos.append(self.local(p))
            if self.g.nrm is not None: self.g.nrm.append(self.normal_local(normal))
            for layer in self.g.uvs: layer.append(uv)
            if self.g.prelit is not None: self.g.prelit.append(bytes((235,235,235,255)))
        for j in range(1,len(ids)-1):
            self.g.tris.append((ids[0],ids[j],ids[j+1],self.mat(kind)))
            self.added_triangles+=1

    def box(self, lo, hi, kind, top=True):
        x0,y0,z0=lo;x1,y1,z1=hi
        v=[(x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),
           (x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)]
        for face in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]:
            if not top and face==(4,5,6,7): continue
            self.face([v[i] for i in face],kind)

    def finalize(self):
        g=self.g
        # Clipping at a vertex can leave zero-area triangles. Discard those
        # rather than exporting invalid faces or relying on Blender to drop them.
        def valid(tri):
            a,b,c=[g.pos[i] for i in tri[:3]]
            v=cross(tuple(y-x for x,y in zip(a,b)),tuple(y-x for x,y in zip(a,c)))
            return sum(x*x for x in v)>1e-14
        g.tris=[t for t in g.tris if valid(t)]
        # Remove unreferenced vertices left by stripe splitting and discarded
        # donor clutter. Attribute arrays are remapped together.
        used=sorted({i for tri in g.tris for i in tri[:3]})
        mapping={i:j for j,i in enumerate(used)}
        g.pos=[g.pos[i] for i in used]
        if g.nrm is not None: g.nrm=[g.nrm[i] for i in used]
        if g.prelit is not None: g.prelit=[g.prelit[i] for i in used]
        g.uvs=[[layer[i] for i in used] for layer in g.uvs]
        g.tris=[tuple(mapping[i] for i in t[:3])+(t[3],) for t in g.tris]
        center=tuple((min(p[j] for p in g.pos)+max(p[j] for p in g.pos))/2 for j in range(3))
        radius=max(math.dist(p,center) for p in g.pos)+0.0001
        g.sphere=struct.pack('<4f',*center,radius)
        if any(rw.material_colour(m)[:3] in [PAINT[:3],BED[:3],STRIPE[:3]] for m in self.materials):
            # White/chrome donor bumpers do not originally need this flag.
            # Their new paint-channel trim does.
            g.flags |= 0x40
        self.node.children[0].data=g.pack()
        mlist=self.node.first(8)
        mlist.children[0].data=struct.pack('<I',len(self.materials))+struct.pack('<'+'i'*len(self.materials),*([-1]*len(self.materials)))
        for ext in self.node.find(3):
            for p in ext.children:
                if p.type==0x50e: p.data=opaque_first_binmesh(g,self.materials)
                elif p.type==0x253f2fd:
                    if p.data!=b'\0'*4: raise ValueError('Cannot remap non-empty breakable plugin')
                elif p.type==0x253f2f9:
                    raise ValueError('Unexpected night-colour payload needs explicit remapping')


def add_cover(part, lod=False):
    # The cover sits inside the original bed rails. Its rear edge clears the
    # tailgate, which remains a separate functioning/damageable component.
    x0,x1=-0.945,0.945;y0,y1=-2.575,-0.605
    z0,z1=0.285,0.333
    part.box((x0,y0,z0),(x1,y1,z1),'bed',top=False)
    # Split the top itself: no overlaid coplanar stripe polygons to z-fight.
    edges=[x0,-.29,-.05,.05,.29,x1]
    for i in range(5):
        a,b=edges[i:i+2]
        part.face([(a,y0,z1),(b,y0,z1),(b,y1,z1),(a,y1,z1)],'stripe' if i in [1,3] else 'bed')
    if not lod:
        # Fine side lips and a discreet polished rear edge.
        part.box((-.957,y0,.325),(-.94,y1,.345),'rubber')
        part.box((.94,y0,.325),(.957,y1,.345),'rubber')
        part.box((-.94,y0-.012,.323),(.94,y0,.344),'chrome')
        part.box((-.075,-2.50,.334),(.075,-2.455,.347),'chrome')


def add_scoop(part, damaged=False, lod=False):
    # A forward-facing, fitted ram-air scoop. Mouth and sides are real
    # geometry; the intake is backed instead of exposing the engine bay.
    dent = -0.035 if damaged else 0
    y0,y1,y2=1.10,1.38,2.15
    z0,z1,z2=.305,.455+dent,.535+dent
    width0,width1,width2=.34,.40,.44
    # Segmented top keeps both racing bands aligned to the original stripes.
    for ya,yb,za,zb,wa,wb in [(y0,y1,z0,z1,width0,width1),(y1,y2,z1,z2,width1,width2)]:
        breaks_a=[-wa,-.29,-.05,.05,.29,wa]
        breaks_b=[-wb,-.29,-.05,.05,.29,wb]
        for i in range(5):
            kind='stripe' if i in [1,3] else 'paint'
            part.face([(breaks_a[i],ya,za),(breaks_a[i+1],ya,za),
                       (breaks_b[i+1],yb,zb),(breaks_b[i],yb,zb)],kind)
    for sign in [-1,1]:
        points=[(sign*width0,y0,z0),(sign*width1,y1,z1),(sign*width2,y2,z2),
                (sign*.44,y2,.278),(sign*.34,y0,.278)]
        if sign>0: points.reverse()
        part.face(points,'paint')
    # Slightly recessed opaque grille is behind an open body-colour lip.
    part.face([(-.415,y2-.008,.30),(-.415,y2-.008,z2-.025),(.415,y2-.008,z2-.025),(.415,y2-.008,.30)],'intake')
    part.box((-.445,y2-.018,z2-.025),(.445,y2+.006,z2+.006),'paint')
    part.box((-.445,y2-.018,.278),(.445,y2+.006,.301),'paint')
    if not lod:
        for x in [-.442,.426]:
            part.box((x,y2-.018,.299),(x+.016,y2+.006,z2-.024),'paint')


def add_front_valance(part, damaged=False, lod=False):
    # Fits below the original bright bumper, leaving both number plates free.
    z=-.565 if not damaged else -.55
    xs=[-1.05,-.97,-.40,.40,.97,1.05]
    for i in range(len(xs)-1):
        x0,x1=xs[i:i+2]
        y0=2.86-.045*abs(x0);y1=2.86-.045*abs(x1)
        part.face(list(reversed([(x0,y0,z),(x1,y1,z),(x1,y1+.035,-.389),(x0,y0+.035,-.389)])),'paint')
    part.face(list(reversed([(-1.05,2.81,z),(-1.05,2.855,-.389),(-1.08,2.65,-.389),(-1.08,2.65,z)])),'paint')
    part.face(list(reversed([(1.05,2.81,z),(1.08,2.65,z),(1.08,2.65,-.389),(1.05,2.855,-.389)])),'paint')
    part.box((-.405,2.846,-.548),(.405,2.86,-.455),'intake')
    if not lod:
        part.box((-1.05,2.75,z-.018),(1.05,2.86,z),'rubber')


def add_sills(part, lod=False):
    for sign in [-1,1]:
        x=sign*1.105
        # Forward and rear tapers keep these between the wheel openings.
        points=[(x,-.89,-.50),(x,1.22,-.50),(sign*1.165,1.10,-.558),(sign*1.165,-.78,-.558)]
        if sign>0: points.reverse()
        part.face(points,'paint')
        points=[(sign*1.165,-.78,-.558),(sign*1.165,1.10,-.558),(sign*1.04,1.10,-.558),(sign*1.04,-.78,-.558)]
        if sign>0: points.reverse()
        part.face(points,'rubber')
        if not lod:
            part.box((min(x,sign*1.165),-.78,-.51),(max(x,sign*1.165),1.10,-.492),'paint')


def add_rear_valance(part, damaged=False, lod=False):
    z0=-.535 if not damaged else -.55
    part.box((-1.075,-2.825,z0),(1.075,-2.755,-.386),'paint')
    if not lod:
        part.box((-.48,-2.836,z0-.009),(.48,-2.825,-.432),'rubber')


def add_exhaust(part):
    # Two modest polished tips, with ring walls and a dark internal cap.
    part.g.tris=[]
    segments=10
    for center in [-.77,.77]:
        for i in range(segments):
            a,b=2*math.pi*i/segments,2*math.pi*(i+1)/segments
            point=lambda theta,y,r:(center+math.cos(theta)*r,y,-.465+math.sin(theta)*r)
            part.face(list(reversed([point(a,-2.80,.062),point(a,-2.98,.062),point(b,-2.98,.062),point(b,-2.80,.062)])),'chrome')
            part.face(list(reversed([point(a,-2.98,.062),point(a,-2.98,.043),point(b,-2.98,.043),point(b,-2.98,.062)])),'chrome')
            part.face(list(reversed([point(a,-2.98,.043),point(a,-2.88,.043),point(b,-2.88,.043),point(b,-2.98,.043)])),'rubber')
        ring=[(center+math.cos(2*math.pi*i/segments)*.043,-2.88,-.465+math.sin(2*math.pi*i/segments)*.043) for i in range(segments)]
        part.face(ring,'rubber',uvs=[(.6,.6)]*segments)


def extend_collision(clump, dragonff):
    sys.path.insert(0,str(Path(dragonff).resolve()))
    from gtaLib import col
    plugin=next(p for e in clump.find(3) for p in e.children if p.type==0x253f2fa)
    container=col.coll();container.load_memory(plugin.data)
    m=container.models[0]
    before={'spheres':len(m.spheres),'boxes':len(m.boxes),'faces':len(m.mesh_faces),'shadow_faces':len(m.shadow_faces)}
    m.model_name='geniusmb'
    boxes=[((-.945,-2.575,.285),(.945,-.605,.333),0),
           ((-1.05,2.72,-.583),(1.05,2.89,-.389),3),
           ((-1.075,-2.836,-.55),(1.075,-2.755,-.386),4),
           ((-1.165,-.78,-.558),(-1.04,1.10,-.492),0),
           ((1.04,-.78,-.558),(1.165,1.10,-.492),0)]
    def add_collision_box(lo,hi,component):
        m.boxes.append(col.TBox(lo,hi,col.TSurface(63,component,187,128)))
        # The cover and skirt physics also need a mesh for cameras/bullets.
        verts=[(lo[0],lo[1],lo[2]),(hi[0],lo[1],lo[2]),(hi[0],hi[1],lo[2]),(lo[0],hi[1],lo[2]),
               (lo[0],lo[1],hi[2]),(hi[0],lo[1],hi[2]),(hi[0],hi[1],hi[2]),(lo[0],hi[1],hi[2])]
        faces=[(0,3,2),(0,2,1),(4,5,6),(4,6,7),(0,1,5),(0,5,4),
               (1,2,6),(1,6,5),(2,3,7),(2,7,6),(3,0,4),(3,4,7)]
        base=len(m.mesh_verts);m.mesh_verts.extend(verts)
        m.mesh_faces.extend(col.TFace(a+base,b+base,c+base,63,128) for a,b,c in faces)
        # New volumes are closed shadow components; retain stock shell shadow.
        base=len(m.shadow_verts);m.shadow_verts.extend(verts)
        m.shadow_faces.extend(col.TFace(a+base,b+base,c+base,63,128) for a,b,c in faces)
    for lo,hi,component in boxes: add_collision_box(lo,hi,component)
    # Small scoop collider, backed by the stock bonnet's collision.
    m.boxes.append(col.TBox((-.44,1.38,.278),(.44,2.156,.541),col.TSurface(63,1,187,128)))
    m.face_groups=[]  # No stale face-group regions after adding geometry.
    lo=list(m.bounds.min);hi=list(m.bounds.max)
    for b in m.boxes:
        lo=[min(a,c) for a,c in zip(lo,b.min)];hi=[max(a,c) for a,c in zip(hi,b.max)]
    center=tuple((a+b)/2 for a,b in zip(lo,hi))
    radius=math.dist(lo,hi)/2+.001
    m.bounds=col.TBounds(tuple(lo),tuple(hi),center,radius)
    plugin.data=container.write_memory()
    return {'before':before,'after':{'spheres':len(m.spheres),'boxes':len(m.boxes),'faces':len(m.mesh_faces),'shadow_faces':len(m.shadow_faces)}}


def build(dragonff):
    (BASE/'dist').mkdir(exist_ok=True)
    original=(BASE/'donor/picador.dff').read_bytes()
    # Existing user-authored stripe operation; authored additions use colour 3
    # directly. Draw order is corrected independently after all modifications.
    modified,stripe_counts=stripes.stripes(original,no_extras=True)
    clump=rw.load(modified)[0]
    frames=rw.frames(clump)
    rootname=clump.first(14).find(3)[0].first(0x253f2fe)
    rootname.data=b'geniusmb'
    geometry_nodes=clump.first(26).find(15)
    # Drop the unused extra geometries and reindex atomics; keep their named
    # frames so existing mission visibility calls remain harmless.
    used=sorted({struct.unpack_from('<II',a.children[0].data)[1] for a in clump.find(20)})
    remap={old:new for new,old in enumerate(used)}
    glist=clump.first(26)
    glist.children=[glist.children[0]]+[geometry_nodes[i] for i in used]
    glist.children[0].data=struct.pack('<I',len(used))
    for atomic in clump.find(20):
        raw=bytearray(atomic.children[0].data);fi,gi=struct.unpack_from('<II',raw)
        struct.pack_into('<II',raw,0,fi,remap[gi]);atomic.children[0].data=bytes(raw)
    geometry_nodes=glist.find(15)
    # Transfer the donor bonnet's actual dent displacement to the new scoop.
    # Sampling the original surfaces keeps its base attached when damage swaps
    # the bonnet, instead of leaving a pristine scoop floating over a dent.
    hood_surfaces={}
    for atomic in clump.find(20):
        fi,gi=struct.unpack_from('<II',atomic.children[0].data)
        name=frames[fi][0]
        if name not in ['bonnet_ok','bonnet_dam']: continue
        r,p=rw.frame_to_root(frames,fi)
        geom=rw.Geometry(geometry_nodes[gi].children[0].data)
        positions=[tuple(sum(v[k]*r[k][j] for k in range(3))+p[j] for j in range(3)) for v in geom.pos]
        hood_surfaces[name]=(positions,geom.tris)
    def height(name,x,y):
        points,triangles=hood_surfaces[name]
        values=[]
        for ia,ib,ic,mi in triangles:
            a,b,c=points[ia],points[ib],points[ic]
            den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
            if abs(den)<1e-10: continue
            u=((b[1]-c[1])*(x-c[0])+(c[0]-b[0])*(y-c[1]))/den
            v=((c[1]-a[1])*(x-c[0])+(a[0]-c[0])*(y-c[1]))/den
            if min(u,v,1-u-v)>=-1e-5: values.append(u*a[2]+v*b[2]+(1-u-v)*c[2])
        if values: return max(values)
        return min(points,key=lambda p:(p[0]-x)**2+(p[1]-y)**2)[2]
    def damaged_scoop(point):
        x,y,z=point
        return x,y,z+height('bonnet_dam',x,y)-height('bonnet_ok',x,y)
    stats=[]
    for atomic in clump.find(20):
        fi,gi=struct.unpack_from('<II',atomic.children[0].data)
        name=frames[fi][0]
        r,p=rw.frame_to_root(frames,fi)
        part=Part(name,geometry_nodes[gi],r,p)
        before=len(part.g.tris)
        if name=='chassis': add_cover(part);add_sills(part)
        elif name=='chassis_vlo':
            part.g.tris=[t for t in part.g.tris if not any(part.world(part.g.pos[i])[2]>.82 for i in t[:3])]
            add_cover(part,True);add_sills(part,True)
            add_scoop(part,lod=True);add_front_valance(part,lod=True);add_rear_valance(part,lod=True)
        elif name in ['bonnet_ok','bonnet_dam']:
            if name=='bonnet_dam': part.deform=damaged_scoop
            add_scoop(part)
        elif name in ['bump_front_ok','bump_front_dam']: add_front_valance(part,name.endswith('_dam'))
        elif name in ['bump_rear_ok','bump_rear_dam']: add_rear_valance(part,name.endswith('_dam'))
        elif name=='exhaust_ok': add_exhaust(part)
        part.finalize()
        stats.append({'part':name,'before_additions':before,'triangles':len(part.g.tris),'vertices':len(part.g.pos)})
    # Shift the exhaust particle point and the nitro bottle mount. Lamps,
    # hinges, wheel dummies and the other mounts stay at their donor positions.
    frame_struct=clump.first(14).children[0]
    raw=bytearray(frame_struct.data)
    exhaust_index=next(i for i,f in enumerate(frames) if f[0]=='exhaust')
    struct.pack_into('<3f',raw,4+56*exhaust_index+36,.77,-2.98,-.465)
    # Tuck the retained nitro upgrade inside the now-covered bed.
    nitro_index=next(i for i,f in enumerate(frames) if f[0]=='ug_nitro')
    struct.pack_into('<3f',raw,4+56*nitro_index+36,0,-1.55,.035)
    frame_struct.data=bytes(raw)
    collision_report=extend_collision(clump,dragonff)
    model=rw.write([clump])
    texture=make_txd(make_atlas())
    (BASE/'dist/geniusmb.dff').write_bytes(model)
    (BASE/'dist/geniusmb.txd').write_bytes(texture)
    report={'model':'geniusmb','donor':'picador','donor_sha256':hashlib.sha256(original).hexdigest(),
            'dff_sha256':hashlib.sha256(model).hexdigest(),'txd_sha256':hashlib.sha256(texture).hexdigest(),
            'stored_triangles':sum(s['triangles'] for s in stats),'stripe_pieces':stripe_counts,
            'collision':collision_report,'parts':stats,'texture':{'name':'genius_detail128','size':[128,128],'mip_levels':8}}
    (BASE/'assets/build_report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='parts'},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--dragonff',required=True)
    build(parser.parse_args().dragonff)
