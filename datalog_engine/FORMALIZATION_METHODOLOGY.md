# Regulatory Formalization Methodology: From Legal Text to Soufflé Datalog

This document describes the methodology used to formalize HIPAA Privacy Rule (45 CFR Part 164, Subpart E) in Soufflé Datalog. Another agent can follow this methodology to formalize other regulations (e.g., CCPA, SOX, GDPR, FERPA).

---

## 1. Overview of the Approach

The methodology converts natural-language regulatory text into executable Datalog rules that can determine compliance for specific scenarios. The core insight: regulations are essentially logical formulas with defined conditions, exceptions, and hierarchies.

**Input**: Regulatory text (PDF, eCFR, statute)
**Output**: A set of `.dl` (Soufflé Datalog) files that, given a scenario encoded as facts, produce a verdict (ALLOWED/DENIED) with an explanation tree citing specific regulatory provisions.

---

## 2. Phase 1: Structural Analysis

### 2.1 Identify the Regulatory Structure

Before writing any code, map the regulation's hierarchical structure:

```
Regulation
  └── Part/Chapter
       └── Section (e.g., §164.502)
            └── Subsection (e.g., (a))
                 └── Paragraph (e.g., (1))
                      └── Sub-paragraph (e.g., (i))
                           └── Clause (e.g., (A))
```

For HIPAA, we identified:
- §164.502: General rules (top-level OR of subsections a-j)
- §164.506: TPO (treatment, payment, operations)
- §164.508: Authorization required
- §164.510: Opportunity to agree/object
- §164.512: No authorization required (12 sub-sections a-l)
- §164.514: Other requirements
- §164.524: Individual access

### 2.2 Identify the Action Signature

Every regulation governs some type of **action**. Identify the parameters of that action.

For HIPAA disclosures, the action signature is a 6-tuple:
```
(p1: sender, p2: receiver, q: subject, m: message, t: attribute_type, u: purpose)
```

For other regulations:
- **GDPR**: `(controller, processor, data_subject, data_category, legal_basis, purpose)`
- **CCPA**: `(business, third_party, consumer, personal_info_category, purpose)`
- **SOX**: `(company, auditor, record_type, action_type, period)`

**Use a macro to reduce verbosity:**
```datalog
#define ARGS p1, p2, q, m, t, u
#define DECL_ARGS p1:Principal, p2:Principal, q:Principal, m:Message, t:Attribute, u:Purpose
```

### 2.3 Identify the Three Types of Norms

Every regulatory rule falls into one of three categories:

| Norm Type | Meaning | Datalog Pattern |
|-----------|---------|-----------------|
| **Positive (φ+)** | "This action IS permitted when..." | `permitted_by_X(ARGS, E) :- conditions.` |
| **Negative (φ-)** | "This action is NOT permitted when..." | `!negative_norm_X(ARGS)` used as guard |
| **Constraint** | "This permitted action must also satisfy..." | Added as extra condition in the body |

Example from HIPAA:
- φ+: §506(c)(2) — "A covered entity may disclose PHI for treatment" (positive)
- φ-: §508(a)(2) — "Psychotherapy notes require authorization" (negative — blocks positive rules)
- Constraint: §502(b) — "Must be minimum necessary" (constraint on otherwise-permitted disclosures)

---

## 3. Phase 2: Define Types and Hierarchies

### 3.1 Type Declarations

Define the domain types in a `types.dl` file:

```datalog
.type Principal <: symbol
.type Role <: symbol
.type Attribute <: symbol
.type Purpose <: symbol
.type Message <: symbol
```

### 3.2 Explanation Tree ADT

Add an algebraic data type for explanation trees:

```datalog
.type Expl = Leaf { reason: symbol }
           | Step1 { reason: symbol, sub1: Expl }
           | Step2 { reason: symbol, sub1: Expl, sub2: Expl }
           | Step3 { reason: symbol, sub1: Expl, sub2: Expl, sub3: Expl }
```

