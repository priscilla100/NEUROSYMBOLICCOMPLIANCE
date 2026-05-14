# Soufflé Datalog & Constraint Logic Programming — Conversation Summary

## Context
This conversation covered Constraint Logic Programming (CLP) in Prolog, sorts/types in Prolog and Datalog, Soufflé Datalog's feature set, stratified negation, provenance/explanation, and rule annotations. The goal was evaluating these tools for use in protocol security analysis (e.g., 5G NGAP/AMF state machine reasoning, access control policy checking).

---

## 1. Constraint Logic Programming (CLP) — Numeric and Symbolic Constraints

### The Question
Is there a Prolog engine supporting `>`, `<`, `=`, `!=`, `>=`, `<=` for numeric data and `=`, `!=` for symbolic/enum data as constraints?

### Answer: Yes — CLP systems

#### SWI-Prolog `CLP(FD)` — integers + enums
```prolog
:- use_module(library(clpfd)).

example :-
    X in 1..10, Y in 1..10,
    X #> 3,
    X #\= Y,
    X #=< Y + 2,
    label([X, Y]).
```

| Your operator | CLP(FD) syntax |
|---|---|
| `=`  | `#=`  |
| `!=` | `#\=` |
| `>`  | `#>`  |
| `<`  | `#<`  |
| `>=` | `#>=` |
| `<=` | `#=<` |

Symbolic/enum data is handled by mapping symbols to integers and using `#\=`.

#### SWI-Prolog `CLP(R)` / `CLP(Q)` — reals and rationals
```prolog
:- use_module(library(clpr)).
example :- { X > 3.0, X + Y =:= 10.0, Y >= 2.0 }.
```

#### ECLiPSe Prolog — most complete CLP system
```prolog
:- lib(ic).
:- lib(ic_symbolic).

example :-
    X :: [red, green, blue],
    Y :: [red, green, blue],
    X #\= Y.
```
`ic_symbolic` gives direct `=` and `#\=` over symbolic domains. Best option for combined numeric + enum constraints in Prolog.

---

## 2. Sorts in Prolog and Datalog

### Prolog — No Native Sort System
Prolog has no type/sort system; everything is a term. Sorts are encoded via:

1. **Guard predicates**:
```prolog
color(red). color(green). color(blue).
paint(X, C) :- color(C), ...
```

2. **CLP(FD) domains as sorts**: `X in 1..100` acts as a sort constraint.

3. **Attributed variables** — used internally by CLP libraries.

### Soufflé Datalog — Explicit `.type` Declarations
```datalog
.type Color = red | green | blue       // enum sort
.type Age <: number                    // numeric subtype
.type Name <: symbol                   // symbolic subtype

.decl Person(name: Name, age: Age, favColor: Color)

.decl Adult(name: Name)
Adult(N) :- Person(N, A, _), A >= 18.

.decl SameColor(a: Name, b: Name)
SameColor(A, B) :- Person(A, _, C), Person(B, _, C), A != B.
```

Soufflé supports `<`, `>`, `<=`, `>=`, `=`, `!=` for numeric types natively in rule bodies, and `=`/`!=` for symbolic types.

### Summary Table

| System | Numeric constraints | Symbolic/enum constraints | Sorts |
|---|---|---|---|
| SWI CLP(FD) | `#=` `#\=` `#>` etc. | Via integer encoding | None native |
| SWI CLP(R/Q) | `{ X > 3.0 }` | No | None native |
| ECLiPSe `ic` + `ic_symbolic` | Full numeric CLP | `#\=` over symbolic domains | None native |
| Soufflé Datalog | `<, >, <=, >=, =, !=` | `=, !=` on symbols | `.type` declarations |

---

## 3. Stratified Negation in Soufflé

### Does Soufflé Support Negation?
Yes. Soufflé enforces **stratified negation** — unstratified (cyclic) negation is a **compile-time error**.

### What is Stratified Datalog?

