## DSL IL — Semantics Descriptor 

This document defines a compact Intermediate Language (IL) to represent program-level semantics. It captures meaning-oriented concepts required for downstream mapping (e.g., to Messir/UCI) while remaining portable across languages and tools.

**Inclusions:**  
The semantics descriptor captures entities, roles, scopes, ownership, relations, operations (capabilities), effects, constraints, events, and interaction channels.

**Exclusions:**  
Implementation details such as concrete statements or expressions are intentionally omitted from the semantics representation.

### M2 — Metamodel Concepts (concise definitions with rationale)

- Entity: A named semantic kind (e.g., Turtle breed, Patch, Link, Globals) that aggregates attributes and capabilities; rationale: models domain-relevant actors/data in a language-neutral way.
- Role: A named viewpoint or responsibility assumed by an Entity (e.g., Observer, Turtle, Link scope); rationale: isolates responsibilities and contextual behavior.
- Attribute: A named semantic property of an Entity; rationale: captures state relevant to behavior and constraints.
- Relation: A typed association between Entities (e.g., adjacency, ownership, membership); rationale: encodes structural semantics beyond raw data shape.
- Scope: A named execution or addressing context (observer, turtles, links, patches); rationale: stratifies operations and visibility.
- Ownership: A directed governance link identifying which Role/Entity governs another Entity or attribute set; rationale: clarifies control/authority.
- Operation: A named capability available to a Role/Entity (analogous to a procedure/reporter at the semantic level) with a signature; rationale: exposes behavior without committing to implementation.
- Signature: The interface of an Operation (parameters and optional return type); rationale: supports composition and contract-based reasoning.
- Effect: A high-level effect category the Operation may produce (e.g., create, update, delete, relate, emit-event); rationale: aids reasoning about state changes without code.
- Constraint (Invariant): A condition intended to hold over Entities/Relations/Scopes (e.g., conservation, uniqueness); rationale: preserves intended properties.
- Event: A named occurrence in the model’s lifecycle that may be emitted/observed (e.g., tick advanced, agent spawned); rationale: describes temporal hooks.
- Channel: An interaction pathway used by Operations (e.g., broadcast/ask-like targeting); rationale: abstracts interaction patterns.
- View (Projection): A named, derived perspective over Entities/Relations/Attributes; rationale: supports queries/analytics without embedding expressions.

Notes:
- The IL is minimal and neutral. Rich typing or formal logic should live in separate descriptors.

### M1 — Model Structure (JSON template)

The following JSON template specifies the allowed structure for M1 instances. Keys and lists are deterministic to be LLM-friendly.

```json
{
  "model": {
    "name": "<string>",
    "entities": [
      {
        "name": "<string>",
        "roles": [ "<string>" ],
        "attributes": [ { "name": "<string>", "type": "<string>" } ],
        "operations": [
          {
            "name": "<string>",
            "signature": {
              "parameters": [ { "name": "<string>", "type": "<string>" } ],
              "returnType": "<string|null>"
            },
            "effects": [ "create" | "update" | "delete" | "relate" | "emit-event" ]
          }
        ]
      }
    ],
    "relations": [
      {
        "name": "<string>",
        "from": "<Entity>",
        "to": "<Entity>",
        "kind": "association|aggregation|composition|adjacency|membership|ownership",
        "cardinality": "<string>"
      }
    ],
    "scopes": [ "observer", "turtles", "patches", "links" ],
    "ownerships": [ { "owner": "<Role|Entity>", "owned": "<Entity|attribute-group>", "notes": "<string>" } ],
    "constraints": [ { "name": "<string>", "kind": "invariant|pre|post", "expression": "<string>" } ],
    "events": [ { "name": "<string>", "emittedBy": [ "<Operation>" ] } ],
    "channels": [ { "name": "<string>", "kind": "direct|broadcast|filter", "source": "<Role|Entity>", "target": "<Role|Entity|View>" } ],
    "views": [ { "name": "<string>", "of": "<Entity|Relation>", "predicate": "<string|null>" } ]
  }
}
```

Notes:
- Use simple type references for `type` fields (builtins like "any", "number", "string", or named Entities).
- Keep `effects` high-level; detailed dataflow or semantics belong in specialized descriptors.
- The `expression` and `predicate` fields are placeholders for human-readable intent, not executable code.




