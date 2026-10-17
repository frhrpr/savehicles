"""Create the flat game-asset package for the user's own IMG/IDE workflow."""
from pathlib import Path
import hashlib
import json
import zipfile

BASE=Path(__file__).resolve().parents[1]


def package():
    report=json.loads((BASE/'assets/validation_report.json').read_text())
    files={}
    for extension in ['dff','txd']:
        name='pip660.'+extension
        data=(BASE/'dist'/name).read_bytes()
        if hashlib.sha256(data).hexdigest()!=report[extension+'_sha256']:
            raise ValueError('Assets changed since validation')
        files[name]=data
    for path in sorted((BASE/'data').glob('*.snippet')):files[path.name]=path.read_bytes()
    files['INTEGRATION.md']=(BASE/'INTEGRATION.md').read_bytes()
    files['build_report.json']=(BASE/'assets/build_report.json').read_bytes()
    files['validation_report.json']=(BASE/'assets/validation_report.json').read_bytes()
    files['SHA256SUMS.txt']=''.join(hashlib.sha256(data).hexdigest()+'  '+name+'\n' for name,data in files.items()).encode()
    out=BASE/'dist/pip660.zip'
    with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name,data in sorted(files.items()):
            info=zipfile.ZipInfo(name,date_time=(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o644<<16
            archive.writestr(info,data)
    with zipfile.ZipFile(out) as archive:
        assert archive.testzip() is None
        for name,data in files.items():assert archive.read(name)==data
    print(f'Packaged and verified {out.name}: {out.stat().st_size:,} bytes')


if __name__=='__main__':package()
