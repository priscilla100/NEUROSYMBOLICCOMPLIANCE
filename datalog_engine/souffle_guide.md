# Soufflé Datalog Engine — In-Depth Guide

This document covers three core aspects of the Soufflé Datalog engine in detail:
the **syntax**, the **stratified evaluation model**, and the **explain (provenance)** feature.

---

## 1. Syntax of Soufflé Datalog

### 1.1 Program Structure

A Soufflé program (`.dl` file) is a sequence of:

- **Type declarations** (`.type`)
- **Relation declarations** (`.decl`)
- **Facts** (ground tuples)
- **Rules** (Horn clauses)
- **Directives** (`.input`, `.output`, `.printsize`, `.limitsize`)
- **Components** (`.comp`, `.init`)
- **User-defined functors** (`.functor`)
- **Pragmas** (`.pragma`)

Comments follow C/C++ style: `//` for single-line, `/* ... */` for blocks.
The C preprocessor is active by default, so `#include` and `#define` work.

### 1.2 Primitive Types

Soufflé has four built-in primitive types (all 64-bit in v2.x):

| Type       | Description                          | Example literals         |
|------------|--------------------------------------|--------------------------|
| `number`   | Signed integer                       | `42`, `-7`, `0xff`       |
| `unsigned` | Unsigned integer                     | `42`                     |
| `float`    | IEEE 754 floating-point              | `3.14`, `-0.001`         |
| `symbol`   | Interned string                      | `"hello"`, `"Alice"`     |

### 1.3 Type Declarations

```prolog
// Alias (equivalence type)
.type PersonName = symbol

// Subtype (strict, no implicit coercion)
.type Age <: number

// Union type
.type Place = City | Town | Village

// Record type (like a struct / tuple)
.type Pair = [first:number, second:number]

// Algebraic Data Type (tagged union)
.type Expr = Num   { val:number }
           | Var   { name:symbol }
           | Add   { lhs:Expr, rhs:Expr }
```

Records use bracket notation `[v1, v2]` and support `nil` as a null value.

### 1.4 Algebraic Data Types (ADTs)

Algebraic Data Types are Soufflé's mechanism for **tagged unions** — a single
type that can take one of several named forms (branches), each carrying its own
fields. They are the Datalog analogue of `enum` variants in Rust or `sealed
class` hierarchies in Kotlin.

#### Declaring an ADT

Each branch is declared with a name and a (possibly empty) set of typed fields,
separated by `|`:

```prolog
.type Expr = Num      { val:number }
           | Var      { name:symbol }
           | Add      { lhs:Expr, rhs:Expr }
           | Neg      { inner:Expr }
           | Literal  {}                      // branch with no fields
```

Key rules:

- **Branch names must be globally unique** across all ADTs in the program
  (unless namespaced inside components).
- Branches can be **recursive** — `Add` references `Expr` itself, enabling
  tree-shaped data.
- An empty branch (`Literal {}`) acts like a nullary constructor / sentinel
  value.
- Unlike records, ADTs do **not** support `nil`. If you need an "absent" case,
  define an explicit empty branch (e.g., `None {}`).

#### Constructing ADT Values

Use the `$BranchName(args)` syntax:

```prolog
.decl expr_store(id:number, e:Expr)
expr_store(1, $Num(42)).
expr_store(2, $Var("x")).
expr_store(3, $Add($Num(1), $Num(2))).
expr_store(4, $Neg($Var("y"))).
expr_store(5, $Add($Num(10), $Add($Num(20), $Num(30)))).   // nested
```

#### Pattern-Matching on ADTs

Rules destructure ADT values by matching on their branch constructors:

```prolog
// Extract all numeric literals
.decl is_number(id:number, val:number)
is_number(id, v) :- expr_store(id, $Num(v)).

// Extract all variable references
.decl is_var(id:number, name:symbol)
is_var(id, n) :- expr_store(id, $Var(n)).

// Recursive traversal: collect all variable names in an expression
.decl uses_var(id:number, name:symbol)
uses_var(id, n) :- expr_store(id, $Var(n)).
uses_var(id, n) :- expr_store(id, $Add(lhs, _)), expr_store(_, lhs), uses_var(_, n).
uses_var(id, n) :- expr_store(id, $Add(_, rhs)), expr_store(_, rhs), uses_var(_, n).
uses_var(id, n) :- expr_store(id, $Neg(inner)), expr_store(_, inner), uses_var(_, n).
```