This replaces Prolog's `writeln` with structured provenance.

### 3.3 Role/Attribute/Purpose Hierarchies

Define hierarchies with transitive closure:

```datalog
// Role hierarchy
.decl role_isa(child: Role, parent: Role)
role_isa("doctor", "provider").
role_isa("provider", "covered-entity").

// Transitive closure
.decl role_subtype(child: Role, ancestor: Role)
role_subtype(C, P) :- role_isa(C, P).
role_subtype(C, A) :- role_isa(C, P), role_subtype(P, A).

// Active role check with hierarchy
.decl activerole(p: Principal, r: Role)
.decl has_role(p: Principal, r: Role)
has_role(P, R) :- activerole(P, R).
has_role(P, R) :- activerole(P, R2), role_subtype(R2, R).
```

**For other regulations**, define analogous hierarchies:
- GDPR: data categories (special categories < personal data), legal bases, controller types
- CCPA: business types, personal info categories, consumer rights

---

## 4. Phase 3: Translate Rules

### 4.1 The Maximal Revelation Principle

**Always decompose the logical structure as much as possible:**

- "A and B and C" → separate conditions joined by comma (AND in Datalog)
- "A or B or C" → separate rules with same head (OR in Datalog)
- "not X" or "unless X" → explicit negation `!X`
- **But**: Don't over-decompose. "John and Jane are dancing together" is one unit, not two separate facts.

### 4.2 Translation Patterns

#### Pattern 1: Simple Permission (Positive Norm)

**Legal text**: "A covered entity may disclose PHI to a health care provider for treatment."

```datalog
permitted_by_164_506_c_2(ARGS,
    $Leaf("164.506(c)(2): treatment activities of health care provider")) :-
    is_covered_entity(p1),      // condition 1: sender is CE
    is_health_care_provider(p2), // condition 2: receiver is provider
    is_phi(t),                   // condition 3: info is PHI
    msg_contains(m, q, t),       // condition 4: message contains info
    is_for_treatment(u).         // condition 5: purpose is treatment
```

#### Pattern 2: Exception Handling (Negative Norm)

**Legal text**: "Except for uses requiring authorization under §164.508..."

```datalog
permitted_by_164_506_a(ARGS, E) :-
    !require_authorization_by_164_508(ARGS),  // negative norm as guard
    is_covered_entity(p1),
    permitted_by_164_506_c(ARGS, E).
```

#### Pattern 3: Disjunction (OR of sub-rules)

**Legal text**: "A covered entity is permitted to use or disclose PHI: (i) to the individual; (ii) for TPO; (iii) incident to..."

```datalog
// One rule per disjunct
permitted_by_164_502_a_1(ARGS, E) :- permitted_by_164_502_a_1_i(ARGS, E).
permitted_by_164_502_a_1(ARGS, E) :- permitted_by_164_502_a_1_ii(ARGS, E).
permitted_by_164_502_a_1(ARGS, E) :- permitted_by_164_502_a_1_iii(ARGS, E).
// ... etc.
```

#### Pattern 4: Oracle Predicates (Subjective/Contextual Conditions)

**Legal text**: "...the covered entity believes in good faith that the entity has engaged in unlawful conduct..."

This is a subjective condition that cannot be derived from structural facts. Declare it as an oracle (EDB fact):

```datalog
.decl believes_unlawful_conduct(employee: Principal, employer: Principal)
// Populated as a fact in the scenario, not derived by rules
```

**Rule of thumb**: If a condition involves:
- Belief, judgment, or discretion → Oracle
- Temporal state ("has been", "once was") → Oracle (collapses temporal operators)
- External legal determination ("required by law") → Oracle
- Procedural completion ("notice was given") → Oracle

#### Pattern 5: Constraint (Not a Permission, but a Guard)

**Legal text**: "Must make reasonable efforts to limit PHI to the minimum necessary..."

