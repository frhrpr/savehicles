"""Decode textures and assemble a labelled mission-upgrade preview model.

The actual game deliverable remains dist/geniusmb.dff. This temporary assembly
adds only the stock Dollar wheel and spotlights retained in the mission.
"""
from pathlib import Path
import copy
import struct
import sys

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE.parent/'tools'))
import rw_dff as rw
from txd_textures import read_txd


def prepare():
    decoded=BASE/'assets/decoded';decoded.mkdir(exist_ok=True)
    for path in [BASE/'donor/vehicle.txd',BASE/'donor/picador.txd',BASE/'dist/geniusmb.txd']:
        for name,levels in read_txd(path).items(): levels[0].save(decoded/(name+'.png'))
    model=rw.load((BASE/'dist/geniusmb.dff').read_bytes())[0]
    frames=rw.frames(model);geometries=model.first(26).find(15)
    for a in model.find(20):
        fi,gi=struct.unpack_from('<II',a.children[0].data)
        if frames[fi][0]=='wheel':
            upgrade=rw.load((BASE/'donor/wheel_lr2.dff').read_bytes())[0].first(26).find(15)[0]
            g=rw.Geometry(upgrade.children[0].data)
            g.pos=[tuple(c*.7 for c in v) for v in g.pos]
            x,y,z,r=struct.unpack('<4f',g.sphere);g.sphere=struct.pack('<4f',x*.7,y*.7,z*.7,r*.7)
            upgrade.children[0].data=g.pack()
            for e in upgrade.find(3):
                for p in e.children:
                    if p.type==0x50e:p.data=g.bin_mesh()
            model.first(26).children[gi+1]=upgrade
    # Attach the existing round spotlight asset at its original Picador mount.
    spots=rw.load((BASE/'donor/lgt_b_rspt.dff').read_bytes())[0].first(26).find(15)[0]
    gl=model.first(26);index=len(gl.find(15));gl.children.append(spots)
    gl.children[0].data=struct.pack('<I',index+1)
    frame_index=next(i for i,f in enumerate(frames) if f[0]=='ug_lights')
    atomic=copy.deepcopy(model.find(20)[0]);raw=bytearray(atomic.children[0].data)
    struct.pack_into('<II',raw,0,frame_index,index);atomic.children[0].data=bytes(raw)
    model.children.insert(-1,atomic)
    raw=bytearray(model.children[0].data);struct.pack_into('<I',raw,0,len(model.find(20)));model.children[0].data=bytes(raw)
    (BASE/'assets/mission_preview.dff').write_bytes(rw.write([model]))
    print('Prepared textures and mission-upgrade assembly (Dollar 1083, spotlights 1013).')


if __name__=='__main__':prepare()
