"""Import delivered assets with DragonFF and retain the native export rig.

blender -b --python geniusmobile/tools/blender_source.py -- /path/to/DragonFF
DragonFF commit used for this MVP: 54baca8ea2ed95fe5a86917f44399ce677379c59.
The addon is an external GPL dependency, not bundled with this project.
"""
import importlib.util
import hashlib
from pathlib import Path
import sys
import bpy

root=Path(__file__).resolve().parents[1]
addon=Path(sys.argv[sys.argv.index('--')+1]).resolve()
spec=importlib.util.spec_from_file_location('dragonff',addon/'__init__.py',submodule_search_locations=[str(addon)])
module=importlib.util.module_from_spec(spec)
sys.modules['dragonff']=module
spec.loader.exec_module(module)
module.register()
from dragonff.ops import dff_importer

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
images={}
for folder in [root/'assets/decoded', root/'assets']:
    for path in folder.glob('*.png'):
        images[path.stem]=[bpy.data.images.load(str(path),check_existing=True)]
result=dff_importer.import_dff({
    'file_name':str(root/'dist/geniusmb.dff'),
    'txd_images':images,'image_ext':'png','connect_bones':False,
    'use_mat_split':True,'remove_doubles':False,'create_backfaces':False,
    'group_materials':False,'import_normals':True,'materials_naming':'TEX',
    'hide_damage_parts':True,
})
for obj in bpy.data.objects:
    if obj.name.endswith('_dam') or obj.name=='chassis_vlo':
        obj.hide_render=True;obj.hide_set(True)
# Imported collision data remains hidden in the collision collection.
for image in bpy.data.images:
    if image.source=='FILE' and not image.packed_file:
        # File images are lazy-loaded in background Blender; packing must not
        # be conditional on has_data before the pixel buffer is requested.
        if not image.filepath: raise RuntimeError('Image has no backing path: '+image.name)
        image.pack()
assert all(image.packed_file for image in bpy.data.images if image.source=='FILE' and image.users), 'Unpacked image in source'
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.region_3d.view_distance=9
            area.spaces.active.shading.type='MATERIAL'
bpy.context.scene['source_dff_sha256']=hashlib.sha256((root/'dist/geniusmb.dff').read_bytes()).hexdigest()
bpy.context.scene['source_txd_sha256']=hashlib.sha256((root/'dist/geniusmb.txd').read_bytes()).hexdigest()
bpy.ops.wm.save_as_mainfile(filepath=str(root/'assets/geniusmb.blend'))
print('Native hierarchy, damage variants, materials and collision imported into assets/geniusmb.blend')