```datalog
// Constraint — not an independent permission, but required by other rules
minimum_necessary_satisfied(ARGS) :-
    believes_minimum_necessary(ARGS).    // option 1: CE believes min necessary
minimum_necessary_satisfied(ARGS) :-
    excluded_164_502_b_2(ARGS).          // option 2: exception applies
```

#### Pattern 6: Closed-World Default (Denial)

**Legal text**: "A covered entity may not use or disclose PHI, except as permitted..."

```datalog
is_disclosure_denied(ARGS) :-
    disclosure_attempted(ARGS),
    !is_disclosure_allowed(ARGS, _).
```

This implements the closed-world assumption: if no rule permits the disclosure, it is denied.

### 4.3 Naming Convention

Match the predicate naming to the regulatory structure:

```
permitted_by_164_502           // §164.502 top-level
permitted_by_164_502_a         // §164.502(a)
permitted_by_164_502_a_1       // §164.502(a)(1)
permitted_by_164_502_a_1_i     // §164.502(a)(1)(i)
required_by_164_502_a_2        // §164.502(a)(2)
excluded_164_502_b_2           // §164.502(b)(2) — exception
```

---

## 5. Phase 4: File Organization

### 5.1 Recommended File Structure

```
regulation_types.dl          — Type declarations, Expl ADT
regulation_hierarchies.dl    — Role/attribute/purpose hierarchies
regulation_macros.dl         — Helper predicates (is_X checks)
regulation_stubs.dl          — Empty decls for unformalized sections
regulation_section_NNN.dl    — One file per major section
regulation_top.dl            — Top-level verdict + .output directives
regulation_main.dl           — Entry point (#include all)
regulation_facts.dl          — Test scenario facts
```

### 5.2 Include Order

```datalog
// regulation_main.dl
#include "regulation_types.dl"       // 1. Types first
#include "regulation_hierarchies.dl" // 2. Hierarchies
#include "regulation_macros.dl"      // 3. Helper predicates
#include "regulation_stubs.dl"       // 4. Stubs for unformalized sections
#include "regulation_section_A.dl"   // 5. Rules (dependency order)
#include "regulation_section_B.dl"   //    B references A, so A first
#include "regulation_top.dl"         // 6. Top-level verdict
#include "regulation_facts.dl"       // 7. Facts last
```

### 5.3 Stub Pattern for Incremental Formalization

Declare but don't define predicates for sections not yet formalized:

```datalog
// Stub — no rules means empty relation (conservative default)
.decl permitted_by_section_X(DECL_ARGS, e: Expl)
// When section X is formalized, rules will be added in a separate file
```

---

## 6. Phase 5: Stratification and Negation

### 6.1 Stratification Requirements

Soufflé uses **stratified negation**. Rules must be organized so that:
- A predicate is fully computed before it is negated
- No circular dependencies through negation

**Strata for HIPAA:**
- Stratum 0: Base facts, hierarchies, helpers
- Stratum 1: Positive permission rules (permitted_by_X)
- Stratum 2: Negative norms and negation-based rules (!require_authorization)
- Stratum 3: Top-level verdict (negates is_disclosure_allowed)

### 6.2 Checking Stratification

```bash
souffle --show=precedence-graph regulation_main.dl
```

If you get a stratification error, it means a negation cycle exists. Fix by restructuring the dependency.

---

## 7. Phase 6: Testing

### 7.1 Test Case Structure

For each test case, create a folder with:
- `scenario_XXX.md` — Natural language description, question, expected verdict
- `fact_XXX.dl` — Datalog facts encoding the scenario
- `query_XXX.dl` — Include file linking formalization to facts
- `run_test_case_XXX.sh` — Execution script

### 7.2 Testing Strategy

