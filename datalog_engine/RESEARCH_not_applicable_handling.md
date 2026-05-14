# Research: Handling "Not Applicable" Through Formalization

**Task 9**: How to determine whether a user's scenario falls under HIPAA jurisdiction, using formalization, GoldCoin-like LLM classification, or steering techniques.

## The Core Question

Before running the compliance checker, we need to answer: **Does this scenario involve a HIPAA-regulated disclosure?** If not, the Datalog engine's verdict is meaningless — it would produce a DENY simply because the entities don't match any HIPAA role, not because the disclosure is actually prohibited.

## Approach 1: Datalog-Based Applicability Check

### Add Scope Predicates to the Formalization

```datalog
// ============================================
// Applicability Check — is HIPAA relevant?
// ============================================

.decl hipaa_applies(DECL_ARGS)
.decl hipaa_not_applicable(DECL_ARGS, reason: symbol)

// HIPAA applies if sender is a CE or BA AND info is PHI
hipaa_applies(ARGS) :-
    disclosure_attempted(ARGS),
    (is_covered_entity(p1) ; is_business_associate(p1)),
    (is_phi(t) ; is_dii(t)).

// Reasons for non-applicability
hipaa_not_applicable(ARGS, "sender-not-regulated") :-
    disclosure_attempted(ARGS),
    !is_covered_entity(p1),
    !is_business_associate(p1).

hipaa_not_applicable(ARGS, "information-not-phi") :-
    disclosure_attempted(ARGS),
    (is_covered_entity(p1) ; is_business_associate(p1)),
    !is_phi(t), !is_dii(t).

.output hipaa_applies
.output hipaa_not_applicable
```

### Advantages
- Integrated into the existing system
- Deterministic and explainable
- Low overhead

### Limitations
- Requires the agent to correctly assign roles — if the agent mistakenly assigns `"hospital"` to a non-healthcare entity, the check passes
- Cannot detect nuanced jurisdictional questions (e.g., state law preemption)

## Approach 2: GoldCoin-Style LLM Classification

### Concept
Use a fine-grained LLM as a pre-filter to classify whether a scenario is HIPAA-applicable before running the Datalog engine.

### Architecture

```
User Question
     │
     ▼
┌─────────────────────┐
│ LLM Applicability   │ ← Prompt: "Does this scenario involve a 
│ Classifier           │    HIPAA-regulated entity disclosing PHI?"
│                     │
│ Output: {           │
│   applicable: bool, │
│   confidence: float,│
│   reason: string,   │
│   alternative_reg:  │
│     string          │
│ }                   │
└─────────────────────┘
     │
     ▼
  applicable?
   ╱      ╲
  Yes       No
   │         │
   ▼         ▼
Run Datalog  Return "Not Applicable"
Engine       with explanation
```

### GoldCoin-Style Structured Prompt

```
You are a HIPAA jurisdiction classifier. Given a scenario, determine 
whether it falls under HIPAA's Privacy Rule (45 CFR Part 164, 
Subpart E).

HIPAA applies when ALL of these conditions are met:
1. The disclosing entity is a "covered entity" (health care provider 
   who transmits health information electronically, health plan, or 
   health care clearinghouse) OR a "business associate" of a covered 
   entity.
2. The information being disclosed is "protected health information" 
   (PHI) — individually identifiable health information created or 
   received by a covered entity.
3. The action is a "use" or "disclosure" of PHI.

HIPAA does NOT apply when:
- The entity is an employer (in its capacity as employer, not as a 
  health plan)
- The entity is a school (FERPA applies instead)
- The entity is a consumer app/device manufacturer (FTC Act applies)
- The information is not individually identifiable
- The information is employment records
- The action is not a use or disclosure (e.g., data retention, 
  security safeguards)

Scenario: {scenario}

Classification:
- Applicable: [Yes/No/Uncertain]
- Confidence: [0.0-1.0]
- Reasoning: [explain why]
- If not applicable, which regulation likely applies: [FERPA/ADA/
  FTC Act/State Law/Other]
```