#### A Complete ADT Example: Linked Lists

ADTs naturally model recursive data structures like linked lists:

```prolog
.type IntList = Cons { head:number, tail:IntList }
              | Nil  {}

.decl my_list(x:IntList)
my_list($Cons(1, $Cons(2, $Cons(3, $Nil())))).

// Membership test
.decl member(list:IntList, val:number)
member(l, v) :- my_list(l), l = $Cons(v, _).
member(l, v) :- my_list(l), l = $Cons(_, t), member(t, v).
```

#### ADTs vs. Records

| Feature             | Records (`[...]`)         | ADTs (`$Branch(...)`)           |
|---------------------|---------------------------|---------------------------------|
| Supports `nil`      | Yes                       | No (use an explicit empty branch) |
| Tagged variants     | No (single shape)         | Yes (multiple named branches)    |
| Pattern matching    | Positional only           | By branch name + positional      |
| Recursive           | Yes (via `nil` base case) | Yes (via empty branch base case) |
| Global uniqueness   | N/A                       | Branch names must be unique      |

Use **records** for simple structured tuples (pairs, triples). Use **ADTs**
when a value can take one of several distinct forms — ASTs, option types,
heterogeneous lists, etc.

### 1.5 Relation Declarations

```prolog
.decl edge(src:symbol, dst:symbol)
.decl path(x:symbol, y:symbol)
```

Multiple relations can share a signature:

```prolog
.decl A, B, C(x:number, y:number)
```

**Qualifiers** can be attached to relations:

| Qualifier     | Effect                                                              |
|---------------|---------------------------------------------------------------------|
| `btree`       | Default index structure (B-tree)                                    |
| `brie`        | Prefix-tree index, good for dense low-arity data                    |
| `eqrel`       | Equivalence relation — automatically reflexive, symmetric, transitive (union-find) |
| `inline`      | Inline this relation into the rules that reference it               |
| `no_inline`   | Prevent inlining                                                    |
| `magic`       | Enable magic-set transformation                                     |
| `overridable` | Allow overriding in component subclasses                            |
| `choice-domain` | Enforce a functional dependency (see below)                       |

Example with qualifier:

```prolog
.decl equiv(x:number, y:number) eqrel
equiv(1,2). equiv(2,3).
// Soufflé automatically derives equiv(1,1), equiv(1,3), equiv(3,1), etc.
```

### 1.5 Facts

A fact is a rule with no body — a ground tuple:

```prolog
.decl parent(child:symbol, par:symbol)
parent("Alice", "Bob").
parent("Alice", "Carol").
```

All arguments must be constants (no variables).

### 1.6 Rules

A rule is a Horn clause: `head :- body.`

```prolog
// Base case
path(x, y) :- edge(x, y).

// Recursive case
path(x, y) :- path(x, z), edge(z, y).
```

**Multiple heads** (syntactic sugar — one rule, multiple conclusions):

```prolog
A(x), B(x) :- C(x).
// Equivalent to:
// A(x) :- C(x).
// B(x) :- C(x).
```

**Disjunction** in the body with `;`:

```prolog
livesAt(person, building) :-
    owner(o, building),
    (person = o ; housemate(o, person)).
```

**Negation** with `!`:

```prolog
unemployed(x) :- person(x), !employed(x).
```

Key constraint: every variable in a rule must be **grounded** — it must appear
as a direct argument to at least one *positive* (non-negated) atom in the body.
Variables that appear *only* inside a negated atom are not grounded.

```prolog
// INVALID — y appears only in the negated atom:
bad(x, y) :- R(x), !S(y).

// VALID — y is grounded by scope/1:
good(x, y) :- R(x), scope(y), !S(y).
```

### 1.7 Constraints and Arithmetic

**Comparison operators**: `<`, `>`, `<=`, `>=`, `=`, `!=`

**Arithmetic operators**: `+`, `-`, `*`, `/`, `%` (modulo), `^` (exponentiation)

**Bitwise**: `band`, `bor`, `bxor`, `bshl`, `bshr`, `bshru`

**Logical**: `land`, `lor`, `lxor`, `lnot`

