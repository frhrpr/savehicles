"""Build a stock-scale, Premier-derived GTA SA vehicle MVP.

Run from any working directory: python tools/build_linden.py
Only Python's standard library and Pillow are needed. References are extracted
from the supplied ZIP. No game data or global textures are modified.
"""
from pathlib import Path
import copy
import hashlib
import json
import math
import struct
import zipfile

from PIL import Image, ImageDraw
import rw_dff as rw

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / 'reference/gtasa_vehicle_reference'
OUT = ROOT / 'dist/modloader/linden'
TEX = ROOT / 'assets/textures'
VER = 0x1803FFFF


def extract():
    with zipfile.ZipFile(ROOT / 'vehicle_reference.zip') as archive:
        base = (ROOT / 'reference').resolve()
        for entry in archive.infolist():
            target = (base / entry.filename).resolve()
            if not target.is_relative_to(base):
                raise ValueError('Unsafe reference ZIP path')
            if entry.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            elif not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(entry))


def chunk(kind, body):
    return struct.pack('<III', kind, len(body), VER) + body


def atlas():
    """128px authored diffuse atlas; intentionally no PBR/normal maps."""
    image = Image.new('RGB', (128, 128), (43, 44, 42))
    d = ImageDraw.Draw(image)
    # Recessed grille: shaded slats, slim brightwork, a tiny diamond emblem.
    d.rectangle((0, 0, 127, 31), fill=(27, 29, 28))
    d.rectangle((2, 2, 125, 29), outline=(119, 126, 123))
    for y in (6, 11, 16, 21, 26):
        d.line((4, y, 123, y), fill=(103, 110, 106), width=1)
        d.line((4, y+1, 123, y+1), fill=(48, 52, 49), width=1)
    for x in (27, 49, 78, 100):
        d.line((x, 4, x, 28), fill=(35, 38, 36))
    d.rectangle((58, 7, 69, 25), fill=(31, 39, 35))
    d.polygon(((64,9),(68,16),(64,23),(60,16)), fill=(165,174,157))
    d.line((64,12,64,19,66,19),fill=(40,55,45))
    # Rear centre garnish; simple original pixel lettering at native resolution.
    d.rectangle((0, 34, 127, 57), fill=(37, 40, 38))
    d.line((2,35,125,35),fill=(128,137,129))
    glyphs = {'L':['100','100','100','100','111'],
              'I':['111','010','010','010','111'],
              'N':['1001','1101','1011','1001','1001'],
              'D':['110','101','101','101','110'],
              'E':['111','100','110','100','111'],
              '1':['010','110','010','010','111'],
              '8':['111','101','111','101','111'],
              '0':['111','101','101','101','111']}
    def text(x,y,s,col):
        for char in s:
            if char==' ': x+=3; continue
            glyph=glyphs[char]
            for iy,row in enumerate(glyph):
                for ix,bit in enumerate(row):
                    if bit=='1': d.point((x+ix,y+iy),fill=col)
            x+=len(glyph[0])+2
    text(12,43,'L I N D E N',(168,179,168))
    text(102,43,'1800',(154,164,154))
    # Plastic and brushed-metal swatches, padded for bilinear filtering.
    for y in range(64, 96):
        for x in range(66, 96):
            n=((x*13+y*7)%7)-3
            d.point((x,y),fill=(42+n,44+n,42+n))
    d.rectangle((100,64,127,95), fill=(158,166,161))
    d.rectangle((100,66,127,69), fill=(196,201,194))
    # Twelve-slot, period-correct stamped wheel cover in a 64px atlas quadrant.
    d.rectangle((0,64,63,127),fill=(53,55,53))
    for radius,color in [(30,(80,83,79)),(28,(178,181,168)),(25,(117,124,115)),(23,(153,159,146)),(15,(170,174,160))]:
        d.ellipse((32-radius,96-radius,32+radius,96+radius),fill=color)
    for i in range(12):
        a=2*math.pi*i/12
        cx,cy=32+20*math.cos(a),96+20*math.sin(a)
        d.ellipse((cx-2,cy-2,cx+2,cy+2),fill=(42,48,44))
        d.point((int(cx),int(cy+2)),fill=(210,212,194))
    d.ellipse((24,88,40,104),fill=(124,133,120),outline=(213,215,196))
    d.line((31,92,31,99,35,99),fill=(222,223,201),width=2)
    TEX.mkdir(parents=True, exist_ok=True)
    image.save(TEX / 'linden128.png')
    # Every mip is explicit; keep the TXD native, uncompressed D3D9 RGB888.
    native = struct.pack('<IHH32s32s',9,0x1106,0,b'linden128',b'')
    levels=[]
    level=image.convert('RGBA')
    while True:
        levels.append(level.tobytes('raw','BGRA'))
        if level.width==1: break
        level=level.resize((level.width//2,level.height//2),Image.Resampling.BOX)
    native += struct.pack('<IIHHBBBB',0x8600,22,128,128,32,len(levels),4,0)
    native += b''.join(struct.pack('<I',len(data))+data for data in levels)
    return chunk(0x15,chunk(1,native)+chunk(3,b''))


def write_txd(new_texture):
    source=(REF/'models/premier.txd').read_bytes()
    end=12+struct.unpack_from('<I',source,4)[0]
    parts=[]
    p=12
    while p<end:
        kind,size,version=struct.unpack_from('<III',source,p)
        raw=source[p:p+12+size]
        if kind==1:
            n,device=struct.unpack_from('<HH',source,p+12)
            raw=chunk(1,struct.pack('<HH',n+1,device))
        if kind==3: parts.append(new_texture)
        parts.append(raw)
        p+=12+size
    (OUT/'premier.txd').write_bytes(chunk(0x16,b''.join(parts)))


def texture(mat, name):
    tx=mat.first(6)
    tx.find(2)[0].data=name.encode('ascii').ljust((len(name)+4)//4*4,b'\0')


def smooth(a,b,v):
    t=max(0,min(1,(v-a)/(b-a)))
    return t*t*(3-2*t)


def shape(p):
    """A continuous car-space deformation shared by intact/damaged/LOD parts.

    Wheelbase/track and door hinge regions remain fixed. Bodywork stays within
    the conservative stock collision envelope; no wheel or seat is rescaled.
    """
    x,y,z=p
    high=smooth(0.28,0.78,z)
    cabin=1-smooth(1.1,1.6,abs(y+0.25))
    nx=x*(1-0.045*high*cabin)
    ny=y-0.12*high*cabin
    nz=z-0.045*high*cabin
    ny-=0.095*smooth(1.80,2.45,y)
    ny+=0.095*(1-smooth(-2.85,-2.20,y))
    # Take a little crown out of the bonnet and boot without breaking seams.
    nz-=0.022*smooth(1.05,1.65,y)*smooth(-0.02,0.26,z)
    return nx,ny,nz


def vector_mat(v,r):
    return tuple(sum(v[k]*r[k][j] for k in range(3)) for j in range(3))


def inverse_vector(v,r):
    return tuple(sum(v[k]*r[j][k] for k in range(3)) for j in range(3))


def norm(v):
    length=math.sqrt(sum(c*c for c in v)) or 1
    return tuple(c/length for c in v)


def change_norm(n,p):
    # Inverse-transpose Jacobian, estimated with central differences. This
    # preserves the donor's intentional hard edges and split vertex normals.
    eps=0.0001
    cols=[]
    for j in range(3):
        a=list(p); b=list(p); a[j]+=eps; b[j]-=eps
        cols.append(tuple((x-y)/(2*eps) for x,y in zip(shape(a),shape(b))))
    a,b,c=cols
    cross=lambda u,v:(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
    cof=[cross(b,c),cross(c,a),cross(a,b)]
    return norm(tuple(sum(n[j]*cof[j][k] for j in range(3)) for k in range(3)))


def bounds(g):
    lo=[min(p[j] for p in g.pos) for j in range(3)]
    hi=[max(p[j] for p in g.pos) for j in range(3)]
    center=tuple((a+b)/2 for a,b in zip(lo,hi))
    radius=max(math.dist(p,center) for p in g.pos)+0.0001
    g.sphere=struct.pack('<4f',*center,radius)


def build():
    extract(); OUT.mkdir(parents=True, exist_ok=True)
    new_texture=atlas(); write_txd(new_texture)
    source=(REF/'models/premier.dff').read_bytes()
    clump=rw.load(source)[0]  # IMG-sector padding is not part of the clump.
    frames=rw.frames(clump)
    transforms=[rw.frame_to_root(frames,i) for i in range(len(frames))]
    targets=[shape(p) for r,p in transforms]
    fl=clump.first(14).children[0]
    raw=bytearray(fl.data)
    for i,f in enumerate(frames):
        parent=f[3]
        if parent<0: local=targets[i]
        else:
            delta=tuple(a-b for a,b in zip(targets[i],targets[parent]))
            local=inverse_vector(delta,transforms[parent][0])
        struct.pack_into('<3f',raw,4+56*i+36,*local)
    fl.data=bytes(raw)
    geoms=clump.first(26).find(15)
    changes=[]
    for atomic in clump.find(20):
        fi,gi=struct.unpack_from('<II',atomic.children[0].data)
        name=frames[fi][0]
        node=geoms[gi]
        g=rw.Geometry(node.children[0].data)
        r,p=transforms[fi]
        original=[tuple(a+b for a,b in zip(vector_mat(v,r),p)) for v in g.pos]
        # Frames and geometry are transformed together, so detachable pieces
        # share the same closed seams as the chassis after the shape edit.
        for i,world in enumerate(original):
            delta=tuple(a-b for a,b in zip(shape(world),targets[fi]))
            g.pos[i]=inverse_vector(delta,r)
            if g.nrm:
                g.nrm[i]=inverse_vector(change_norm(vector_mat(g.nrm[i],r),world),r)
        mats=node.first(8).find(7)
        before=len(g.tris)
        def add_material(name='linden128', swatch=False):
            mat=copy.deepcopy(mats[0])
            rw.set_material_colour(mat,bytes((255,255,255,255)))
            texture(mat,name)
            # New plastic/metal trim uses no donor paint reflection plugins.
            mat.children=[c for c in mat.children if c.type!=3]
            mat.children.append(rw.Chunk(3,VER,children=[]))
            node.first(8).children.append(mat); mats.append(mat)
            return len(mats)-1
        atlas_index=None
        if name=='chassis':
            atlas_index=add_material()
            # Replace the original central grille rather than covering it.
            g.tris=[t for t in g.tris if not (t[3] in (17,18) and
                    all(abs(original[i][0])<0.585 and original[i][1]>2.35 and original[i][2]<0.15 for i in t[:3]))]

        def vertex(world,uv,normal):
            delta=tuple(a-b for a,b in zip(shape(world),targets[fi]))
            g.pos.append(inverse_vector(delta,r))
            if g.nrm is not None:
                g.nrm.append(inverse_vector(change_norm(normal,world),r))
            for layer in g.uvs: layer.append(uv)
            if g.prelit is not None: g.prelit.append(bytes((255,255,255,255)))
            return len(g.pos)-1

        def quad(points,uvs,normal,material_index):
            ids=[vertex(p,uv,normal) for p,uv in zip(points,uvs)]
            g.tris += [(ids[0],ids[1],ids[2],material_index),(ids[0],ids[2],ids[3],material_index)]

        def rectangle(x0,x1,y,z0,z1,region,front=True):
            u0,v0,u1,v1=(v/128 for v in region)
            pts=[(x0,y,z0),(x0,y,z1),(x1,y,z1),(x1,y,z0)]
            uv=[(u0,v1),(u0,v0),(u1,v0),(u1,v1)]
            normal=(0,1,0)
            if not front:
                pts.reverse(); uv.reverse(); normal=(0,-1,0)
            quad(pts,uv,normal,atlas_index)

        if name=='chassis':
            rectangle(-0.55,0.55,2.453,-0.128,0.105,(1,1,127,31))
            # Small black dividers produce four rectangular sealed-beam lamps.
            for sign in [-1,1]:
                x=sign*0.76
                rectangle(x-0.012,x+0.012,2.399,-0.105,0.065,(75,75,85,85))
            rectangle(-0.47,0.47,-2.790,-0.095,0.101,(1,34,127,57),False)
            # A narrow chrome edge and black return make the new grille solid.
            rectangle(-0.558,0.558,2.450,0.105,0.120,(102,68,123,70))
            rectangle(-0.558,0.558,2.450,-0.143,-0.128,(102,68,123,70))
            for x in [-0.558,0.55]:
                rectangle(x,x+0.008,2.450,-0.128,0.105,(102,68,123,70))

        if name.startswith('bump_'):
            # Convert the stock painted bumper surfaces to molded charcoal.
            for mi,mat in enumerate(mats):
                if rw.material_colour(mat)[:3]==bytes((60,255,0)):
                    rw.set_material_colour(mat,bytes((255,255,255,255)))
                    texture(mat,'linden128')
                    ids={i for t in g.tris if t[3]==mi for i in t[:3]}
                    for i in ids:
                        for uv in g.uvs: uv[i]=(80/128,80/128)
        if name=='wheel':
            texture(mats[2],'linden128')
            ids={i for t in g.tris if t[3]==2 for i in t[:3]}
            for i in ids:
                # A proper radial UV instead of the donor's mirrored wedge UV.
                y,z=g.pos[i][1:]
                for uv in g.uvs:
                    uv[i]=((32+y/0.233*30)/128,(96-z/0.233*30)/128)

        bounds(g)
        node.children[0].data=g.pack()
        node.first(8).children[0].data=struct.pack('<I',len(mats))+struct.pack('<'+'i'*len(mats),*([-1]*len(mats)))
        for ext in node.find(3):
            for plugin in ext.children:
                if plugin.type==0x50e: plugin.data=g.bin_mesh()
                elif plugin.type==0x253f2f9 and len(g.pos)!=len(original):
                    # Rockstar night colours: keep existing values, extend for
                    # added trim. The first uint32 is the non-null marker.
                    assert len(plugin.data)==4+len(original)*4
                    plugin.data+=bytes((180,180,180,255))*(len(g.pos)-len(original))
        changes.append({'part':name,'triangles_before':before,'triangles_after':len(g.tris),
                        'vertices':len(g.pos)})
    result=rw.write([clump])
    (OUT/'premier.dff').write_bytes(result)
    report={'vehicle':'Linden 1800','replacement':'Premier (426)',
            'donor_sha256':hashlib.sha256(source).hexdigest(),
            'dff_sha256':hashlib.sha256(result).hexdigest(),
            'triangles_before':sum(c['triangles_before'] for c in changes),
            'triangles_after':sum(c['triangles_after'] for c in changes),
            'new_texture':{'name':'linden128','size':[128,128],'mip_levels':8},
            'parts':changes}
    (ROOT/'assets/build_report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='parts'},indent=2))


if __name__=='__main__': build()