### Training Data Sources
- **GoldCoin dataset** (25 real court cases — all are HIPAA-applicable)
- **Negative examples**: Create scenarios involving schools (FERPA), employers (ADA), fitness apps (FTC), etc.
- **Edge cases**: Hybrid entities (school that is also a healthcare provider), employer-sponsored health plans

## Approach 3: Steering/Skill Pre-Processing

### Concept
Create an agent "skill" (a pre-processing step) that runs before the main compliance analysis.

### Implementation as an Agent Skill

```yaml
name: hipaa-applicability-check
trigger: "Before any HIPAA compliance analysis"
steps:
  1. Extract entities from the user's question
  2. For each entity, classify:
     - Is it a healthcare provider? (hospitals, clinics, doctors, pharmacies)
     - Is it a health plan? (insurers, HMOs, Medicare, Medicaid)
     - Is it a clearinghouse?
     - Is it a business associate of any of the above?
  3. Classify the information type:
     - Is it health information? (diagnoses, treatments, lab results, etc.)
     - Is it individually identifiable?
  4. Classify the action:
     - Is it a use (internal) or disclosure (external sharing)?
  5. Decision:
     - If entity is covered + info is PHI + action is use/disclosure → APPLICABLE
     - If any condition fails → NOT APPLICABLE with explanation
     - If uncertain → Flag for clarification
```

### Entity Recognition Patterns

| Pattern | Classification |
|---------|---------------|
| "hospital", "clinic", "medical center", "doctor's office" | Healthcare provider (covered entity) |
| "health insurance", "Medicare", "Medicaid", "HMO" | Health plan (covered entity) |
| "billing company", "cloud storage for medical records" | Business associate |
| "employer", "HR department", "my boss" | NOT covered entity (unless also a health plan) |
| "school", "university", "principal" | FERPA, not HIPAA |
| "fitness app", "Apple Watch", "23andMe" | NOT covered entity |

## Approach 4: Hybrid (Recommended)

Combine all three approaches in a layered architecture:

```
┌──────────────────────────────────────────┐
│ Layer 1: Pattern-Based Quick Check       │
│ (Skill/steering — fast, catches obvious) │
│ "Is 'my employer' a covered entity?" → NO│
└──────────────┬───────────────────────────┘
               │ If uncertain
               ▼
┌──────────────────────────────────────────┐
│ Layer 2: LLM Classification              │
│ (GoldCoin-style structured prompt)       │
│ Confidence threshold: 0.85               │
└──────────────┬───────────────────────────┘
               │ If applicable
               ▼
┌──────────────────────────────────────────┐
│ Layer 3: Datalog Scope Check             │
│ (hipaa_applies / hipaa_not_applicable)   │
│ Catches encoding errors                  │
└──────────────┬───────────────────────────┘
               │
               ▼
         Run Compliance Engine
```

### Decision Matrix

| L1 Result | L2 Result | L3 Result | Action |
|-----------|-----------|-----------|--------|
| Applicable | Applicable | Applicable | Run engine |
| Not applicable | — | — | Return "Not HIPAA" |
| Uncertain | Applicable | Applicable | Run engine |
| Uncertain | Not applicable | — | Return "Not HIPAA" |
| Uncertain | Uncertain | — | Ask user for clarification |
| Applicable | Applicable | Not applicable | Review encoding (likely error) |

## Edge Cases Requiring Special Handling

1. **Hybrid entities**: A university that operates a medical school hospital — the hospital component is covered, but the school records aren't
2. **Employer-sponsored health plans**: The employer isn't covered, but the health plan it sponsors IS
3. **State law preemption**: When state law provides stronger protection, HIPAA defers
4. **Research exemptions**: IRB-approved research may have different applicability boundaries
5. **Military/VA**: Special rules under §512(k) for military and veterans

## Implementation Priority

1. **Immediate**: Add the Datalog scope-check predicates (Approach 1) — low effort, catches encoding mistakes
2. **Short-term**: Implement the agent skill (Approach 3) — moderate effort, catches most non-HIPAA cases  
3. **Medium-term**: Add LLM classification layer (Approach 2) — higher effort, best accuracy for edge cases