**String functions**: `cat(a, b)` (concatenation), `strlen(s)`, `substr(s, i, len)`,
`contains(sub, s)`, `match(pattern, s)`, `ord(s)`, `to_number(s)`, `to_string(n)`

### 1.8 Aggregates

Soufflé supports five aggregate operations:

```prolog
// count
total(c) :- c = count : { person(_) }.

// min / max
youngest(a) :- a = min age : { person(_, age) }.
oldest(a)   :- a = max age : { person(_, age) }.

// sum
total_sal(s) :- s = sum sal : { employee(_, sal) }.

// mean
avg_sal(m) :- m = mean sal : { employee(_, sal) }.
```

Grouping is implicit — variables appearing both inside and outside the
aggregate body act as group-by keys:

```prolog
// Count of ancestors per person
ancestor_count(x, c) :- person(x), c = count : { ancestor(x, _) }.
```

`count` returns 0 for empty sets; `min`/`max` produce no result on empty sets.

### 1.9 Input / Output Directives

```prolog
// Read from a tab-separated file (default: <relation>.facts)
.input edge

// Custom file, CSV
.input edge(IO=file, filename="edges.csv", delimiter=",")

// Read from stdin or SQLite
.input edge(IO=stdin)
.input edge(IO=sqlite, dbname="graph.db")

// Write results
.output path                          // writes path.csv (tab-separated)
.output path(IO=stdout)               // print to terminal
.output path(IO=sqlite, dbname="out.db")

// Just print the count
.printsize path
```

### 1.10 Components (Modules)

Components provide namespacing, reuse, and inheritance:

```prolog
.comp Graph<N> {
    .decl node(x:N)
    .decl edge(x:N, y:N)
    .decl path(x:N, y:N)

    node(x) :- edge(x, _).
    node(x) :- edge(_, x).
    path(x, y) :- edge(x, y).
    path(x, y) :- path(x, z), edge(z, y).
}

.init g = Graph<symbol>
g.edge("a", "b").
g.edge("b", "c").
.output g.path
```

**Inheritance**:

```prolog
.comp Weighted : Graph<number> {
    .decl cost(x:number, y:number, w:number)
}
```

### 1.11 Subsumption

Subsumption rules delete dominated tuples:

```prolog
.decl shortest(x:number, y:number, cost:number)
shortest(x, y, c1) <= shortest(x, y, c2) :- c1 >= c2.
// Keeps only the minimum-cost tuple for each (x, y) pair
```

### 1.12 Choice Domain

Enforces a functional dependency — each key maps to at most one value:

```prolog
.decl assign(student:symbol, advisor:symbol) choice-domain (student)
assign(s, a) :- request(s, a).
// Soufflé non-deterministically picks one advisor per student
```

### 1.13 User-Defined Functors

```prolog
.functor factorial(n:number):number
.decl result(x:number)
result(@factorial(10)).
```

The functor body is implemented in C/C++ and compiled as a shared library.

---

## 2. Stratification in Soufflé

### 2.1 What Is Stratification?

Standard Datalog (without negation) has clean, unambiguous semantics: start
with the facts and repeatedly apply all rules until no new tuples are derived
(the **least fixpoint**). Every program terminates and produces a unique result.

**Negation** breaks this simplicity. Consider:

```prolog
P(x) :- Q(x), !P(x).   // "x is in P if x is in Q and x is NOT in P"
```

This is paradoxical — if `P(1)` is true, the body says it shouldn't be; if
`P(1)` is false, the body says it should be. There is no consistent least fixpoint.

**Stratification** is the standard solution. It partitions the rules of a
program into ordered layers called **strata** such that:

1. If a rule in stratum *i* negates a relation *R*, then all rules that
   define *R* must reside in some stratum *j < i*.
2. Within a single stratum, only **positive** recursion is allowed.

Evaluation proceeds bottom-up, one stratum at a time: compute stratum 0 to
its fixpoint, then stratum 1 (which may negate relations from stratum 0, now
fully determined), then stratum 2, and so on.

### 2.2 How Soufflé Computes Strata

Soufflé builds a **precedence graph** over relations:

- An edge `R -> S` is **positive** if a rule defining `R` uses `S` in a
  positive literal.
- An edge `R -> S` is **negative** if a rule defining `R` negates `S` (or
  aggregates over `S`).

