"""Build the Pip: new city-car meshes using the stock Manana hierarchy.
Python 3.12+, Pillow; DragonFF is used only for embedded COL3 serialization.
"""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import math
import struct
import sys
from PIL import Image, ImageDraw, ImageFont

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE.parent/'tools'))
import rw_dff as rw
V=0x1803FFFF
MODEL='pip660'
PAINT=(60,255,0,255);SECONDARY=(255,0,175,255)
LIGHTS={'head_l':(255,175,0,255),'head_r':(0,255,200,255),
        'tail_l':(185,255,0,255),'tail_r':(255,60,0,255)}
RECT={'paint':(2,66,29,125),'roof':(2,66,29,125),'plastic':(34,66,61,125),
      'rubber':(34,94,61,125),'fabric':(66,66,93,125),'steel':(98,66,125,125),
      'hub':(1,1,31,31),'amber':(33,1,63,31),'badge':(65,1,95,31),
      'grille':(97,1,126,29),'gauges':(1,33,63,61),'label':(65,33,95,61),
      'cracks':(97,33,126,61),'glass':(34,66,61,91),'engine':(1,33,63,61)}


def chunk(kind,data):return struct.pack('<III',kind,len(data),V)+data

def cross(a,b):return a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]
def sub(a,b):return tuple(x-y for x,y in zip(a,b))
def unit(v):
    length=math.sqrt(sum(x*x for x in v))
    return tuple(x/(length or 1) for x in v)

