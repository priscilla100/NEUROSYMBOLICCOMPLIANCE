# Research: Handling Non-HIPAA Cases

**Task 4**: Identifying scenarios where the question does not fall under HIPAA jurisdiction and no adjudication is possible.

## What Falls Outside HIPAA Scope?

### 1. Non-Covered Entities
HIPAA only applies to **covered entities** (health plans, health care clearinghouses, health care providers who transmit health information electronically) and their **business associates**. Common scenarios that look like HIPAA but aren't:

| Entity | Regulation | Why Not HIPAA |
|--------|-----------|---------------|
| Employers (non-healthcare) | ADA, state law | Employers are not covered entities unless they are also a health plan |
| Schools (K-12, universities) | FERPA | Student health records are education records under FERPA |
| Life insurance companies | State insurance law | Life insurers are not health plans |
| Fitness apps / wearables | FTC Act, state privacy | App developers are not covered entities |
| Direct-to-consumer genetic testing | FTC, state genetic privacy laws | Companies like 23andMe are not covered entities |
| Law enforcement agencies | Constitutional protections | Police departments are not covered entities |
| Workers' comp insurers (sometimes) | State workers' comp law | May or may not be a covered entity depending on structure |

### 2. Non-PHI Information
Even for covered entities, HIPAA only protects **Protected Health Information** (PHI) — individually identifiable health information. Not PHI:

- De-identified data (per §164.514(a)-(b))
- Education records under FERPA
- Employment records held by a covered entity in its role as employer
- Health information that is not individually identifiable
- Information about someone who has been deceased for more than 50 years

### 3. Non-Disclosure Actions
HIPAA's use/disclosure rules only apply to **uses** and **disclosures** of PHI. Not covered:

- Data retention/destruction policies (separate provisions)
- Physical/technical safeguards (Security Rule, not Privacy Rule)
- Breach notification (§164.400-414, different subpart)
- Patient rights to amend records (§164.526)

### 4. State Law Preemption
HIPAA preempts state law UNLESS the state law is **more stringent** (provides greater privacy protection). In those cases, state law applies instead. The formalization does not capture state-specific provisions.

## Detection Approach

### Layer 1: Structural Detection in Datalog

Add a scope-check predicate:

```datalog
.decl is_hipaa_applicable(DECL_ARGS)
.decl not_hipaa_applicable(DECL_ARGS, reason: symbol)

// Applicable only if sender is a covered entity or BA
is_hipaa_applicable(ARGS) :-
    disclosure_attempted(ARGS),
    (is_covered_entity(p1) ; is_business_associate(p1)),
    is_phi(t).

// Detect non-applicability
not_hipaa_applicable(ARGS, "sender is not a covered entity or business associate") :-
    disclosure_attempted(ARGS),
    !is_covered_entity(p1),
    !is_business_associate(p1).

not_hipaa_applicable(ARGS, "information is not PHI") :-
    disclosure_attempted(ARGS),
    !is_phi(t),
    !is_dii(t).

.output not_hipaa_applicable
```

### Layer 2: Agent-Level Pre-Screening

Before encoding facts, the agent should check:

1. **Is the sender a HIPAA-regulated entity?**
   - Ask: "Is [entity] a healthcare provider, health plan, clearinghouse, or business associate of one?"
   - Red flags: schools, employers, fitness apps, insurers (non-health)

2. **Is the information PHI?**
   - Ask: "Is this individually identifiable health information created or received by a healthcare provider, health plan, or clearinghouse?"
   - Red flags: employment records, education records, de-identified data

3. **Is this a use or disclosure?**
   - Ask: "Is [entity] sharing, releasing, transferring, or providing access to this information?"
   - Red flags: retention policies, security questions, breach notification

### Layer 3: Response Template for Non-HIPAA Cases

```
⚠️ HIPAA MAY NOT APPLY TO THIS SCENARIO

Based on the information provided, this scenario may fall outside 
HIPAA's jurisdiction because:
- [Reason: e.g., "The employer is not a covered entity under HIPAA"]

HIPAA applies to covered entities (health care providers, health 
plans, and health care clearinghouses) and their business associates.

The applicable regulation may instead be:
- [Alternative: e.g., "The Americans with Disabilities Act (ADA) 
  governs employer access to employee medical information"]

Would you like me to:
1. Analyze this scenario under HIPAA anyway (in case the entity 
   qualifies as a covered entity)?
2. Identify which regulation likely applies?
```

## Example Non-HIPAA Scenarios

### Scenario A: Employer Requesting Sick Note
> "My boss at the accounting firm is asking me to bring a doctor's note for my three sick days. Does HIPAA prevent them from asking?"

**Analysis**: The accounting firm is NOT a covered entity. HIPAA does not prevent employers from requesting sick notes. The ADA limits what medical information employers can request, but basic fitness-for-duty documentation is permitted.

### Scenario B: School Sharing Student Health Records
> "My son's elementary school shared his allergy information with the after-school program without my consent."

**Analysis**: K-12 schools are covered by FERPA, not HIPAA. Even if the school has a nurse's office, student health records maintained by the school are education records under FERPA.

### Scenario C: Fitness App Data Sharing
> "My Fitbit shared my heart rate data with a marketing company. Is that a HIPAA violation?"

**Analysis**: Fitbit (and similar consumer health apps) is not a covered entity. The FTC Act and state privacy laws may apply, but HIPAA does not regulate consumer health technology companies unless they are business associates of a covered entity.
