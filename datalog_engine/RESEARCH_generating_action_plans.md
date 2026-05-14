# Research: Generating Action Plans for Denied Disclosures

**Task 3**: Can the system generate a plan showing what conditions must be met for a denied disclosure to become allowed?

## Problem Statement

Currently the HIPAA compliance checker outputs a binary verdict: ALLOWED (with explanation tree) or DENIED (no explanation of what's missing). When a disclosure is denied, users need to know: **what would need to change for it to become allowed?**

## Approach 1: Pathway Enumeration with Missing Condition Analysis (Recommended)

### Concept
For each denied disclosure, identify all potential permission pathways and, for each pathway, determine which conditions are satisfied and which are missing.

### Implementation

Create a set of "diagnostic" predicates that mirror each permission pathway but with relaxed conditions, tagging what's missing:

```datalog
// Diagnostic: what's needed for §506(c)(2) — treatment to provider?
.type MissingCondition = MissingCE {} | MissingProvider {} | MissingTPO {} | MissingPHI {} | MissingMsg {}

.decl pathway_506c2_missing(DECL_ARGS, condition: symbol)

// Check each condition independently
pathway_506c2_missing(ARGS, "p1 must be a covered entity") :-
    disclosure_attempted(ARGS), !is_covered_entity(p1).

pathway_506c2_missing(ARGS, "p2 must be a health care provider") :-
    disclosure_attempted(ARGS), is_covered_entity(p1), !is_health_care_provider(p2).

pathway_506c2_missing(ARGS, "purpose must be treatment") :-
    disclosure_attempted(ARGS), is_covered_entity(p1), is_health_care_provider(p2), !is_for_treatment(u).

pathway_506c2_missing(ARGS, "attribute must be PHI") :-
    disclosure_attempted(ARGS), is_covered_entity(p1), is_health_care_provider(p2), is_for_treatment(u), !is_phi(t).
```

Then a top-level aggregation predicate:

```datalog
.decl disclosure_plan(DECL_ARGS, pathway: symbol, missing: symbol)

disclosure_plan(ARGS, "506(c)(2): treatment to provider", Missing) :-
    is_disclosure_denied(ARGS),
    pathway_506c2_missing(ARGS, Missing).
```

### Advantages
- Provides actionable, specific guidance ("You need authorization under §508" or "The recipient must be a covered entity")
- Can rank pathways by number of missing conditions (fewer = easier to satisfy)
- Works within Soufflé's capabilities

### Limitations
- Requires writing diagnostic rules for every pathway (labor-intensive)
- Doesn't handle interactions between pathways (e.g., negative norms blocking paths)

## Approach 2: Abductive Reasoning via External Wrapper

### Concept
Use an external Python/shell script that systematically adds oracle predicates and re-runs the checker to find the minimal set of facts that would flip a DENY to ALLOW.

```python
# Pseudocode
oracle_candidates = [
    'obtained_authorization_164_508("{p1}", "{p2}", "{q}", "{t}", "{u}").',
    'is_required_by_law("{p1}", "{p2}", "{q}", "{t}", "{u}").',
    'obtained_consent_506b("{p1}", "{p2}", "{q}", "{t}", "{u}").',
    # ... all oracle predicates
]

for oracle in oracle_candidates:
    # Add oracle to facts file, re-run souffle
    if result == ALLOWED:
        print(f"Adding {oracle} would make this ALLOWED")
```

### Advantages
- No changes to formalization needed
- Finds the actual minimal fix
- Can try combinations

### Limitations
- Slow (N oracle predicates × Soufflé compilation time)
- Combinatorial explosion for multi-predicate fixes
- May miss structural changes (e.g., changing roles)

## Approach 3: Soufflé Provenance Feature

### Concept
Use `souffle -t explain` to explore why specific tuples do or don't exist.

```bash
souffle -t explain hipaa_query_main.dl
# In REPL:
> explain is_disclosure_allowed("hospital", "doctor", "patient", "msg", "diagnosis", "treatment")
```

This shows the proof tree if the tuple exists, or the failure point if it doesn't.

### Limitations
- Interactive only (not programmable)
- Doesn't suggest fixes, only shows failure points
- Requires manual interpretation

## Recommendation

**Use Approach 1 (pathway enumeration) as the primary method**, supplemented by **Approach 2 (wrapper script)** for complex cases. The agent prompt should instruct the agent to:

1. When a disclosure is DENIED, run a "what-if" analysis
2. For each relevant pathway, list the conditions that are met and those that are missing
3. Present the easiest path to compliance (fewest missing conditions)
4. Phrase recommendations as actionable steps: "To permit this disclosure, you would need to: (1) obtain a valid authorization under §164.508, OR (2) obtain a court order under §164.512(e)"

## Example Output Format

```
VERDICT: DENIED

POSSIBLE PATHS TO COMPLIANCE:
1. §164.508 Authorization (1 condition missing):
   ✓ Sender is a covered entity
   ✓ Information is PHI
   ✗ No valid authorization obtained
   → ACTION: Obtain written authorization from the patient

2. §164.512(e)(1)(i) Court Order (1 condition missing):
   ✓ Sender is a covered entity
   ✓ Purpose is judicial proceeding
   ✗ No court order provided
   → ACTION: Obtain a court order for the disclosure

3. §164.506(c)(2) Treatment (2 conditions missing):
   ✓ Sender is a covered entity
   ✗ Recipient is not a health care provider
   ✗ Purpose is not treatment
   → ACTION: N/A — structural mismatch
```
