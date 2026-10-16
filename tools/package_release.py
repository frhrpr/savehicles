"""Package the validated DFF/TXD pair for Mod Loader without extra dependencies."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT=Path(__file__).resolve().parents[1]
MODEL=ROOT/'dist/modloader/linden'

instructions='''LINDEN 1800 — GTA SAN ANDREAS PC MVP

Replaces Premier, vehicle ID 426. Designed for classic downgraded SA 1.0.

INSTALL (with Mod Loader already installed):
Copy the modloader/linden folder into your GTA San Andreas game folder.
The two files should end up at:
  GTA San Andreas/modloader/linden/premier.dff
  GTA San Andreas/modloader/linden/premier.txd
Disable other Premier replacements. Start the game and find/spawn a Premier.

Uses stock Premier handling, colours, name and audio. No data-file edits or
limit adjuster are needed. Uninstall by removing modloader/linden.

SCOPE:
This is a Premier-derived proof of concept, not a scratch-built vehicle.
It includes body shape edits, a new grille, rear garnish, wheel-cover UVs and
a 128x128 diffuse atlas with mipmaps. The donor interior, rig, damage parts,
conservative original collision and shared game textures are retained.

VALIDATION:
Structural file checks passed; exact checks and hashes accompany this archive.
GTA SA was not available to run here. In-game lights, doors, damage, collision,
tuning and LOD behaviour still need testing. Blender previews are offline
renders, not game screenshots. Use on a test install first.

Sources, editable Blender file and build tools are in the savehicles checkout.
'''


def package():
    report=json.loads((ROOT/'assets/validation_report.json').read_text())
    files={f'modloader/linden/{name}':(MODEL/name).read_bytes() for name in ['premier.dff','premier.txd']}
    for suffix in ['dff','txd']:
        data=files[f'modloader/linden/premier.{suffix}']
        if hashlib.sha256(data).hexdigest()!=report[suffix+'_sha256']:
            raise RuntimeError('Assets changed after validation; rerun validation before packaging')
    sums=''.join(hashlib.sha256(data).hexdigest()+'  '+name+'\n' for name,data in files.items())
    files.update({'INSTALL.txt':instructions.encode('utf-8'),
                  'SHA256SUMS.txt':sums.encode('ascii'),
                  'build_report.json':(ROOT/'assets/build_report.json').read_bytes(),
                  'validation_report.json':(ROOT/'assets/validation_report.json').read_bytes()})
    path=ROOT/'dist/linden-mvp.zip'
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name,data in sorted(files.items()):
            info=zipfile.ZipInfo(name,date_time=(2026,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o644<<16
            archive.writestr(info,data)
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None: raise RuntimeError('ZIP integrity check failed')
        for name,data in files.items():
            if archive.read(name)!=data: raise RuntimeError('Packaged file differs from validated output')
    print(f'Packaged and verified {path.name}: {path.stat().st_size:,} bytes')


if __name__=='__main__': package()
