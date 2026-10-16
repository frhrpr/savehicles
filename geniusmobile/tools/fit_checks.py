"""Independent surface-intersection probes for the exported lower body kit.

These inspect the actual exported triangles, not the builder's control points.
They catch the original sills' air gap and aprons attached only at the centre.
"""
import struct

import rw_dff as rw


def exported_parts(clump):
    frames=rw.frames(clump)
    nodes=clump.first(26).find(15)
    result={}
    for atomic in clump.find(20):
        fi,gi=struct.unpack_from('<II',atomic.children[0].data)
        g=rw.Geometry(nodes[gi].children[0].data)
        rotation,position=rw.frame_to_root(frames,fi)
        points=[tuple(sum(v[k]*rotation[k][j] for k in range(3))+position[j]
                      for j in range(3)) for v in g.pos]
        custom={i for i,m in enumerate(nodes[gi].first(8).find(7)) if m.find(6) and
                m.first(6).find(2)[0].data.rstrip(b'\0')==b'genius_detail128'}
        result[frames[fi][0]]=(points,g.tris,custom)
    return result


def sub(a,b):return tuple(x-y for x,y in zip(a,b))
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def cross(a,b):return a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]


def segment_triangle(a,b,p,q,r):
    direction=sub(b,a);e1=sub(q,p);e2=sub(r,p)
    h=cross(direction,e2);det=dot(e1,h)
    if abs(det)<1e-9:return None
    offset=sub(a,p);u=dot(offset,h)/det
    if not 0<=u<=1:return None
    side=cross(offset,e1);v=dot(direction,side)/det
    if v<0 or u+v>1:return None
    distance=dot(e2,side)/det
    if 1e-5<distance<1-1e-5:
        return tuple(x+distance*y for x,y in zip(a,direction))
    return None


def kit_intersections(new,donor):
    points,triangles,custom=new
    original,original_triangles,_=donor
    edges=set()
    for a,b,c,m in triangles:
        if m in custom:
            for i,j in [(a,b),(b,c),(c,a)]:edges.add(tuple(sorted((i,j))))
    hits=set()
    for i,j in edges:
        a,b=points[i],points[j]
        if max(a[2],b[2])>-.32:continue  # Exclude the bed cover and upper shell.
        for u,v,w,_ in original_triangles:
            hit=segment_triangle(a,b,original[u],original[v],original[w])
            if hit:hits.add(tuple(round(z,5) for z in hit))
    return hits


def check_fit(clump,donor,check):
    parts=exported_parts(clump);stock=exported_parts(donor)
    for name in ['chassis','bump_front_ok','bump_front_dam','bump_rear_ok','bump_rear_dam']:
        hits=kit_intersections(parts[name],stock[name])
        if name=='chassis':
            for sign in [-1,1]:
                for lo,hi in [(-.92,-.75),(-.75,1.11),(1.11,1.31)]:
                    check(any(p[0]*sign>1 and lo<=p[1]<=hi for p in hits),
                          f'Sill {sign}: exported skin enters stock rocker between y={lo} and {hi}')
        else:
            for lo,hi in [(-1.1,-.5),(-.5,.5),(.5,1.1)]:
                check(any(lo<p[0]<hi for p in hits),
                      f'{name}: apron intersects donor bumper in x interval {lo}..{hi}')
    # The exhaust tubes must enter the rear apron on both sides. Short loose
    # tips remain valid DFF geometry, but fail this physical attachment probe.
    exhaust_hits=kit_intersections(parts['exhaust_ok'],parts['bump_rear_ok'])
    for sign in [-1,1]:
        check(any(p[0]*sign>.65 for p in exhaust_hits),
              f'Exhaust {sign}: pipe intersects rear apron instead of floating')
    # Each door rotates around a vertical hinge. Verify all its vertices stay
    # above the actual new sill, on both sides and for both damage variants.
    kit_points,triangles,custom=parts['chassis']
    sill_top=max(kit_points[i][2] for t in triangles if t[3] in custom
                 for i in t[:3] if kit_points[i][2]<-.48)
    for name in ['door_lf_ok','door_rf_ok','door_lf_dam','door_rf_dam']:
        points=parts[name][0]
        check(min(p[2] for p in points)>sill_top+.004,
              f'{name}: vertical hinge swing clears sill by over 4mm')
    # This probe must reject the original failure mode, even if the entire kit
    # remains otherwise well formed and loadable.
    points,tris,custom=parts['chassis']
    detached=[(x+(.20 if x>0 else -.20),y,z) for x,y,z in points]
    check(not kit_intersections((detached,tris,custom),stock['chassis']),
          'Attachment regression rejects sills displaced 20cm out from body')
    # Scoop is attached to the bonnet along BOTH bottom returns, and remains
    # attached on the donor's damaged surface after the transferred deformation.
    for name in ['bonnet_ok','bonnet_dam']:
        points,triangles,custom=parts[name]
        original,ots,_=stock[name]
        def height(x,y):
            hits=[]
            for u,v,w,_ in ots:
                hit=segment_triangle((x,y,-2),(x,y,2),original[u],original[v],original[w])
                if hit:hits.append(hit[2])
            return max(hits) if hits else None
        for sign in [-1,1]:
            roots=[p for t in triangles if t[3] in custom for i in t[:3]
                   if (p:=points[i])[0]*sign>.32 and 1.09<p[1]<2.13]
            checked=[]
            for p in roots:
                z=height(p[0],p[1])
                if z is not None:checked.append(p[2]-z)
            check(checked and min(checked)<-.005 and max(checked)>.001,
                  f'{name}: scoop return overlaps bonnet on side {sign}')
    # Forward rays through the opening must hit an opaque custom surface.
    points,tris,custom=parts['bonnet_ok']
    for x in [-.26,0,.26]:
        for z in [.335,.375]:
            check(any(segment_triangle((x,2.3,z),(x,1.95,z),
                      points[a],points[b],points[c]) for a,b,c,m in tris if m in custom),
                  f'Scoop mouth is backed at x={x}, z={z}')
