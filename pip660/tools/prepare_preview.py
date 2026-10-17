"""Decode the delivered TXD and stock shared textures for offline previews."""
from pathlib import Path
import sys
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE.parent/'tools'))
from txd_textures import read_txd
out=BASE/'assets/decoded';out.mkdir(exist_ok=True)
for path in [BASE/'donor/vehicle.txd',BASE/'dist/pip660.txd']:
    for name,levels in read_txd(path).items():levels[0].save(out/(name+'.png'))
print('Decoded delivered and shared textures for preview')
