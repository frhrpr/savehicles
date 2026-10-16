"""Small PC TXD reader for the formats used by this reference pack.

Pillow supplies the DXT decoder. No game textures are edited or resampled.
"""
from pathlib import Path
import struct
from PIL import Image


def chunks(data, start=0, end=None):
    end=len(data) if end is None else end
    while start+12<=end:
        kind,size,version=struct.unpack_from('<III',data,start)
        if start+12+size>end: raise ValueError('Truncated RenderWare chunk')
        yield kind,data[start+12:start+12+size]
        start+=12+size


def read_txd(path):
    result={}
    dictionary=next(chunks(Path(path).read_bytes()))
    if dictionary[0]!=0x16: raise ValueError('Expected a TXD')
    for kind,body in chunks(dictionary[1]):
        if kind!=0x15: continue
        native=next(body for k,body in chunks(body) if k==1)
        platform=struct.unpack_from('<I',native)[0]
        name=native[8:40].split(b'\0')[0].decode('ascii')
        flags,fmt,w,h,depth,count,raster,properties=struct.unpack_from('<IIHHBBBB',native,72)
        if platform!=9 or flags&0x6000: raise ValueError('Only non-paletted PC D3D9 textures are supported')
        pos=88
        levels=[]
        for i in range(count):
            size=struct.unpack_from('<I',native,pos)[0];pos+=4
            pixels=native[pos:pos+size];pos+=size
            width,height=max(1,w>>i),max(1,h>>i)
            if fmt in [827611204,861165636,894720068]:
                code={827611204:(1,'DXT1'),861165636:(2,'DXT3'),894720068:(3,'DXT5')}[fmt]
                im=Image.frombytes('RGBA',(width,height),pixels,'bcn',code)
            elif fmt in [21,22]:
                if len(pixels)!=width*height*4: raise ValueError('Unexpected native raster stride')
                im=Image.frombytes('RGBA',(width,height),pixels,'raw','BGRA')
                if fmt==22: im.putalpha(255)
            else: raise ValueError(f'Unsupported D3D format {fmt}')
            levels.append(im)
        if pos!=len(native): raise ValueError('Unexpected native raster data')
        result[name]=levels
    return result


def prepare():
    root=Path(__file__).resolve().parents[1]
    dest=root/'reference/textures';dest.mkdir(parents=True,exist_ok=True)
    for file in ['premier.txd','generic/vehicle.txd']:
        for name,images in read_txd(root/'reference/gtasa_vehicle_reference/models'/file).items():
            images[0].save(dest/(name+'.png'))
    print('Decoded donor and shared textures for Blender previews.')


if __name__=='__main__': prepare()
