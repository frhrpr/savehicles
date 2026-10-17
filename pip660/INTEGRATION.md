# Pip — integration

The displayed vehicle name is **Pip**. Map your game-name/GXT key to `Pip`;
`PIP660` in the supplied snippet is an internal key, not the display label.

Use `pip660.dff` and `pip660.txd` together in your IMG. Give the vehicle a free
ID through your existing loader and configure its audio and game-name key in
your usual way. Keep the vehicle type **`car`**, animation field **`null`** and
both IDE wheel scales **`0.58`**. Snippets are included for `vehicles.ide` and
`handling.cfg`; substitute your own ID in the IDE line. The handling line is a
starting tune, not an in-game-verified setup. Wheelbase and suspension mounts
are already authored for this smaller car.

For a simple replacement test, use Manana ID 410 and your usual replacement
process: rename the model to `manana.dff`, keep its IDE TXD column as `pip660`,
and install `pip660.txd`. Use the supplied wheel scales and, preferably, the
PIP660 handling line. Keep your existing install backed up. Do not use the
unchanged Manana wheel scales: its wheels are larger.

The vehicle has **two seats**, two conventional doors, a front-opening bonnet
hinged by the windscreen, and a roof-hinged rear hatch using the stock boot
component. Body is paint colour 1; roof and mirror caps are colour 2. Choose
colours through your existing carcols/script pipeline. The preview uses sage
green and cream; it is a Blender render, not a screenshot from SA.

All visible meshes are new, including the two-seat interior and small steel
wheels. The Manana supplies the frame hierarchy, atomic bindings, vehicle
material conventions and render plugins. Stock `vehicle.txd` supplies the
switchable lamp texture and generated plate texture; the local TXD adds one
128×128 diffuse texture with eight mips. Do not replace shared `vehicle.txd`.

No original Manana upgrades are supported. Its `ug_*` frames have ordinary
unused names, so a spoiler/skirt cannot appear at a mismatched old mount. Do
not copy its carmods entry. There are no optional `extraN` frames.

The exported DFF/TXD pass independent DragonFF reads, complete attribute and
index checks, opaque-before-transparent draw order, exterior glass/lamp winding,
paint/lamp tags, wheel/hinge placement, door-to-sill clearance, closed collision
and shadow checks. All damage parts and the LOD are present. The new collider
and damage spheres match the smaller silhouette; the original sedan collider
is not reused.

**Pending in GTA SA:** load/spawn, wheel/suspension ride height, adult rider
alignment and entry/exit, head/brake lights and lamp damage, hatch/bonnet/door
opening and detachment, damage swaps, LOD transition, and driving/collision.
The open-panel preview is an offline hinge pose, not a game test. Inherited SA
entry animations may need placement refinement after that first test.
