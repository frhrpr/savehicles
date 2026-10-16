# Geniusmobile — integration note

Use **`geniusmb.dff` and `geniusmb.txd` together** in your own IMG. Keep your
existing vehicle ID, handling ID, audio configuration and game-name text key.
In its IDE entry, change the **TXD column from `picador` to `geniusmb`**. The
new dictionary retains the two Picador textures and adds `genius_detail128`.

## Revision 2 — replace the old DFF

Fixes the load crash from empty `extra1`/`extra2` frames by renaming them to
ordinary `cargo_removed_*` frames. Every remaining `extraN` must have an atomic;
removing only its geometry/atomic is unsafe in SA. The build and validator now
enforce this. The TXD is unchanged from revision 1.

Rebuilt the sills and lower aprons with actual joins to the donor body/bumper
surfaces. Replaced the tall box scoop with a lower arched opening, rounded
shoulders and a tapered rear ramp. Its mouth remains opaque-backed.

## Built into the model

- A fitted, forward-facing ram-air scoop, on both bonnet variants.
- Painted front/rear lower valances, a front intake and side sills.
- A near-black hard bed cover with bright edge trim and a small latch.
- Twin polished exhaust tips; the exhaust particle point is at the right tip.
- Twin racing stripes across the body, bonnet, tailgate and cover, using
  **paint colour 3** throughout. Body remains colour 1; bed/cover are colour 2.
- Matching LOD details, no optional bed clutter, fitted COL3 additions, and
  closed shadow volumes for the cover and lower trim.

The Picador cab, wings, wheelbase, original lamps, doors and tailgate remain.
The donor dirt/wear is retained: Ryder's old pickup has acquired an expensive,
somewhat excessive street-truck conversion.

## Mission/mod-shop changes

| Action | Upgrade |
|---|---|
| **Keep** | Dollar wheels **1083**, round spotlights **1013**, stereo **1086**, hydraulics **1087**, your chosen nitro **1008/1009/1010** |
| **Remove** | Bonnet scoops **1004/1005**: a custom scoop is built in |
| **Remove** | Roof scoop **1006**: deliberately omitted to keep the cab readable |
| **Remove** | Side skirts **1007/1017**: built-in sills replace them |
| **Remove** | Picador exhaust upgrades **1018/1020/1022**: built-in twin tips replace them |

Remove those conflicting items from the model's allowed `carmods.dat` list too,
if upgrades remain purchasable. Optional cargo atomics are already removed.
The nitro mount is moved under the cover so all three retained bottle variants
can fit; performance and upgrade scripting remain yours.

Keep your red / near-black / white setup (`car4` colours **3,36,1,0**, as in your
earlier example). **Do not run the stripe-cutting step again**: stripes are
already geometry with colour-3 materials. Keep the front/rear wheel scales at
**0.7** initially. No suspension or handling changes are required by the model.

For smoke from both tips, OR **`0x2000` (`DOUBLE_EXHAUST`)** into your existing
handling **model flags**, preserving the other bits, including the Picador's
tailgate flag. This is separate from the handling-flags field.

## Checked here / pending in game

Your revision-1 in-game diagnosis confirmed that geometry, textures, collision,
lamps, paint and draw order loaded correctly once the empty extras were fixed.
Revision 2 has not yet been tested in GTA here.

507 asset checks passed, including transparent-last draw order, original lamp
geometry/material preservation, paint modulation, damage/LOD structure, native
format reads, a collision probe hitting the new bed cover, and independent
attachment probes for the sills, both bumper variants and both scoop variants.
The validator
also rejects the old Linden chassis's incorrect draw order. Native Blender
source reopens with embedded, readable textures.

**GTA runtime checks remain pending:** lights/brakes and individual lamp damage,
door/bonnet/tailgate operation, damage swaps and detachment, LOD transitions,
spotlight fit, hydraulics at minimum height, and collision/bullet behaviour.
Offline renders include a labelled mission-upgrade view with stock 1083/1013;
those two upgrades are **not baked into the delivered DFF**.