It then computes the **strongly connected components (SCCs)** of this graph.
If any SCC contains a **negative** edge, the program is **unstratifiable** and
Soufflé rejects it at compile time with an error.

You can visualize this with:

```bash
souffle --show=precedence-graph program.dl
souffle --show=scc-graph program.dl
```

Or generate a full HTML debug report (requires Graphviz):

```bash
souffle -r report.html program.dl
```

### 2.3 A Stratified Example

```prolog
// === Stratum 0: base facts and positive recursion ===

.decl edge(x:number, y:number)
edge(1,2). edge(2,3). edge(3,4). edge(4,5).

.decl node(x:number)
node(x) :- edge(x, _).
node(x) :- edge(_, x).

.decl reachable(x:number, y:number)
reachable(x, y) :- edge(x, y).
reachable(x, y) :- reachable(x, z), edge(z, y).   // positive recursion — OK

// === Stratum 1: negation over fully-computed reachable ===

.decl unreachable(x:number, y:number)
unreachable(x, y) :- node(x), node(y), x != y, !reachable(x, y).
```

**Why this is valid**: `unreachable` depends negatively on `reachable`, but
`reachable` is defined entirely within stratum 0 using only positive recursion.
By the time stratum 1 begins, `reachable` is complete and frozen — the negation
`!reachable(x, y)` has well-defined meaning.

The strata are:

| Stratum | Relations computed          | Dependencies                 |
|---------|-----------------------------|------------------------------|
| 0       | `edge`, `node`, `reachable` | Positive recursion only       |
| 1       | `unreachable`               | Negates `reachable` (stratum 0) |

### 2.4 A Multi-Stratum Example (from `family.dl`)

Our example program `family.dl` has three natural strata:

```
Stratum 0:  parent (facts)
            person       ← positive dependency on parent
            ancestor     ← positive recursion through parent
            descendant   ← positive dependency on ancestor
            related      ← positive dependency on ancestor, descendant
            sibling      ← positive dependency on parent
            cousin       ← positive dependency on parent, sibling

Stratum 1:  unrelated    ← NEGATES related (from stratum 0)

Stratum 2:  ancestor_count ← AGGREGATES over ancestor (from stratum 0)
```

Negation (`!related(x,y)`) and aggregation (`count : { ancestor(x,_) }`) are
both treated as **non-monotone** operations. Both require the referenced
relation to be fully computed before they can be evaluated. Soufflé places them
in a higher stratum automatically.

### 2.5 Unstratifiable Programs (Rejected by Soufflé)

**Self-negation:**

```prolog
.decl P(x:number)
.decl Q(x:number)
Q(1). Q(2).

P(x) :- Q(x), !P(x).   // ERROR: P negates itself
```

Soufflé will refuse to compile this with an error indicating that `P` depends
negatively on itself.

**Mutual negative recursion:**

```prolog
.decl A(x:number)
.decl B(x:number)
.decl C(x:number)
C(1). C(2). C(3).

A(x) :- C(x), !B(x).
B(x) :- C(x), !A(x).   // ERROR: A ↔ B negative cycle
```

`A` negates `B` and `B` negates `A`, forming a negative cycle in the
precedence graph. No valid ordering of strata exists.

**Negation inside positive recursion:**

```prolog
.decl path(x:number, y:number)
.decl blocked(x:number, y:number)

path(x, y) :- edge(x, y), !blocked(x, y).
path(x, y) :- path(x, z), edge(z, y), !blocked(z, y).
blocked(x, y) :- path(x, y), dangerous(y).   // ERROR: path ↔ blocked cycle
```

`path` negates `blocked`, and `blocked` depends positively on `path`.
This puts `path` and `blocked` in the same SCC with a negative edge — rejected.

### 2.6 Aggregates and Stratification

Aggregates are treated like negation for stratification purposes. An aggregate
over relation `R` requires `R` to be in a lower stratum:

```prolog
// VALID: aggregate over a base relation
.decl item(x:number)
item(1). item(2). item(3).
.decl total(c:number)
total(c) :- c = count : { item(_) }.

// INVALID: aggregate over a relation being recursively defined in the same stratum
.decl R(x:number)
R(1).
R(x+1) :- R(x), x < count : { R(_) }.   // ERROR: R aggregated while being defined
```