def atlas():
    im=Image.new('RGB',(128,128),(32,35,34));d=ImageDraw.Draw(im)
    for y in range(64,128):
        for x in range(128):
            n=((x*13+y*19)%5)-2
            if x<32:
                dirt=int(max(0,y-104)*.35)
                c=(238+n-dirt,238+n-dirt,232+n-dirt)
            elif x<64:c=(43+n,46+n,45+n)
            elif x<96:
                weave=(x+y)%3*3;c=(111+n+weave,112+n+weave,104+n+weave)
            else:c=(168+n,170+n,165+n)
            d.point((x,y),fill=c)
    # Small pressed-steel wheel face. Holes are texture detail at stock scale.
    d.rectangle((0,0,31,31),fill=(50,53,50));d.ellipse((1,1,30,30),fill=(170,173,164),outline=(205,207,197))
    d.ellipse((5,5,26,26),outline=(112,116,108));d.ellipse((11,11,20,20),fill=(146,151,141),outline=(203,205,194))
    for i in range(8):
        a=2*math.pi*i/8;x=15.5+10*math.cos(a);y=15.5+10*math.sin(a)
        d.ellipse((int(x)-1,int(y)-1,int(x)+1,int(y)+1),fill=(36,39,36))
    for i in range(4):
        a=2*math.pi*i/4;x=15.5+6*math.cos(a);y=15.5+6*math.sin(a)
        d.point((round(x),round(y)),fill=(228,228,216))
    d.rectangle((32,0,63,31),fill=(187,102,27))
    for x in range(34,63,3):d.line((x,2,x,29),fill=(229,150,52))
    d.rectangle((64,0,95,31),fill=(225,225,214))
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',9)
    d.text((69,8),'pip',font=font,fill=(49,61,56))
    d.rectangle((96,0,127,31),fill=(22,27,25))
    for y in range(4,30,5):d.line((98,y,125,y),fill=(86,91,82))
    d.rectangle((0,32,63,63),fill=(34,39,36))
    for x in [15,42]:
        d.ellipse((x-10,35,x+10,57),fill=(19,26,23),outline=(125,135,113))
        d.line((x,47,x+5,41),fill=(217,207,170))
        for a in range(0,360,60):
            r=math.radians(a);d.point((round(x+8*math.cos(r)),round(46+8*math.sin(r))),fill=(208,211,188))
    d.rectangle((64,32,95,63),fill=(44,52,47));d.text((72,42),'PIP',font=font,fill=(200,201,181))
    d.rectangle((96,32,127,63),fill=(36,48,46))
    for i in range(11):
        x=98+(i*11)%28;y=34+(i*7)%26
        d.line((112,47,x,y),fill=(185,199,185),width=1)
        d.line((x,y,min(126,x+5),min(62,y+4)),fill=(151,172,157))
    out=BASE/'assets/pip_detail128.png';im.save(out)
    levels=[];level=im.convert('RGBA')
    while True:
        levels.append(level.tobytes('raw','BGRA'))
        if level.width==1:break
        level=level.resize((level.width//2,level.height//2),Image.Resampling.BOX)
    native=struct.pack('<IHH32s32s',9,0x1106,0,b'pip_detail128',b'')
    native+=struct.pack('<IIHHBBBB',0x8600,22,128,128,32,len(levels),4,0)
    native+=b''.join(struct.pack('<I',len(p))+p for p in levels)
    return chunk(0x16,chunk(1,struct.pack('<HH',1,2))+chunk(0x15,chunk(1,native)+chunk(3,b''))+chunk(3,b''))


def materials(donor):
    templates={}
    for node in donor.first(26).find(15):
        for m in node.first(8).find(7):
            color=tuple(rw.material_colour(m))
            templates.setdefault(color,copy.deepcopy(m))
    result={}
    for kind in RECT.keys()|LIGHTS.keys()|{'plate','plate_back'}:
        color=PAINT if kind=='paint' else SECONDARY if kind=='roof' else LIGHTS.get(kind,(255,255,255,255))
        m=copy.deepcopy(templates[color if color in templates else PAINT])
        rw.set_material_colour(m,bytes((195,210,205,125)) if kind=='glass' else bytes((210,220,211,175)) if kind=='cracks' else bytes(color))
        if kind not in ['paint','roof'] and kind not in LIGHTS:
            m.children=[c for c in m.children if c.type!=3]+[rw.Chunk(3,V,children=[])]
        texname='vehiclelights128' if kind in LIGHTS else 'carplate' if kind=='plate' else 'carpback' if kind=='plate_back' else 'pip_detail128'
        tex=m.first(6);tex.find(2)[0].data=texname.encode().ljust((len(texname)+4)//4*4,b'\0')
        result[kind]=m
    return result


class Mesh:
    def __init__(self,name,translation,mats,deform=None):
        self.name=name;self.translation=translation;self.templates=mats;self.mats=[];self.material_ids={};self.deform=deform;self.smooth={}
        g=rw.Geometry.__new__(rw.Geometry);g.flags=0x1007e;g.pos=[];g.nrm=[];g.prelit=[];g.uvs=[[]];g.tris=[];g.sphere=b'\0'*16;self.g=g
    def face(self,points,kind='paint',direction=None,uv=None,smooth=None):
        points=[self.deform(p) for p in points] if self.deform else list(points)
        if len(points)<3:return
        n=cross(sub(points[1],points[0]),sub(points[2],points[0]))
        if sum(x*x for x in n)<1e-14:return
        if direction and sum(a*b for a,b in zip(n,direction))<0:
            points.reverse()
            if uv:uv=list(reversed(uv))
            n=tuple(-x for x in n)
        n=unit(n)
        if kind not in self.material_ids:
            self.material_ids[kind]=len(self.mats);self.mats.append(copy.deepcopy(self.templates[kind]))
        mi=self.material_ids[kind]
        if uv is None:
            rect=(.02,.27,.48,.48) if kind.startswith('head') else (.53,.015,.93,.24) if kind.startswith('tail') else (0,0,1,1) if kind.startswith('plate') else tuple(v/128 for v in RECT[kind])
            u0,v0,u1,v1=rect
            uv=[(u0,v1),(u1,v1),(u1,v0),(u0,v0)] if len(points)==4 else [(u0+(u1-u0)*i/max(1,len(points)-1),v0) for i in range(len(points))]
        start=len(self.g.pos)
        for p,t in zip(points,uv):
            self.g.pos.append(tuple(a-b for a,b in zip(p,self.translation)))
            self.g.nrm.append(n);self.g.prelit.append(bytes((231,231,231,255)));self.g.uvs[0].append(t)
            if smooth:self.smooth.setdefault((smooth,tuple(round(v,6) for v in p)),[]).append(len(self.g.pos)-1)
        for i in range(1,len(points)-1):self.g.tris.append((start,start+i,start+i+1,mi))
    def box(self,lo,hi,kind='plastic'):
        x,y,z=lo;X,Y,Z=hi
        v=[(x,y,z),(X,y,z),(X,Y,z),(x,Y,z),(x,y,Z),(X,y,Z),(X,Y,Z),(x,Y,Z)]
        for f in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]:self.face([v[i] for i in f],kind)
    def bridge(self,a,b,kind='paint',direction=None,smooth=None):
        for i in range(len(a)-1):self.face([a[i],a[i+1],b[i+1],b[i]],kind,direction,smooth=smooth)
    def ring(self,outer,inner,kind,direction):
        for i in range(len(outer)):
            j=(i+1)%len(outer);self.face([outer[i],outer[j],inner[j],inner[i]],kind,direction)
    def finish(self):
        g=self.g
        g.tris=[t for t in g.tris if sum(v*v for v in cross(sub(g.pos[t[1]],g.pos[t[0]]),sub(g.pos[t[2]],g.pos[t[0]])))>1e-14]
        for ids in self.smooth.values():
            n=unit(tuple(sum(g.nrm[i][j] for i in ids) for j in range(3)))
            for i in ids:g.nrm[i]=n
        center=tuple((min(p[j] for p in g.pos)+max(p[j] for p in g.pos))/2 for j in range(3))
        radius=max(math.dist(center,p) for p in g.pos)+.0001;g.sphere=struct.pack('<4f',*center,radius)
        batches={}
        for a,b,c,m in g.tris:batches.setdefault(m,[]).extend((a,b,c))
        order=sorted(batches,key=lambda m:(rw.material_colour(self.mats[m])[3]<255,m))
        bm=struct.pack('<III',0,len(batches),len(g.tris)*3)
        for m in order:bm+=struct.pack('<II',len(batches[m]),m)+struct.pack('<'+'I'*len(batches[m]),*batches[m])
        ml=rw.Chunk(8,V,children=[rw.Chunk(1,V,data=struct.pack('<I',len(self.mats))+struct.pack('<'+'i'*len(self.mats),*([-1]*len(self.mats))))]+self.mats)
        return rw.Chunk(15,V,children=[rw.Chunk(1,V,data=g.pack()),ml,rw.Chunk(3,V,children=[rw.Chunk(0x50e,V,data=bm),rw.Chunk(0x253f2fd,V,data=b'\0'*4)])])


def side_x(z,y=0):
    base=.667 if z<-.40 else .73 if z<.1 else .704
    return base-max(0,abs(y)-1.25)*.32

def belt(y):return .30-max(0,y-.60)*.13-max(0,-y-1.10)*.10

def fenders(m):
    for sign in [-1,1]:
        for center,lo,hi in [(.96,.59,1.46),(-.96,-1.48,-.59)]:
            samples=[(lo,-.32 if abs(lo)>1.4 else -.425)]
            for i in range(9):
                a=math.pi-i*math.pi/8;y=center+.345*math.cos(a);z=-.32+.345*math.sin(a)
                if lo<=y<=hi:samples.append((y,z))
            samples.append((hi,-.32 if abs(hi)>1.4 else -.425));samples.sort()
            for (ya,za),(yb,zb) in zip(samples,samples[1:]):
                a=(sign*side_x(za,ya),ya,za);b=(sign*side_x(zb,yb),yb,zb)
                A=(sign*side_x(belt(ya),ya),ya,belt(ya));B=(sign*side_x(belt(yb),yb),yb,belt(yb))
                m.face([a,b,B,A],'paint',(sign,0,0),smooth='body')
                # Dark inner wheelhouse, ending inside the shell.
                if max(za,zb)>-.42:
                    m.face([a,b,(sign*.52,yb,zb),(sign*.52,ya,za)],'rubber',(0,0,-1))
            # Small black arch eyebrow follows the true cutout, no floating flare.
            contour=[(center+.345*math.cos(math.pi-i*math.pi/8),-.32+.345*math.sin(math.pi-i*math.pi/8)) for i in range(9)]
            for (ya,za),(yb,zb) in zip(contour,contour[1:]):
                if not (lo<=ya<=hi and lo<=yb<=hi):continue
                m.face([(sign*(side_x(za,ya)+.003),ya,za),(sign*(side_x(zb,yb)+.003),yb,zb),
                        (sign*(side_x(zb+.017,yb)+.004),yb,zb+.017),(sign*(side_x(za+.017,ya)+.004),ya,za+.017)],'plastic',(sign,0,0))
        # Rockers connect front/rear wings below both doors.
        m.box((min(sign*.65,sign*.685),-.60,-.445),(max(sign*.65,sign*.685),.60,-.432),'paint')
        # Door aperture returns: no empty cabin wall exposed on opening.
        for y in [-.594,.594]:m.box((min(sign*.635,sign*.704),y-.012,-.425),(max(sign*.635,sign*.704),y+.012,.30),'plastic')
        # A-pillar / B-pillar / C-pillar, each with an inner return.
        for a,b,width in [((.66,.65,.32),(.55,.20,.980),.045),((.70,-.60,.30),(.558,-.60,1.045),.045),((.65,-1.44,.27),(.55,-.92,.980),.055)]:
            p=(sign*a[0],a[1],a[2]);q=(sign*b[0],b[1],b[2])
            offset=width if a[1]<-1 else -width
            m.face([p,q,(q[0],q[1]+offset,q[2]),(p[0],p[1]+offset,p[2])],'paint',(sign,0,0))
            m.face([(p[0]-sign*.025,p[1],p[2]),(q[0]-sign*.025,q[1],q[2]),q,p],'plastic',(0,1,0))
        # Fixed rear quarter light, surrounded by a substantial painted pillar.
        outer=[(sign*.697,-.63,.31),(sign*.648,-1.375,.29),(sign*.555,-.925,.980),(sign*.559,-.63,1.015)]
        cy=sum(p[1] for p in outer)/4;cz=sum(p[2] for p in outer)/4
        inner=[(p[0]-sign*.006,cy+(p[1]-cy)*.83,cz+(p[2]-cz)*.82) for p in outer]
        m.ring(outer,inner,'plastic',(sign,0,0));m.face(inner,'glass',(sign,0,0))
        # Rear-quarter shoulder between window and wheel arch.
        m.face([(sign*side_x(belt(-.60),-.60),-.60,belt(-.60)),(sign*side_x(belt(-1.46),-1.46),-1.46,belt(-1.46)),
                (sign*.648,-1.375,.29),(sign*.697,-.63,.31)],'paint',(0,0,1))
        # Each crown shares the bonnet's actual section coordinates. A single
        # flat wedge here would leave the curved bonnet visibly above its wing.
        sections=[(.665,.335,.628),(.94,.320,.646),(1.24,.267,.615),(1.405,.220,.576)]
        for (ya,za,wa),(yb,zb,wb) in zip(sections,sections[1:]):
            m.face([(sign*side_x(belt(ya),ya),ya,belt(ya)),
                    (sign*side_x(belt(yb),yb),yb,belt(yb)),
                    (sign*(wb+.003),yb,zb-.028),(sign*(wa+.003),ya,za-.028)],
                   'paint',(0,0,1),smooth='body')



def roof(m):
    ys=[(.20,1.035),(-.10,1.105),(-.65,1.105),(-.92,1.035)]
    rows=[]
    for y,z in ys:rows.append([(x,y,z-.055*(abs(x)/.55)**2) for x in [-.55,-.40,0,.40,.55]])
    for a,b in zip(rows,rows[1:]):m.bridge(a,b,'roof',(0,0,1),smooth='roof')
    # Front/rear headers close the cambered roof above straight window edges.
    for row,direction in [(rows[0],(0,1,0)),(rows[-1],(0,-1,0))]:
        low=[(x,y,.975) for x,y,z in row]
        m.bridge(row,low,'roof',direction)
    def rail_z(y):
        return .980+(.20-y)/.80*.035 if y>=-.60 else 1.015-(abs(y)-.60)/.32*.035
    for sign in [-1,1]:
        for (ya,za),(yb,zb) in zip(ys,ys[1:]):
            m.face([(sign*.55,ya,za-.055),(sign*.55,yb,zb-.055),
                    (sign*.558,yb,rail_z(yb)-.003),(sign*.558,ya,rail_z(ya)-.003)],'roof',(sign,0,0))
    m.face([(-.53,.17,.965),(.53,.17,.965),(.53,-.90,.965),(-.53,-.90,.965)],'fabric',(0,0,-1))


def windscreen(m,damaged=False):
    outer=[(-.65,.65,.345),(.65,.65,.345),(.55,.20,.98),(-.55,.20,.98)]
    # Roof's front edge is z=.980 at both corners; all panels share that seam.
    inner=[(-.611,.632,.371),(.611,.632,.371),(.519,.218,.956),(-.519,.218,.956)]
    m.ring(outer,inner,'plastic',(0,1,1));m.face(inner,'cracks' if damaged else 'glass',(0,1,1))
    m.box((-.645,.615,.305),(.645,.656,.342),'plastic')
    # Two blades attached to the cowl, lying along the screen's lower edge.
    for x in [-.30,.24]:
        m.face([(x-.20,.633,.364),(x+.15,.616,.389),(x+.15,.610,.397),(x-.20,.627,.372)],'rubber',(0,1,1))


def door(m,sign,damaged=False):
    ys=[-.582,0,.582];zs=[-.420,-.12,.295]
    for za,zb in zip(zs,zs[1:]):
        a=[(sign*(.664 if za<-.4 else .724),y,za) for y in ys]
        b=[(sign*(.724 if zb<.1 else .700),y,zb) for y in ys]
        m.bridge(a,b,'paint',(sign,0,0),smooth='door')
    # Structural inner door and aperture thickness.
    for za,zb in zip(zs,zs[1:]):
        m.bridge([(sign*.645,y,za+.006) for y in ys],[(sign*.645,y,zb-.006) for y in ys],'plastic',(-sign,0,0))
    for y in [ys[0],ys[-1]]:m.face([(sign*.664,y,-.420),(sign*.700,y,.295),(sign*.645,y,.285),(sign*.645,y,-.410)],'paint',(0,1 if y>0 else -1,0))
    outer=[(sign*.700,.582,.295),(sign*.700,-.582,.295),(sign*.559,-.582,1.015),(sign*.550,.185,.980)]
    inner=[(sign*.691,.527,.342),(sign*.691,-.532,.342),(sign*.565,-.532,.964),(sign*.557,.159,.934)]
    m.ring(outer,inner,'paint',(sign,0,0))
    # Narrow black seal is actual window frame surface, no coplanar decal.
    center=tuple(sum(p[j] for p in inner)/4 for j in range(3))
    glass=[tuple(center[j]+(p[j]-center[j])*.965 for j in range(3)) for p in inner]
    m.ring(inner,glass,'rubber',(sign,0,0));m.face(glass,'cracks' if damaged else 'glass',(sign,0,0))
    # Waist moulding, flush handle and inner armrest.
    m.box((min(sign*.719,sign*.733),-.55,-.085),(max(sign*.719,sign*.733),.55,-.055),'plastic')
    m.box((min(sign*.700,sign*.715),-.48,.195),(max(sign*.700,sign*.715),-.33,.233),'plastic')
    m.box((min(sign*.595,sign*.645),-.44,.06),(max(sign*.595,sign*.645),.20,.115),'plastic')
    # Mirror mounts meet the leading window corner and move with the door.
    m.box((min(sign*.67,sign*.77),.46,.32),(max(sign*.67,sign*.77),.55,.37),'plastic')
    cx=sign*.795;cz=.395;w=.070;h=.049;c=.014
    outline=[(-w,-h+c),(-w+c,-h),(w-c,-h),(w,-h+c),(w,h-c),(w-c,h),(-w+c,h),(-w,h-c)]
    front=[(cx+x,.556,cz+z) for x,z in outline]
    rear=[(cx+x,.444,cz+z) for x,z in outline]
    for i in range(8):
        j=(i+1)%8;m.face([front[i],front[j],rear[j],rear[i]],'plastic')
    for row,kind,d in [(front,'roof',(0,1,0)),(rear,'steel',(0,-1,0))]:
        center=(cx,row[0][1],cz)
        for i in range(8):m.face([center,row[i],row[(i+1)%8]],kind,d)



def bonnet(m):
    rows=[]
    for y,z,w in [(.665,.335,.628),(.94,.320,.646),(1.24,.267,.615),(1.405,.220,.576)]:
        rows.append([(x*w,y,z-.028*(abs(x))**2) for x in [-1,-.7,0,.7,1]])
    for a,b in zip(rows,rows[1:]):m.bridge(a,b,'paint',(0,0,1),smooth='bonnet')
    for side in [0,-1]:
        for a,b in zip(rows,rows[1:]):
            p,q=a[side],b[side];m.face([p,q,(q[0],q[1],q[2]-.025),(p[0],p[1],p[2]-.025)],'paint',(-1 if side==0 else 1,0,0))
    underside=[[(x,y,z-.025) for x,y,z in row] for row in rows]
    for a,b in zip(underside,underside[1:]):
        for i in range(len(a)-1):
            # Use the SAME diagonal as the outer skin, even after denting.
            m.face([a[i],b[i+1],a[i+1]],'plastic',(0,0,-1))
            m.face([a[i],b[i],b[i+1]],'plastic',(0,0,-1))


def hatch(m,damaged=False):
    outer=[(-.55,-.92,.980),(.55,-.92,.980),(.540,-1.435,.275),(-.540,-1.435,.275)]
    inner=[(-.51,-.953,.933),(.51,-.953,.933),(.500,-1.369,.365),(-.500,-1.369,.365)]
    m.ring(outer,inner,'paint',(0,-1,1))
    glass=[(x*.975,y+.003,z) for x,y,z in inner]
    m.ring(inner,glass,'rubber',(0,-1,1));m.face(glass,'cracks' if damaged else 'glass',(0,-1,1))
    m.face([(-.540,-1.435,.275),(.540,-1.435,.275),(.532,-1.475,-.115),(-.532,-1.475,-.115)],'paint',(0,-1,0),smooth='hatch')
    m.face([(-.521,-1.423,.24),(.521,-1.423,.24),(.521,-1.459,-.105),(-.521,-1.459,-.105)],'plastic',(0,1,0))
    m.box((-.08,-1.460,.16),(.08,-1.443,.19),'plastic')
    m.face([(-.49,-1.4575,.065),(-.34,-1.4575,.065),(-.34,-1.4511,.128),(-.49,-1.4511,.128)],'label',(0,-1,0))
    # Rear blade sits on the window rather than over a hole.
    m.face([(-.02,-1.360,.376),(.27,-1.230,.555),(.28,-1.230,.559),(-.01,-1.365,.374)],'rubber',(0,-1,1))


def bumper(m,front):
    sign=1 if front else -1
    xs=[-.72,-.64,-.40,0,.40,.64,.72];rows=[]
    for x in xs:
        y=sign*(1.53-max(0,abs(x)-.50)*.48)
        rows.append([(x,y-sign*.045,-.125),(x,y,-.18),(x,y-sign*.010,-.315),(x,y-sign*.065,-.345),(x,y-sign*.125,-.310),(x,y-sign*.125,-.14)])
    for a,b in zip(rows,rows[1:]):
        for j in range(6):
            k=(j+1)%6;m.face([a[j],b[j],b[k],a[k]],'plastic',(0,0,1) if j==5 else (0,0,-1) if j==3 else (0,sign if j<3 else -sign,0))
    for row,d in [(rows[0],(-1,0,0)),(rows[-1],(1,0,0))]:
        for i in range(1,len(row)-1):m.face([row[0],row[i],row[i+1]],'plastic',d)
    y=sign*1.536
    # Plate belongs to the detachable bumper; carplate is the runtime text key.
    plate=[(-.17,y,-.165),(.17,y,-.165),(.17,y,-.285),(-.17,y,-.285)]
    m.face(plate,'plate',(0,sign,0))
    if front:
        m.face([(-.30,1.523,-.325),(.30,1.523,-.325),(.30,1.523,-.292),(-.30,1.523,-.292)],'grille',(0,1,0))


def fascia(m):
    # Closed nose/back below moving panels; lamp recesses have solid backs.
    m.face([(-.63,1.410,.195),(.63,1.410,.195),(.68,1.47,-.135),(-.68,1.47,-.135)],'paint',(0,1,0),smooth='nose')
    m.face([(-.65,-1.470,-.115),(.65,-1.470,-.115),(.68,-1.46,-.33),(-.68,-1.46,-.33)],'paint',(0,-1,0))
    for sign,side in [(-1,'l'),(1,'r')]:
        # Headlamp sockets project INTO the nose, then the opaque lens closes it.
        a,b=sorted((sign*.30,sign*.615))
        m.box((a,1.418,-.065),(b,1.471,.153),'plastic')
        points=[(a+.014,1.473,-.048),(b-.014,1.473,-.048),(b-.014,1.473,.135),(a+.014,1.473,.135)]
        m.face(points,'head_'+side,(0,1,0))
        a,b=sorted((sign*.32,sign*.59))
        m.face([(a,1.4651,-.100),(b,1.4651,-.100),(b,1.4593,-.068),(a,1.4593,-.068)],'amber',(0,1,0))
        a,b=sorted((sign*.550,sign*.650))
        m.box((a,-1.488,-.12),(b,-1.445,.29),'plastic')
        m.face([(a+.009,-1.490,-.10),(b-.009,-1.490,-.10),(b-.009,-1.490,.27),(a+.009,-1.490,.27)],'tail_'+side,(0,-1,0))
    for sign in [-1,1]:
        m.face([(sign*.54,-1.470,-.12),(sign*.65,-1.470,-.12),
                (sign*.65,-1.445,.285),(sign*.54,-1.435,.275)],'paint',(0,-1,0))
    m.face([(-.255,1.4424,.025),(.255,1.4424,.025),(.255,1.4260,.115),(-.255,1.4260,.115)],'grille',(0,1,0))
    m.face([(-.052,1.4242,.125),(.052,1.4242,.125),(.052,1.4137,.183),(-.052,1.4137,.183)],'badge',(0,1,0))


def interior(m):
    m.box((-.64,-1.40,-.43),(.64,.66,-.405),'plastic')
    m.box((-.61,-1.35,-.40),(.61,-.60,-.285),'fabric')
    for x in [-.32,.32]:
        m.box((x-.235,-.43,-.265),(x+.235,.04,-.13),'plastic')
        m.box((x-.23,-.40,-.13),(x+.23,.045,-.015),'fabric')
        # Raked seat back, four strips give the fabric a stock pleated read.
        for i in range(4):
            a=x-.23+i*.115;b=a+.115
            m.face([(a,-.43,-.02),(b,-.43,-.02),(b,-.55,.58),(a,-.55,.58)],'fabric',(0,1,0))
        m.box((x-.235,-.59,.0),(x+.235,-.55,.58),'plastic')
        for a in [x-.23,x+.23]:m.face([(a,-.43,-.02),(a,-.55,.58),(a,-.59,.58),(a,-.59,0)],'fabric',(-1 if a<x else 1,0,0))
        m.box((x-.075,-.57,.58),(x+.075,-.55,.67),'steel')
        m.box((x-.145,-.61,.65),(x+.145,-.52,.79),'fabric')
    m.box((-.63,.44,.16),(.63,.64,.305),'plastic')
    m.face([(-.51,.438,.205),(-.12,.438,.205),(-.12,.438,.29),(-.51,.438,.29)],'gauges',(0,-1,0))
    m.box((-.08,.36,-.38),(.08,.61,.16),'plastic')
    m.box((-.015,.37,-.06),(.015,.40,.08),'rubber')
    # Steering rim; the driver and passenger seats remain full adult size.
    center=(-.32,.305,.365)
    for i in range(12):
        a=2*math.pi*i/12;b=2*math.pi*(i+1)/12
        def p(t,r):return center[0]+r*math.cos(t),center[1]+.35*r*math.sin(t),center[2]+r*math.sin(t)
        m.face([p(a,.127),p(b,.127),p(b,.108),p(a,.108)],'rubber',(0,-1,0),smooth='wheelrim')
    for a in [0,2*math.pi/3,4*math.pi/3]:
        m.face([center,(center[0]+.10*math.cos(a-.13),center[1],center[2]+.10*math.sin(a-.13)),
                (center[0]+.10*math.cos(a+.13),center[1],center[2]+.10*math.sin(a+.13))],'plastic',(0,-1,0))
    # Modest engine bay closes the space below the opening bonnet.
    m.box((-.54,.69,-.30),(.54,1.30,-.265),'plastic')
    m.box((-.28,.78,-.26),(.26,1.17,.105),'plastic')
    m.box((-.22,.82,.105),(.20,1.14,.15),'steel')
    m.box((.32,.81,-.21),(.51,1.08,.13),'rubber')
    for y in [.96,-.96]:m.box((-.59,y-.035,-.39),(.59,y+.035,-.33),'plastic')
    m.box((-.12,-1.15,-.465),(.12,1.15,-.43),'plastic')


def wheel(m,lod=False):
    center=m.translation
    N=8 if lod else 12
    profile=[(-.075,.17),(-.085,.25),(-.060,.29),(.060,.29),(.085,.25),(.075,.17)]
    for (x,r),(X,R) in zip(profile,profile[1:]):
        for i in range(N):
            a=2*math.pi*i/N;b=2*math.pi*(i+1)/N
            points=[(center[0]+x,center[1]+r*math.cos(a),center[2]+r*math.sin(a)),(center[0]+x,center[1]+r*math.cos(b),center[2]+r*math.sin(b)),
                    (center[0]+X,center[1]+R*math.cos(b),center[2]+R*math.sin(b)),(center[0]+X,center[1]+R*math.cos(a),center[2]+R*math.sin(a))]
            m.face(points,'rubber',smooth='tyre')
    for sign in [-1,1]:
        for i in range(N):
            a=2*math.pi*i/N;b=2*math.pi*(i+1)/N
            uv=[(.125,.125),(.125+.112*math.cos(a),.125+.112*math.sin(a)),(.125+.112*math.cos(b),.125+.112*math.sin(b))]
            m.face([(center[0]+sign*.077,center[1],center[2]),(center[0]+sign*.077,center[1]+.17*math.cos(a),center[2]+.17*math.sin(a)),
                    (center[0]+sign*.077,center[1]+.17*math.cos(b),center[2]+.17*math.sin(b))],'hub',(sign,0,0),uv)


def exhaust(m):
    for i in range(8):
        a=2*math.pi*i/8;b=2*math.pi*(i+1)/8
        def p(t,y,r):return .37+r*math.cos(t),y,-.385+r*math.sin(t)
        m.face([p(a,-1.18,.032),p(b,-1.18,.032),p(b,-1.57,.032),p(a,-1.57,.032)],'steel')
        m.face([p(a,-1.572,.032),p(b,-1.572,.032),p(b,-1.572,.020),p(a,-1.572,.020)],'steel',(0,-1,0))
        m.face([(.37,-1.545,-.385),p(a,-1.545,.020),p(b,-1.545,.020)],'rubber',(0,-1,0))


def lod(m):
    # Coarse shell follows the same tall cabin, short overhangs and two colours.
    m.box((-.67,-1.46,-.40),(.67,1.44,.24),'paint')
    low=[(-.67,.65,.24),(.67,.65,.24),(.64,-1.44,.24),(-.64,-1.44,.24)]
    high=[(-.55,.20,.98),(.55,.20,.98),(.55,-.92,.98),(-.55,-.92,.98)]
    for i in range(4):
        j=(i+1)%4;m.face([low[i],low[j],high[j],high[i]],'glass',[(0,1,0),(1,0,0),(0,-1,0),(-1,0,0)][i])
    m.face(high,'roof',(0,0,1))
    for front in [True,False]:bumper(m,front)
    for sign in [-1,1]:
        m.box((min(sign*.60,sign*.64),-.61,.25),(max(sign*.60,sign*.64),-.57,.98),'paint')


def collision(clump,dragonff):
    sys.path.insert(0,str(Path(dragonff).resolve()))
    from gtaLib import col
    col.Sections.init_sections(3)
    m=col.ColModel();m.version=3;m.model_name=MODEL;m.model_id=0
    # Separate damage-region spheres, matching the new panel positions.
    for center,r,piece in [((0,1.16,.13),.29,1),((0,-1.23,.37),.29,2),
                           ((-.42,1.35,-.20),.26,3),((.42,1.35,-.20),.26,3),
                           ((-.42,-1.35,-.20),.26,4),((.42,-1.35,-.20),.26,4),
                           ((-.48,.17,.12),.23,5),((-.48,-.34,.12),.23,5),
                           ((.48,.17,.12),.23,6),((.48,-.34,.12),.23,6)]:
        m.spheres.append(col.TSphere(center,r,col.TSurface(63,piece,187,0)))
    m.boxes=[col.TBox((-.57,-.88,-.405),(.57,.58,.18),col.TSurface(63,0,187,128))]
    # A closed ten-vertex longitudinal profile produces cabin slopes, not an
    # old sedan collider. Low wheel-opening skirts are left to suspension rays.
    yz=[(-1.48,-.39),(1.46,-.39),(1.46,.19),(.65,.34),(.20,.98),(-.10,1.07),(-.65,1.07),(-.92,.98),(-1.44,.28),(-1.48,-.10)]
    m.mesh_verts=[]
    for sign in [-1,1]:
        for y,z in yz:
            w=.54 if z>.9 else .67
            m.mesh_verts.append((sign*w,y,z))
    faces=[];N=len(yz)
    for i in range(N):
        j=(i+1)%N;faces.extend([(i,j,N+j),(i,N+j,N+i)])
    for side in [0,1]:
        for i in range(1,N-1):faces.append((side*N,side*N+i,side*N+i+1) if side else (0,i+1,i))
    m.mesh_faces=[col.TFace(*f,63,128) for f in faces]
    m.shadow_verts=list(m.mesh_verts);m.shadow_faces=list(m.mesh_faces)
    lo=[-.75,-1.60,-.48];hi=[.75,1.58,1.10]
    for sphere in m.spheres:
        lo=[min(a,c-sphere.radius) for a,c in zip(lo,sphere.center)]
        hi=[max(a,c+sphere.radius) for a,c in zip(hi,sphere.center)]
    center=tuple((a+b)/2 for a,b in zip(lo,hi))
    m.bounds=col.TBounds(tuple(lo),tuple(hi),center,math.dist(lo,hi)/2+.001)
    container=col.coll(m);raw=container.write_memory()
    plugin=next(p for ext in clump.find(3) for p in ext.children if p.type==0x253f2fa)
    plugin.data=raw
    return {'spheres':len(m.spheres),'boxes':len(m.boxes),'mesh_triangles':len(m.mesh_faces),'shadow_triangles':len(m.shadow_faces)}


def deform_for(name):
    if not name.endswith('_dam'):return None
    def deform(p):
        x,y,z=p
        if name=='bonnet_dam':
            f=max(0,1-abs(x)/.65)*max(0,(y-.68)/.75)
            return x+.035*f,y-.055*f,z-.15*f
        if name.startswith('bump_'):
            front='front' in name;f=max(0,1-abs(x+.25)/1.0)
            return x,y+(-.10 if front else .09)*f,z-.035*f
        if name.startswith('door_'):
            f=max(0,1-abs(y)/.6)*max(0,1-abs(z+.08)/.40)
            return x-math.copysign(.09*f,x),y,z-.018*f
        if name=='boot_dam':
            f=max(0,1-abs(x)/.65)*max(0,1-abs(z)/.5)
            return x,y+.075*f,z-.035*f
        return p
    return deform


def build(dragonff):
    for directory in ['assets','dist']: (BASE/directory).mkdir(exist_ok=True)
    donor=rw.load((BASE/'donor/manana.dff').read_bytes())[0];clump=copy.deepcopy(donor)
    fs=rw.frames(clump);names={f[0]:i for i,f in enumerate(fs)}
    targets={'wheel_lf_dummy':(-.625,.96,-.32),'wheel_rf_dummy':(.625,.96,-.32),
             'wheel_lb_dummy':(-.625,-.96,-.32),'wheel_rb_dummy':(.625,-.96,-.32),
             'headlights':(.46,1.49,.045),'taillights':(.60,-1.50,.09),
             'ped_frontseat':(.32,-.14,-.065),'ped_arm':(-.69,-.04,.39),'petrolcap':(-.69,-1.22,.12),
             'engine':(0,1.0,-.08),'exhaust':(.37,-1.572,-.385),
             'bonnet_dummy':(0,.665,.335),'boot_dummy':(0,-.92,.98),
             'door_lf_dummy':(-.70,.59,-.04),'door_rf_dummy':(.70,.59,-.04),
             'bump_front_dummy':(0,1.42,-.20),'bump_rear_dummy':(0,-1.42,-.20),
             'windscreen_dummy':(0,.65,.345),
             'ug_roof':(0,-.30,1.11),'ug_nitro':(0,-.90,-.20)}
    raw=bytearray(clump.first(14).children[0].data)
    for name,position in targets.items():
        i=names[name];parent=fs[i][3]
        parentpos=rw.frame_to_root(rw.frames(clump),parent)[1] if parent>=0 else (0,0,0)
        # All relocated parent frames have identity bases in this donor.
        struct.pack_into('<3f',raw,4+56*i+36,*sub(position,parentpos))
        clump.first(14).children[0].data=bytes(raw)
    # Disable incompatible original upgrade names while preserving indices.
    for i,f in enumerate(fs):
        if f[0].startswith('ug_'):clump.first(14).find(3)[i].first(0x253f2fe).data=('unused_mount_'+str(i)).encode()
    clump.first(14).find(3)[0].first(0x253f2fe).data=MODEL.encode()
    fs=rw.frames(clump);mats=materials(donor);nodes=[None]*len(clump.first(26).find(15));stats=[]
    for atomic in clump.find(20):
        fi,gi=struct.unpack_from('<II',atomic.children[0].data);name=fs[fi][0];r,p=rw.frame_to_root(fs,fi)
        assert all(abs(r[j][k]-(j==k))<1e-6 for j in range(3) for k in range(3)),name
        mesh=Mesh(name,p,mats,deform_for(name))
        if name=='chassis':fenders(mesh);roof(mesh);fascia(mesh);interior(mesh)
        elif name=='chassis_vlo':lod(mesh)
        elif name.startswith('bonnet'):bonnet(mesh)
        elif name.startswith('boot'):hatch(mesh,name.endswith('_dam'))
        elif name.startswith('door_'):door(mesh,-1 if '_lf_' in name else 1,name.endswith('_dam'))
        elif name.startswith('windscreen'):windscreen(mesh,name.endswith('_dam'))
        elif name.startswith('bump_'):bumper(mesh,'front' in name)
        elif name=='wheel':wheel(mesh)
        elif name=='exhaust_ok':exhaust(mesh)
        else:raise ValueError(name)
        nodes[gi]=mesh.finish();stats.append({'part':name,'triangles':len(mesh.g.tris),'vertices':len(mesh.g.pos)})
    gl=clump.first(26);gl.children=[gl.children[0]]+nodes
    collision_report=collision(clump,dragonff)
    model=rw.write([clump]);texture=atlas()
    (BASE/'dist/pip660.dff').write_bytes(model);(BASE/'dist/pip660.txd').write_bytes(texture)
    visible=sum(s['triangles']*(4 if s['part']=='wheel' else 1) for s in stats if not s['part'].endswith('_dam') and s['part']!='chassis_vlo')
    report={'model':MODEL,'rig_reference':'manana','new_meshes':'all body, interior, wheels, damage and LOD geometries',
            'dimensions':{'length':3.11,'body_width':1.46,'width_with_mirrors':1.73,'height':1.715,'wheelbase':1.92,'wheel_diameter':.58},
            'stored_triangles':sum(s['triangles'] for s in stats),'visible_triangles_four_wheels':visible,
            'collision':collision_report,'parts':stats,'texture':{'name':'pip_detail128','size':[128,128],'mips':8},
            'dff_sha256':hashlib.sha256(model).hexdigest(),'txd_sha256':hashlib.sha256(texture).hexdigest()}
    (BASE/'assets/build_report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='parts'},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--dragonff',required=True);build(p.parse_args().dragonff)
