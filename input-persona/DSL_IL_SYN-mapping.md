## NetLogo → DSL IL Mapping (NL-IL)

This file describes how NetLogo surface concepts are represented using the minimal IL defined in DSL_IL_SYN-description.md. Only high-level structure is mapped; concepts that are not mapped to the IL are excluded by design.

### Mapping Rules 

- NetLogo Model (.nlogo file) → Program: exactly one per file; Program.name = model filename.
- extensions [e1 e2 ...] → Import*: one Import per extension; Import.from = extension name; Import.alias = null.
- breeds (breed / directed-link-breed) → Declaration(Type):
  - Each breed becomes a Type with Type.name = BreedName (PascalCase recommended).
  - Fields come from the corresponding own-variables section (e.g., turtles-own, links-own) for that breed.
- turtles-own [vars...] (for a breed) → Field*: added to the Type of that turtle breed; Field.type = "any" unless a stronger convention exists.
- links-own [vars...] (for a link breed) → Field*: added to the Type of that link breed; Field.type = "any".
- patches-own [vars...] → Declaration(Type): a Type named "Patch" with one Field per variable; Field.type = "any".
- globals [vars...] → Declaration(Type): a Type named "Globals" with one Field per variable; Field.type = "any".
- observer (implicit) → Declaration(Type): optional Type named "Observer" if needed to host observer-scoped fields (rare); otherwise omit.
- to proc [args] → Function: Function.name = proc; Signature.parameters from args (Parameter.type = "any"); Signature.returnType = null.
- to-report proc [args] → Function: same as above, but Signature.returnType = "any" (or a named Type if known externally).
- Primitives (built-ins), statements, and expressions → not represented (out of scope for this IL).

### Normalization Notes

- Type names should be stable identifiers (e.g., `TurtleBreed` rather than pluralized lists); apply consistent casing.
- When NetLogo variables imply known domains (e.g., color, coordinates), keep `type = "any"` in this IL; richer typing belongs to a separate semantics descriptor.
- If a breed has no own-variables, it still maps to a Type with an empty fields list.