### 2.7 Why Stratification Matters

Without stratification, a Datalog program with negation can have **zero, one,
or multiple** minimal models — the semantics become ambiguous. Stratification
guarantees:

1. **Existence**: A unique **stratified model** always exists.
2. **Determinism**: The result does not depend on evaluation order.
3. **Computability**: Bottom-up, stratum-by-stratum evaluation always terminates.

This is why Soufflé enforces stratification as a hard constraint. If your
program is rejected, you must restructure it to eliminate negative cycles.

### 2.8 Practical Patterns

**Pattern**: Compute a positive fixpoint, then apply negation in a separate step.

```prolog
// Stratum 0: all reachable nodes
.decl reachable(x:symbol)
reachable("start").
reachable(y) :- reachable(x), edge(x, y).

// Stratum 1: dead code = defined but unreachable
.decl dead(x:symbol)
dead(x) :- defined(x), !reachable(x).
```

**Pattern**: Use an intermediate relation to break a negative cycle.

```prolog
// Instead of:  A(x) :- B(x), !A(x).   (invalid)
// Introduce a snapshot:
A_prev(x) :- /* some base condition */.
A(x) :- B(x), !A_prev(x).              // valid: A negates A_prev, not itself
```

---

## 3. The Explain Feature (Provenance and Debugging)

### 3.1 What Is Provenance?

When Soufflé derives a tuple like `path(1, 4)`, you might ask: **why?** Which
facts and rules combined to produce this result? The **explain** feature
answers this by constructing **proof trees** — traces that show every
derivation step from base facts up to the queried tuple.

### 3.2 Enabling Provenance

Use the `-t` flag with one of three modes:

| Flag           | Description                                                      |
|----------------|------------------------------------------------------------------|
| `-t none`      | Enables provenance annotations internally, no interactive UI     |
| `-t explain`   | Interactive command-line interface (stdout)                       |
| `-t explore`   | Interactive ncurses-based UI for navigating large proof trees    |

```bash
souffle -t explain program.dl
```

After evaluation completes, Soufflé drops you into an interactive prompt.

### 3.3 How It Works Internally

During evaluation, Soufflé annotates each derived tuple with:

- The **rule number** that produced it.
- The **height** of its proof tree (number of derivation steps from base facts).

Soufflé stores the derivation with the **minimal height** for each tuple. The
actual proof tree is **not materialized during evaluation** — it is
reconstructed lazily on demand when you issue an `explain` query. This keeps
the runtime overhead manageable.

### 3.4 Interactive Commands

Once in the provenance shell, the following commands are available:

#### `explain <relation>(<args>)`

Shows the proof tree for a specific tuple:

```
souffle> explain path(1, 4)
```

Output (conceptual):

```
path(1, 4)                   ── Rule 2: path(x,y) :- path(x,z), edge(z,y).
├── path(1, 3)               ── Rule 2: path(x,y) :- path(x,z), edge(z,y).
│   ├── path(1, 2)           ── Rule 1: path(x,y) :- edge(x,y).
│   │   └── edge(1, 2)       [fact]
│   └── edge(2, 3)           [fact]
└── edge(3, 4)               [fact]
```

For symbol arguments, use quotes:

```
souffle> explain ancestor("Alice", "Henry")
```

#### `setdepth <n>`

Controls how many levels of the proof tree are displayed (default: 4).
Deeper portions are collapsed into labeled **subproof** placeholders.

```
souffle> setdepth 2
souffle> explain path(1, 4)
```

Output:

```
path(1, 4)                   ── Rule 2
├── path(1, 3)               [subproof path_0]
└── edge(3, 4)               [fact]
```

#### `subproof <label>`

Expands a collapsed subproof:

```
souffle> subproof path_0
```

Output:

```
path(1, 3)                   ── Rule 2
├── path(1, 2)               ── Rule 1
│   └── edge(1, 2)           [fact]
└── edge(2, 3)               [fact]
```

#### `explainnegation <relation>(<args>)`

Interactively explains **why a tuple was NOT derived**. Soufflé walks you
through the rules that *could* have derived the tuple, asking you to select
bindings, and then shows which sub-goal failed:

```
souffle> explainnegation path(4, 1)
// Soufflé will interactively ask:
//   Which rule could derive path(4,1)?
//   Rule 1: path(x,y) :- edge(x,y).    → edge(4,1) does not exist.
//   Rule 2: path(x,y) :- path(x,z), edge(z,y).  → no z such that path(4,z) exists.
```

This is an interactive, guided process — Soufflé prompts you at each decision
point.

#### `query <relation>(<args>)`

Checks whether a tuple exists. Supports wildcards (`_`) for partial queries:

```
souffle> query path(1, _)
// Lists all tuples matching path(1, *)
```

#### `format <json|proof>`

Switches output between the default proof-tree format and JSON:

```
souffle> format json
souffle> explain path(1, 3)
// Outputs a JSON representation of the proof tree
```

JSON format is useful for piping to external visualization tools.

#### `output <filename>`

Redirects proof tree output to a file instead of the terminal:

```
souffle> output proof_log.txt
souffle> explain path(1, 4)
// Written to proof_log.txt
```

#### `rule <relation> <rulenumber>`

Displays the source text of a specific rule:

```
souffle> rule path 1
// path(x, y) :- edge(x, y).
```

#### `exit` / `quit` / `q`

Exits the provenance shell.

### 3.5 The `explore` Mode

Running with `-t explore` launches an **ncurses-based terminal UI**. This is
particularly valuable for complex programs where proof trees can span dozens of
levels. The ncurses interface lets you:

- Navigate the proof tree with arrow keys.
- Expand and collapse nodes interactively.
- Search for specific sub-derivations.

This mode requires ncurses support (which Soufflé on macOS via Homebrew includes
by default, as confirmed by the `ncurses` option in `souffle --version`).

### 3.6 Full Walkthrough Example

Given our `family.dl` program, let's trace why `ancestor("Alice", "Henry")` is derived.

```bash
souffle -t explain family.dl
```

At the prompt:

```
souffle> explain ancestor("Alice", "Henry")
```

Expected proof tree:

```
ancestor("Alice", "Henry")          ── Rule 2: ancestor(x,y) :- parent(x,z), ancestor(z,y).
├── parent("Alice", "Bob")          [fact]
└── ancestor("Bob", "Henry")        ── Rule 2: ancestor(x,y) :- parent(x,z), ancestor(z,y).
    ├── parent("Bob", "Dave")       [fact]
    └── ancestor("Dave", "Henry")   ── Rule 1: ancestor(x,y) :- parent(x,y).
        └── parent("Dave", "Henry") [fact]
```

Reading bottom-up: Dave is Henry's parent (fact), so Dave is Henry's ancestor
(Rule 1). Bob is Dave's parent (fact) and Dave is Henry's ancestor, so Bob is
Henry's ancestor (Rule 2). Alice is Bob's parent (fact) and Bob is Henry's
ancestor, so Alice is Henry's ancestor (Rule 2).

Now let's check why `ancestor("Henry", "Alice")` does **not** hold:

```
souffle> explainnegation ancestor("Henry", "Alice")
```

Soufflé will guide you through:

- **Rule 1**: `ancestor(x,y) :- parent(x,y).` — Is `parent("Henry", "Alice")`
  a fact? **No.** Henry has no children in our data.
- **Rule 2**: `ancestor(x,y) :- parent(x,z), ancestor(z,y).` — Is there any
  `z` such that `parent("Henry", z)` holds? **No.** Dead end.

Therefore, `ancestor("Henry", "Alice")` cannot be derived by any rule.

### 3.7 Practical Tips

1. **Use provenance for debugging, not production.** The annotations add
   memory overhead.
2. **Start with `setdepth 3` or `4`** for large programs to avoid overwhelming
   output, then drill into subproofs as needed.
3. **Use `format json`** if you want to post-process proof trees programmatically
   (e.g., render them as graphs with Graphviz or D3).
4. **`explainnegation` is interactive** — it cannot be fully scripted, but it is
   invaluable for understanding why expected results are missing.
5. **The `-t none` mode** is useful when you want to access provenance data
   through the C++ API without launching an interactive shell.

---

## References

- [Soufflé Official Documentation](https://souffle-lang.github.io/)
- [Soufflé GitHub Repository](https://github.com/souffle-lang/souffle)
- Scholz et al., "On fast large-scale program analysis in Datalog," CC 2016.
