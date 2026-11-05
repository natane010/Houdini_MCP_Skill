---
name: houdini-cop-workbench
description: Inspect, create, and tune Houdini Copernicus and legacy COP image networks, validating layers and resolution without implicit image exports.
---

# Houdini COP workbench

Inspect the Houdini version, existing network and its child type category before choosing node names. Houdini 22.0.368 has modern Copernicus `copnet` with category `Cop` and legacy `cop2net` with category `Cop2`; they are distinct systems. Discover node types and parameters in the running version instead of assuming a recipe transfers across versions. Prefer changing requested existing nodes, preserving their paths, connections and expressions. Inspect first and compare after each targeted edit.

In Houdini 22.0.368, this small modern Copernicus example was validated in an isolated hython scene: create a `copnet` under `/obj`, set its `setres` to 1 and `res` tuple to `(64, 64)`, create `constant` and `blur` inside, and connect blur input 0 to constant. The blur parameter `size` exists in this version. Force a cook only when needed, check `errors()` and `warnings()`, then retrieve `blur.layer()` and report its `displayWindow()`, `bufferResolution()`, `channelCount()` and `typeInfo()`. `layer()` can cook the node; it is not a read-only inspection. The constant image is intentionally minimal, useful for proving graph operation rather than judging blur visually. For a meaningful effect, use a user-authorized image or nonuniform input and inspect its actual available types and parameters.

The isolated validation returned display window `[0, 0, 64, 64]`, buffer resolution `(64, 64)`, one channel, `imageLayerTypeInfo.Raw`, and no cook errors or warnings. This is an example observation, not a promise for other networks or Houdini versions. A COP may have multiple outputs; report the output index and each layer requested when relevant.

For executable examples and an existing-node adjustment, read [references/cop-recipes.md](references/cop-recipes.md).

Do not perform costly full-resolution cooks or rendering by default. Only write image files when a destination is explicitly provided; check for an existing destination and respect overwrite intent. A scene or image export is distinct from evaluating a COP. COP layer retrieval and pixel evaluation may consume GPU/CPU resources; report actual resolution and channels, not assumed ones. For legacy COP2, discover and validate separately rather than applying the modern recipe.
