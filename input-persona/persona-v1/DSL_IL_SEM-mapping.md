## NetLogo → DSL IL SEM Mapping (NL-SEM)

This file describes how NetLogo semantic surface is represented using the minimal semantics IL defined in `DSL_IL_SEM-description.md`. Only high-level semantics are mapped; statements and expressions are excluded by design.

### Mapping Rules

- Model (.nlogo) → model.name: set to the file name (or canonical model name).
- Scopes (implicit in NetLogo) → scopes: include `observer`, `turtles`, `patches`, `links` as present.
- Breeds (breed / directed-link-breed) → Entity:
  - Create an Entity with `name = BreedName` (PascalCase recommended).
  - Add Role(s) that reflect the NetLogo scope (e.g., `Turtle`, `Link`).
  - Attributes from corresponding own-variable sections become semantic Attributes with `type = "any"` by default.
- turtles-own / links-own / patches-own → Attributes:
  - Each variable becomes an Attribute on the corresponding Entity (`type = "any"`).
- globals → Entity("Globals"):
  - Represent globals as an Entity named `Globals` with Attributes for each global variable.
  - Optionally relate `Globals` to roles that primarily own or govern them (e.g., Observer ownership).
- patches (implicit) → Entity("Patch") with optional Attributes (from patches-own); add Role `Patch`.
- links (implicit) → Entity for each link breed or a generic `Link` when untyped; add Role `Link`.
- Procedures `to` / Reporters `to-report` → Operations:
  - Each procedure/reporter maps to an Operation on the Role/Entity most natural for its scope.
  - Signature.parameters derive from the NetLogo argument list with `type = "any"`.
  - Signature.returnType = `null` for `to`, and `"any"` (or known semantic type) for `to-report`.
  - Effects: annotate high-level intent if evident (e.g., `update`, `create`, `relate`, `emit-event`).
- ask / with / of patterns → Channels and Relations:
  - Use Channel.kind = `direct|broadcast|filter` to capture interaction style.
  - Relations can capture stable structural semantics (e.g., membership, adjacency) independent of runtime selection.
- Ownership:
  - Use ownerships to indicate governance (e.g., Observer owns Globals; a model governance role may own creation of agents).
- Constraints (Invariants):
  - Encode persistent properties (e.g., counts non-negative) as `constraints` with kind `invariant`.
- Events:
  - Introduce Events for notable lifecycle changes (e.g., tick advanced, agent spawned); associate emitting Operations when known.

### Normalization Notes

- Prefer stable Entity names; use PascalCase for Entities/Roles.
- Keep Attribute `type = "any"` unless a stable domain is known. Richer domains belong to separate descriptors.
- If a breed has no own-variables, still create an Entity with an empty `attributes` list.
- Keep effects high-level and optional when intent is unclear.
