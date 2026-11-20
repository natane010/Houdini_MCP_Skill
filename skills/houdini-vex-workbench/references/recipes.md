# Standard node alternatives for existing VEX

Choose the operator based on the original run-over class, input attributes, and required output. Check the available types and parameters in the current Houdini session.

| Behavior to preserve | Standard SOP operators |
| --- | --- |
| Set a constant point scale or custom attribute | Attribute Create |
| Vary point scale or color with a seed | Attribute Randomize |
| Select or combine groups and remove geometry | Group Create, Group Combine, Blast |
| Remap, copy, or change the class of an attribute | Attribute Adjust Float, Attribute Copy, Attribute Promote |
| Attribute-driven point instancing | Attribute Randomize or Attribute Adjust, then Copy to Points |
| Offset along normals by a fixed amount | Normal, then Peak |

Inspect both sides of the change. For instancing, typically verify point `pscale` as a single float and point `orient` as a quaternion when the network needs it. Check point and primitive counts, relevant attributes, and the final owner's class before saving the HIP or publishing an HDA.