Plain Datalog has no negation. Adding negation naively can cause paradoxes (liar's paradox equivalent). Stratification is the structural discipline that prevents this.

**Core idea**: Partition rules into **strata** (layers) where:
- A relation can **positively** depend on relations in the **same or lower** stratum.
- A relation can **negatively** depend (via `!`) **only on strictly lower strata** — i.e., relations already at fixed point.

**Dependency graph rule**: Build a predicate dependency graph with positive (`→`) and negative (`→⁻`) edges. Program is stratifiable iff **no cycle passes through a negative edge**.

### Example: Two Strata

```datalog
// Stratum 0: base facts and recursive positive relation
.decl edge(x: number, y: number)
edge(1, 2). edge(2, 3). edge(3, 4).

.decl reachable(x: number, y: number)
reachable(X, Y) :- edge(X, Y).
reachable(X, Z) :- reachable(X, Y), edge(Y, Z).

// Stratum 1: negates reachable — safe because stratum 0 is fully computed first
.decl node(n: number)
node(1). node(2). node(3). node(4).

.decl unreachable(x: number, y: number)
unreachable(X, Y) :- node(X), node(Y), X != Y, !reachable(X, Y).
```

### Example: Three Strata (security domain)
```datalog
// Stratum 0
.decl vulnerable(host: symbol)
vulnerable("db01"). vulnerable("web02").
.decl patched(host: symbol)
patched("web02").

// Stratum 1: negates stratum-0 relation
.decl unpatched(host: symbol)
unpatched(H) :- vulnerable(H), !patched(H).

// Stratum 2: negates stratum-1 relation
.decl monitored(host: symbol)
monitored("db01").
.decl critical(host: symbol)
critical(H) :- unpatched(H), !monitored(H).
```

### What Soufflé Rejects
```datalog
// REJECTED: cycle through negation
p(X) :- q(X), !r(X).  // p negatively depends on r
r(X) :- p(X).          // r positively depends on p → cycle → ERROR
```

### Rules for Controlled Negation

1. **Safety**: every variable under `!` must be bound by a positive body literal first:
```datalog
// UNSAFE
bad(X) :- !edge(X, _).

// SAFE
good(X) :- node(X), !edge(X, _).
```

2. **Aggregates are stratification-like**: `count`, `sum`, `min`, `max` also require their input to be fully computed.

3. **Key intuition**: *Negation-as-failure only makes sense when the thing you're failing on is done being derived.*

### Summary Table

| Concept | Meaning |
|---|---|
| Stratified Datalog | No cycle in dependency graph passes through a negative edge |
| Stratum | Layer computed together; negation only references lower strata |
| Safety | Negated variables must be bound by positive literals |
| Soufflé enforcement | Stratification violations are compile-time errors |

---

## 4. Soufflé Provenance / Explanation System

### Overview
Soufflé has a first-class provenance system that produces **proof trees** for any derived tuple.

### Enabling Provenance: `-t` Flag
```bash
souffle -t explain foo.dl    # interactive REPL on stdout
souffle -t explore foo.dl    # ncurses TUI for large trees
souffle -t none foo.dl       # transformer only, no interface
```

### How It Works Internally
Soufflé uses **lazy provenance with annotations**: during bottom-up evaluation, each tuple is annotated with the rule that produced it and the height of a minimal-height proof tree. Proof trees are constructed on-demand (not upfront) via backwards search guided by these annotations.

### Interactive REPL Commands

Given:
```datalog
.decl edge(x: number, y: number)
.decl path(x: number, y: number)
edge(1,2). edge(2,3). edge(3,4). edge(4,5).
path(x,y) :- edge(x,y).
path(x,z) :- edge(x,y), path(y,z).
```

| Command | Purpose |
|---|---|
| `explain path(1,3)` | Full proof tree for an existing tuple |
| `explainnegation path(1,6)` | Guided partial tree for a missing tuple (semi-interactive) |
| `query path(1,3)` | Check tuple existence |
| `query path(1,3), path(2,4)` | Check multiple tuples |
| `setdepth 3` | Limit proof tree height (use `subproof` to expand) |
| `subproof path(0)` | Expand a truncated subtree |
| `rule path 2` | Print rule text for rule number 2 of `path` |
| `format json` | Switch output to JSON for programmatic use |
| `output <filename>` | Redirect output to file |

### Proof Tree Output Example
```
> explain path(1, 3)

edge(1,2)   edge(2,3)
---------   ---------
path(1,2)        (R1)
-------------------(R2)
     path(1,3)
```

### Non-Existence Explanation
```
> explainnegation path(1, 6)
1: path(x,y) :- edge(x,y).
2: path(x,z) :- edge(x,y), path(y,z).
Pick a rule number: 2
Pick a value for y: 2
====
edge(1, 2) ✓    path(2, 6) ✗
------------------------(R2)
        path(1,6)
```

### Provenance Flavors (Theory)
- **Why-provenance**: which input (EDB) facts contributed — the *leaves* of the proof tree
- **How-provenance**: full derivation structure — the *whole tree* including rule applications
- **Where-provenance**: which specific fields came from which input columns

---

## 5. Rule String Annotations in Explain Output

### The Question
Can you attach human-readable string annotations to rules that appear in the `explain` output?

### Answer: Not natively — but three workarounds exist

Soufflé's `@[doc]` / `/// doc comment` annotations are **tooling-only** and do not surface in proof trees. The proof tree only shows rule numbers like `(R1)`, `(R2)`.

#### Workaround 1: Reason Column in the Relation
Carry a `reason` symbol as an extra column — it threads naturally through the proof tree.

```datalog
.type Reason <: symbol

.decl path_j(x: number, y: number, reason: Reason)

path_j(X, Y, "direct-edge") :-
    edge(X, Y).

path_j(X, Z, cat(cat("via-", to_string(Y)), cat("-from-", R))) :-
    edge(X, Y),
    path_j(Y, Z, R).
```

`explain path_j(1,4)` now shows the reason string embedded in each node of the proof tree.

#### Workaround 2: Parallel Justification Relation
Keep the logic relation clean and maintain a separate `*_rule` relation:

```datalog
.decl path(x: number, y: number)
.decl path_rule(x: number, y: number, rule_name: symbol)

path(X, Y) :- edge(X, Y).
path_rule(X, Y, "base: direct edge") :- edge(X, Y).

path(X, Z) :- edge(X, Y), path(Y, Z).
path_rule(X, Z, cat("step via node ", to_string(Y))) :-
    edge(X, Y), path(Y, Z).
```

Query both:
```
> explain path(1, 4)       // structural proof tree
> output path_rule         // human-readable rule firings
```

#### Workaround 3: ADT Explanation Tree (most principled)
Build a recursive explanation tree as a first-class ADT value:

```datalog
.type Expl = Base { reason: symbol }
           | Step { reason: symbol, sub: Expl }

.decl path_e(x: number, y: number, expl: Expl)

path_e(X, Y, $Base("direct edge")) :-
    edge(X, Y).

path_e(X, Z, $Step("transitive step", E)) :-
    edge(X, Y),
    path_e(Y, Z, E).
```

Output as JSON and render the explanation tree however you like.

### Summary Table

| Mechanism | Appears in `explain`? | Human labels? | Notes |
|---|---|---|---|
| `@[doc]` / `///` annotations | ✗ | ✓ | IDE/tooling only |
| `rule <rel> <n>` REPL command | ✓ (indirect) | Rule text | Shows raw rule text, not custom label |
| `reason` column in relation | ✓ (as tuple data) | ✓ | Best for simple cases |
| Parallel `justification` relation | Alongside explain | ✓ | Clean separation of concerns |
| ADT explanation tree | ✓ (as structured data) | ✓ | Most principled; requires ADT support |

---

## Key Takeaways for Protocol/Security Analysis

- **Soufflé** is the best Datalog engine for this work: typed sorts, numeric+symbolic constraints, stratified negation, built-in provenance.
- **ECLiPSe** is the best Prolog CLP engine if you need combined numeric+enum constraint solving.
- For **proof explanations** in security analysis (e.g., "why is this host flagged critical?"), use the **ADT explanation tree** pattern — it gives you structured, labelable derivation trees as first-class data.
- **Negation in Soufflé** maps cleanly to closed-world security reasoning: "host is vulnerable if it is in `vulnerable` and NOT in `patched`" is exactly stratum-1 negation.
- The `format json` + `explain` combination is the right integration point for building automated explanation pipelines over NGAP state machine or access control policy derivations.
