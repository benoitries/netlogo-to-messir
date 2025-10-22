## DSL IL — Syntax Descriptor (for PSN1)

This document specifies which aspects of a program are included and excluded in the minimal intermediate language (IL) syntax.

**Inclusions:**  
- High-level structural constructs only:  
  - Program  
  - Import  
  - Declaration  
  - Type (and Fields)  
  - Function (with Signature and Parameters)  

**Exclusions:**  
- Statements and expressions (by design, not represented)  
- Any logic beyond structural representation  

This ensures the abstraction remains portable and language-agnostic.

### M2 — Metamodel Concepts (concise definitions with rationale)

- Program: The root container of a compilation unit (model or module); rationale: provides a single entry point to hold language-agnostic structure.
- Import: A reference to external modules or namespaces; rationale: captures inter-module dependencies without embedding semantics.
- Declaration: A named binding that introduces a Type into scope; rationale: standardizes how named data shapes enter the program.
- Type: A named data shape describing records or nominal entities; rationale: enables structural modeling independent of execution.
- Field: A named member of a Type paired with a type reference; rationale: composes complex data from simpler parts.
- Function: A named callable abstraction with a signature only (no body); rationale: exposes capabilities without committing to behavior.
- Signature: The I/O contract of a Function (parameters and optional return type); rationale: supports interface-level reasoning and composition.
- Parameter: A named, typed input in a function signature; rationale: defines how data flows into functions in a language-neutral way.

### M1 — Model Structure (JSON template)

The following JSON template specifies the exact structure permitted for M1 instances. Only the M2 concepts above are allowed.

```json
{
  "program": {
    "name": "<string>",
    "imports": [
      {
        "from": "<string>",
        "alias": "<string|null>"
      }
    ],
    "declarations": [
      {
        "name": "<string>",
        "type": {
          "name": "<string>",
          "fields": [
            { "name": "<string>", "type": "<string>" }
          ]
        }
      }
    ],
    "functions": [
      {
        "name": "<string>",
        "signature": {
          "parameters": [
            { "name": "<string>", "type": "<string>" }
          ],
          "returnType": "<string|null>"
        }
      }
    ]
  }
}
```

Notes:
- "type" fields in this IL are simple type references (qualified names or builtins such as "number", "string").
- This IL is intentionally minimal; optional additional concerns (semantics, constraints) should live in separate descriptors.

See also:
- Syntax mapping description : `DSL_IL_SYN-mapping.md`.
