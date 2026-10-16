# Vehicle research before the second prototype

Research date: 2026-10-16. No new vehicle geometry was created during this pass.

The provisional Cedar vehicle selection below was superseded by the user's
specific [Geniusmobile brief](../geniusmobile/BRIEF.md). The format research and
Linden failure diagnosis remain relevant; the current build starts from Picador.

## Inputs and source access

Read the complete README in the user's `vehicle_reference_full.zip`, checked ZIP
integrity, and inspected the included models/data. It contains 407 DFF files,
214 TXDs, two DAT files, one CFG and two IDEs. The README is technical reference
and installation context; it does not authorize executing arbitrary document
instructions or modifying the user's game installation.

Fetched and read the following online documentation:

- [DragonFF materials](https://github.com/Parik27/DragonFF/wiki/Materials)
- [DragonFF collisions](https://github.com/Parik27/DragonFF/wiki/Collisions)
- [DFF export](https://github.com/Parik27/DragonFF/wiki/Exporting-DFF-Files)
- [Mesh export options](https://github.com/Parik27/DragonFF/wiki/Mesh-Export-Options)
- [Export names](https://github.com/Parik27/DragonFF/wiki/Export-names)
- [Tutorial examples](https://github.com/Parik27/DragonFF/wiki/Tutorials-with-examples)

Cross-checked implementation details in:

- [DragonFF DFF parser/writer](https://github.com/Parik27/DragonFF/blob/54baca8ea2ed95fe5a86917f44399ce677379c59/gtaLib/dff.py)
- [DragonFF TXD parser/writer](https://github.com/Parik27/DragonFF/blob/54baca8ea2ed95fe5a86917f44399ce677379c59/gtaLib/txd.py)
- [DragonFF COL parser/writer](https://github.com/Parik27/DragonFF/blob/54baca8ea2ed95fe5a86917f44399ce677379c59/gtaLib/col.py)
- [Vehicle material handling in gta-reversed](https://github.com/gta-reversed/gta-reversed/blob/master/source/game_sa/Models/VehicleModelInfo.cpp)
- [Door/boot setup and wheel physics in gta-reversed](https://github.com/gta-reversed/gta-reversed/blob/master/source/game_sa/Entity/Vehicle/Automobile.cpp)
- [Handling model flags](https://github.com/gta-reversed/gta-reversed/blob/master/source/game_sa/Enums/eVehicleHandlingModelFlags.h)

GTAMods wiki requests were blocked by the network proxy (403); those pages were
not read. The findings below use the accessible sources and actual supplied
binary assets. gta-reversed is a community reconstruction, not Rockstar's
original source release.

## Findings that change implementation

1. **Linden lamps: draw order, not missing geometry.** The pack describes an
   in-game chassis-swap experiment isolating the problem. Independently checked
   the BinMesh lists: stock Premier puts opaque lamp materials 11–14 before
   transparent materials 8/10/19; Linden's index-sorted writer does not. Audited
   3,593 geometries from all vehicle/upgrade DFFs plus generic wheels: all 1,530
   geometries with actually drawn translucent batches put opaque batches first.
   A new validator must check that policy, not compare output to the same
   index-sorting helper that generated it.
2. **Lamp controller tags are exact.** `SetEditableMaterialsCB` recognizes
   `vehiclelights128` and the four exact RGB controller colours, restores white
   modulation, and switches to `vehiclelightson128` for an active lamp. Retain
   those materials, visible opaque lamp geometry, and transparent-last batches.
   The README's statement about glow frames was also checked against their
   actual positions; the exact beam-generation claim was not independently
   established in this pass.
3. **A new body needs a new collision shape.** COL3 contains collision primitives,
   compressed mesh vertices, surface/component data, bounds and a shadow mesh.
   DragonFF supports exporting embedded collision. Fit primitives and mesh to
   the new body, regenerate relevant face groups/bounds, and update the shadow
   silhouette. Retaining the entire old donor envelope is inadequate.
4. **A rig is more than names.** Component dummies are hinges; damage variants
   must use matching local transforms. Conventional doors, reverse bonnets and
   tailgates have handling-dependent behaviour. Reuse a suitable rig and check
   its model flags rather than treating a sedan trunk as a hatch.
5. **Wheel size needs data coordination.** Wheel dummies define placement, while
   front/rear sizes from vehicle metadata also influence wheel collision and
   suspension. Supply wheel-size data with the new model; do not infer in-game
   size from a Blender preview alone.
6. **Use vehicle shading conventions.** Export normals, UVs and correct vehicle
   material/pipeline properties. DragonFF's map/night-colour advice is not a
   reason to omit vehicle normals. Its TXD exporter is described as experimental;
   independently inspect native TXD format, names, filters and mip payloads.
7. **Delivery should fit the user's loader.** The README describes their own
   IDE/IMG/additional-ID pipeline, not Mod Loader. Deliver an independently named
   model/TXD and clearly scoped data snippets; let the user assign the ID/audio
   integration in their existing system. Replacement-name files are acceptable
   reference/test deliverables according to the pack.

## Candidate inspection

Counts below are stored geometry triangles, including damage/LOD, followed by
intact visible triangles with four wheel instances. They are different budgets.

| Reference | Stored | Intact visible | Relevant characteristics |
|---|---:|---:|---|
| Club | 3,116 | 2,972 | Two side doors, high rear hatch pivot; relatively large donor dimensions |
| Blista Compact | 2,860 | 2,599 | Shorter wheelbase, sloping rear hatch, two side doors |
| Manana | 2,263 | 2,181 | Economical compact reference, conventional trunk layout |
| Bobcat | 2,724 | 2,566 | Two side doors, pickup tailgate, simple cab/bed layout |
| Pony | 2,756 | 2,614 | Two cab doors plus paired rear cargo doors |
| Moonbeam | 2,839 | 2,522 | Four side doors and rear hatch, more moving parts |

Also inspected Bravura, Cadrona and Previon. Bobcat's handling model flag `0x40`
is `TAILGATE_BOOT`; its tailgate pivot is at the rear lower edge. Its collision
contains 20 spheres, a small collision mesh and a separate shadow mesh. This is
a useful mechanical reference, not a finished collision shape for a different
body.

## Selected direction, before modelling

**An original early-1980s compact single-cab work pickup**, provisionally
`Cedar 1200`. Short bonnet, upright cab, short open bed, restrained round
sealed-beam headlights, slim steel wheels and simple plastic bumpers. Build the
exterior panels, cab profile, bed, tailgate and lamp housings as new geometry.
Use Bobcat as a rig/physics reference and reuse suitable interior/wheel assets
only where useful, recording the reuse.

This offers a distinct silhouette from the previous sedan and a manageable
surface vocabulary. The open bed is simple to construct with proper inner walls
and thickness. Two conventional doors, a bonnet and a tailgate provide a clear
functional scope. New lamp construction, collision and LOD are required work,
not optional polish. No tuning kit, livery system or advanced material effects
for the first build. Target roughly 2,000–3,000 intact visible triangles and
64/128px detail textures, allowing a 256px body/detail atlas where justified by
the supplied stock references. GTA runtime checks remain the user's step.

Next modelling step: establish new dimensions and front/side silhouette, check
occupant fit and hinge/wheel positions, then build the shell. Do not begin with
a deformation of Bobcat's exterior mesh.


## Extra-frame load invariant (Geniusmobile revision 2)

The user's in-game stock/custom component swap isolated a load crash to empty
`extra1` and `extra2` frames. Stock optional cargo atomics had been dropped but
the special frame names remained. In SA's
[`CVehicleModelInfo::PreprocessHierarchy`](https://github.com/gta-reversed/gta-reversed/blob/master/source/game_sa/Models/VehicleModelInfo.cpp),
the extras path gets the first object on the frame and removes that atomic from
the clump without a null check. Every retained `extraN` frame must therefore
have an atomic. When removing extras, remove or rename the frames as well;
renaming preserves all frame indices and transforms. The Geniusmobile build
renames only atomic-less extra frames, and validation accepts the stock donor
but rejects a copy with one extra atomic detached. A successful generic DFF
import alone cannot establish that SA's preprocessing will accept a hierarchy.