1. **Positive tests**: One per permission pathway (verify it fires correctly)
2. **Negative tests**: Scenarios that should be denied (verify no false positives)
3. **Boundary tests**: Edge cases (e.g., minor with abuse exception)
4. **Real-world tests**: Actual court cases or regulatory guidance examples
5. **Cross-product check**: Ensure the output doesn't explode due to grounding

### 7.3 Verification Against Source Text

After formalizing, compare clause-by-clause against the original regulation:
- Fetch the actual regulatory text (e.g., from eCFR API)
- For each sub-clause, verify a corresponding Datalog rule exists
- Check that all conditions are captured
- Verify the maximal revelation principle is followed

---

## 8. Phase 7: Agent Integration

### 8.1 Agent Prompt Design

Create a system prompt that instructs an LLM agent to:
1. Parse natural language scenarios into the action signature
2. Map entities to roles using the hierarchy
3. Assert appropriate oracle predicates
4. Run the Datalog engine
5. Interpret the explanation tree
6. Respond with citations

### 8.2 Key Sections in the Agent Prompt

1. **Predicate reference**: Complete list of all facts, oracles, and their argument signatures
2. **Hierarchy reference**: All role/attribute/purpose hierarchies
3. **Scenario encoding template**: Example of how to create a facts file
4. **Common patterns**: Pre-built examples for frequent scenario types
5. **Caveats**: Stubbed sections, limitations, closed-world assumption

---

## 9. Applying to Other Regulations

### 9.1 GDPR (General Data Protection Regulation)

| HIPAA Concept | GDPR Equivalent |
|--------------|-----------------|
| Covered entity | Data controller |
| Business associate | Data processor |
| PHI | Personal data / Special categories |
| TPO purposes | Legitimate interests / Consent / Legal obligation |
| Authorization | Consent (Art. 6, Art. 9) |
| §512 exceptions | Art. 6(1)(b)-(f) legal bases |
| Minimum necessary | Data minimization (Art. 5(1)(c)) |
| Explanation tree | Accountability documentation |

**Action signature**: `(controller, processor, data_subject, data_category, legal_basis, purpose, transfer_destination)`

### 9.2 CCPA (California Consumer Privacy Act)

| HIPAA Concept | CCPA Equivalent |
|--------------|-----------------|
| Covered entity | Business |
| Business associate | Service provider / Third party |
| PHI | Personal information |
| Permitted disclosures | Business purposes / Consumer consent |
| §502(a)(1)(i) to individual | Right to know / Right to access |
| Denial | Opt-out of sale |

**Action signature**: `(business, recipient, consumer, info_category, purpose, is_sale)`

### 9.3 SOX (Sarbanes-Oxley)

Focus is on financial reporting and internal controls rather than data disclosure:

| HIPAA Concept | SOX Equivalent |
|--------------|----------------|
| Covered entity | Issuer / Public company |
| PHI | Financial records / Internal controls |
| Permitted uses | Audit, reporting, oversight |
| Whistleblower (§502(j)) | §806 whistleblower protection |
| Secretary investigation | SEC investigation |

---

## 10. Checklist for New Formalizations

- [ ] Map the regulatory structure (sections → subsections → paragraphs)
- [ ] Define the action signature
- [ ] Identify all types and hierarchies
- [ ] Classify every rule as positive norm, negative norm, or constraint
- [ ] Identify all oracle predicates (subjective/temporal/external conditions)
- [ ] Create type declarations and Expl ADT
- [ ] Build hierarchies with transitive closure
- [ ] Write helper predicates (is_X checks)
- [ ] Create stubs for sections not yet formalized
- [ ] Translate rules following maximal revelation principle
- [ ] Write top-level verdict predicate with closed-world denial
- [ ] Verify stratification (`souffle --show=precedence-graph`)
- [ ] Create test cases (positive, negative, boundary, real-world)
- [ ] Run all tests and verify 100% pass
- [ ] Compare clause-by-clause against original text
- [ ] Write agent prompt with complete predicate reference
