"""Render the exported DFF or explicitly prepared mission-upgrade assembly.

blender -b --python geniusmobile/tools/render.py -- geniusmobile/dist/geniusmb.dff geniusmobile/previews/base
"""
import sys
import math
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
import rw_dff as rw
import struct

ROOT = Path(__file__).resolve().parents[1]
args = sys.argv[sys.argv.index('--') + 1:]
source = Path(args[0]).resolve()
prefix = Path(args[1]).resolve()
prefix.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
clump = rw.load(source.read_bytes())[0]
frames = rw.frames(clump)
geoms = clump.first(0x1a).find(15)
images = {}
for folder in [ROOT / 'assets/decoded', ROOT / 'assets']:
    for path in folder.glob('*.png'):
        images[path.stem] = bpy.data.images.load(str(path), check_existing=True)

primary = (0.43, 0.012, 0.008, 1)
secondary = (0.018, 0.019, 0.019, 1)
tertiary = (0.8, 0.79, 0.74, 1)
all_visible = []

def material(node, index):
    rgba = tuple(x / 255 for x in rw.material_colour(node))
    textures = node.find(6)
    name = textures[0].find(2)[0].data.rstrip(b'\0').decode('ascii') if textures else ''
    mat = bpy.data.materials.new(f'{index}_{name}')
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bs = nodes.get('Principled BSDF')
    color = primary if rgba[:3] == (60/255, 1, 0) else secondary if rgba[:3] == (1, 0, 175/255) else rgba
    if rgba[:3] == (0,1,1): color=tertiary
    # Light component RGB values are engine control tags, not the displayed tint.
    if tuple(round(c*255) for c in rgba[:3]) in [(255,175,0),(0,255,200),(185,255,0),(255,60,0)]:
        color = (1,1,1,1)
    bs.inputs['Base Color'].default_value = color
    bs.inputs['Roughness'].default_value = 0.43 if color == primary else 0.67
    if name in images:
        tex = nodes.new('ShaderNodeTexImage')
        tex.image = images[name]
        tex.interpolation = 'Linear'
        mix = nodes.new('ShaderNodeMixRGB')
        mix.blend_type = 'MULTIPLY'
        mix.inputs[0].default_value = 1
        mix.inputs[2].default_value = color
        links.new(tex.outputs['Color'], mix.inputs[1])
        links.new(mix.outputs[0], bs.inputs['Base Color'])
    if rgba[3] < 0.99:
        bs.inputs['Base Color'].default_value = (0.11,0.19,0.20,1)
        # A dark, mildly reflective pane is easier to compare than renderer refraction.
        bs.inputs['Metallic'].default_value = 0.28
        bs.inputs['Roughness'].default_value = 0.22
        bs.inputs['Alpha'].default_value = rgba[3]
    return mat

for atomic in clump.find(20):
    fi, gi = struct.unpack_from('<II', atomic.children[0].data)
    name = frames[fi][0]
    g = rw.Geometry(geoms[gi].children[0].data)
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(g.pos, [], [t[:3] for t in g.tris])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    r, p = rw.frame_to_root(frames, fi)
    obj.matrix_world = Matrix(((r[0][0],r[1][0],r[2][0],p[0]),
                               (r[0][1],r[1][1],r[2][1],p[1]),
                               (r[0][2],r[1][2],r[2][2],p[2]),(0,0,0,1)))
    for i, mat in enumerate(geoms[gi].first(8).find(7)):
        mesh.materials.append(material(mat, f'{name}_{i}'))
    for poly, tri in zip(mesh.polygons, g.tris):
        poly.material_index = tri[3]
        poly.use_smooth = True
    if g.uvs:
        uv = mesh.uv_layers.new(name='UVMap')
        for poly in mesh.polygons:
            for li in poly.loop_indices:
                u, v = g.uvs[0][mesh.loops[li].vertex_index]
                uv.data[li].uv = (u, 1-v)
    if g.nrm:
        mesh.normals_split_custom_set_from_vertices(g.nrm)
    damage='--damage' in args
    if damage:
        obj.hide_render = (name.endswith('_ok') and name!='exhaust_ok') or name=='chassis_vlo'
    else:
        obj.hide_render = name.endswith('_dam') or name == 'chassis_vlo'
    obj.hide_set(obj.hide_render)
    if not obj.hide_render:
        all_visible.append(obj)
    if name == 'wheel':
        for xsign, back in [(-1,False),(1,True),(-1,True)]:
            copy = obj.copy()
            copy.data = mesh
            bpy.context.collection.objects.link(copy)
            copy.name = 'preview_wheel_' + str(xsign) + str(back)
            # Stock game instantiates the RF wheel at all four wheel dummies.
            copy.matrix_world = Matrix.Diagonal((xsign,1,1,1)) @ obj.matrix_world
            if back:
                copy.location.y += next(f[2][1] for f in frames if f[0]=='wheel_rb_dummy') - next(f[2][1] for f in frames if f[0]=='wheel_rf_dummy')
            all_visible.append(copy)

collection = bpy.data.collections.new('Presentation only (not exported)')
bpy.context.scene.collection.children.link(collection)
def presentation(obj):
    for c in list(obj.users_collection): c.objects.unlink(obj)
    collection.objects.link(obj)

bpy.ops.mesh.primitive_plane_add(size=200, location=(0,0,-0.706))
ground = bpy.context.object
ground.name = 'Studio floor'
presentation(ground)
mat = bpy.data.materials.new('Warm gray floor')
mat.diffuse_color = (0.23,0.22,0.20,1)
ground.data.materials.append(mat)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 64
scene.cycles.use_denoising = False
scene.render.resolution_x = 1200
scene.render.resolution_y = 850
scene.render.resolution_percentage = 100
scene.world.color = (0.3,0.3,0.3)
scene.view_settings.view_transform = 'Standard'
scene.view_settings.look = 'Medium High Contrast'
for loc, power, size in [((2,4,8),1500,7),((-5,0,4),950,6),((0,-6,6),1200,5)]:
    data = bpy.data.lights.new('Softbox','AREA')
    data.energy, data.shape, data.size = power * 0.65, 'DISK', size
    light = bpy.data.objects.new('Softbox',data)
    collection.objects.link(light)
    light.location = loc
    light.rotation_euler = (Vector((0,0,0))-light.location).to_track_quat('-Z','Y').to_euler()
data = bpy.data.cameras.new('Camera')
cam = bpy.data.objects.new('Camera',data)
collection.objects.link(cam)
scene.camera = cam
data.type = 'ORTHO'
data.ortho_scale = 8.2
views=[('front',(7,10,5)),('rear',(-7,-10,4.3)),('side',(10,0,2.1))]
if '--front-only' in args: views=views[:1]
if '--rear-only' in args: views=[v for v in views if v[0]=='rear']
for view, location in views:
    cam.location = location
    cam.rotation_euler = (Vector((0,-0.15,0))-cam.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath = str(prefix) + '_' + view + '.png'
    bpy.ops.render.render(write_still=True)
for image in bpy.data.images:
    if image.source == 'FILE': image.pack()
bpy.ops.wm.save_as_mainfile(filepath=str(prefix.with_suffix('.blend')))
