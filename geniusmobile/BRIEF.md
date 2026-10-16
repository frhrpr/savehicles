# The Geniusmobile: model brief

## What it is
SAVibe is a GTA San Andreas mission overhaul. The Geniusmobile is the car you win by finding an easter egg in an early
mission: Ryder's beat-up Picador (a small pickup) after someone has spent a stupid amount of money on it.

It should still read as a Picador at a glance, just one that has been lovingly, expensively and somewhat pointlessly
built up. Keep it in GTA's tone: a bit much, but not a cartoon.

## What it is now
`picador.dff` with racing stripes cut into the body by our build script. The script marks the stripes with paint
colour 3, so the colours are red body, a near-black bed and white stripes. Ryder's mission also adds stock mod-shop
parts:
- large bonnet scoop
- roof scoop
- side skirts
- nitro
- round spotlights
- twin exhaust
- Dollar wheels
- stereo
- hydraulics

It also hides the Picador's bed clutter.

## What we want
A model of its own, `geniusmb.dff` (plus a TXD if it needs its own textures), that takes the idea further than
stripes and stock parts. What that means is up to you: what would such a build have, what's the right amount, and
what to leave alone so it stays a Picador.

The stock mod-shop parts it gets now can stay, go, or be replaced by things built into the model. Tell us which, and
we'll change the mission to match.

## Constraints
- **Starting point:** start from `models/vehicles/picador.dff` in the reference pack you already have
  (`gtasa_vehicle_reference/`). Its README lists the non-obvious rules. Draw order and the light frames have
  already caught us out once.
- **Paint:** keep the body paintable through the colour materials. `carcols.dat` and scripts set the colours, and
  the stripes should stay paint colour 3, whether you model them in or leave them to our script.
- **Must still work:** damage parts, lights, doors and the low-detail model.
- **Collision:** rebuild it if the shape changes enough to matter.
- **Handling and sound:** we do the data side (handling, sound, colours, which parts fit). Suggest changes if the
  build calls for them, e.g. wheel size.

## What to send back
- The DFF, and the TXD if any.
- A short note: what you built, anything we need to change on our side, and what you couldn't check. We test in game
  and report back.
