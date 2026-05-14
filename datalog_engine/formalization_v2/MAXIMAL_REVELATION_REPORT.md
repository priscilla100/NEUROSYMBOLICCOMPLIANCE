# Maximal Revelation Verification Report

## Summary
- Rules checked: ~120 (across all .dl files)
- Violations found: 23
- Under-decomposition (conjunctions): 5
- Under-decomposition (disjunctions): 4
- Missing negation exposure: 5
- Over-decomposition: 0
- Oracle granularity issues: 9

## Findings by Category

### Category 1: Under-decomposition — Conjunctions Not Split

**1. `hipaa_164_502.dl` line 184 — §502(a)(1)(iv) authorization**
CFR: "Except for uses prohibited under 502(a)(5)(i), pursuant to a valid authorization under §164.508."
Two AND conditions: (a) not prohibited by 502(a)(5)(i), AND (b) valid authorization.
Rule only checks (b). The 502(a)(5)(i) negation is missing entirely.

**2. `hipaa_164_506.dl` line 47 — §506(a) standard TPO**
CFR: "except 508(a)(2) through (4)". Rule negates `require_authorization_by_164_508` which covers (a)(2) psych notes and (a)(3) marketing but NOT (a)(4) sale.
Should be three separate negated conditions.

**3. `hipaa_164_502.dl` lines 549-560 — §502(j)(1) whistleblower**
CFR requires oversight agency to be "authorized by law to investigate the relevant conduct." The `is_authorized_by_law_for_purpose` check is missing for the oversight branch.

**4. `hipaa_164_512.dl` line 334 — §512(f)(1)(ii)(C) administrative request**
CFR specifies 3 conditions for administrative requests. Currently uses a single oracle `in_compliance_with_court_order` for all 3 types.

**5. `hipaa_164_514.dl` — §514(f)(1) fundraising PHI types**
CFR lists 6 PHI types; formalization only models demographic-info and healthcare-dates (2 of 6).

### Category 2: Under-decomposition — Disjunctions Not Split

**6. `hipaa_164_512.dl` lines 199-212 — §512(c)(1) abuse/neglect**
Three alternative grounds (required by law, individual agrees, authorized+necessary) in a single rule body disjunction. Should be THREE separate rules for provenance clarity.

**7. `hipaa_164_502.dl` line 381 — §502(c) restriction agreements**
Two paths in single disjunction. Should be two separate rules.

**8. `hipaa_164_510.dl` lines 159-161 — §510(b)(1)(i) care involvement**
Agreement vs. professional judgment in one rule body. Should be two separate rules (different scenarios: patient present vs. absent).

**9. `hipaa_164_510.dl` lines 267-270 — §510(b)(4) disaster relief**
Three-way disjunction in one rule. Should be three rules.

### Category 3: Missing Negation Exposure

**10. `hipaa_164_502.dl` line 184 — §502(a)(5)(i)**
"Except" requires `!prohibited_502a5i(ARGS)`. Negation entirely absent.

**11. `hipaa_164_508.dl` — defective authorization**
CFR 508(b)(2): "An authorization is not valid if..." The `is_defective_authorization` oracle is declared but never negated in any rule.

**12. `hipaa_164_512.dl` — §512(d)(2) oversight exception**
"does not include investigation of individual... unless related to health care" — double negation pattern not modeled.

**13. `hipaa_164_512.dl` — §512(f)(2)(ii) DNA prohibition**
Explicit prohibition on DNA/dental/tissue info for LE identification. Needs `!is_dna_dental_body_fluid(t)` guard. Not present.

**14. `hipaa_164_510.dl` — §510(b)(5) prior preference**
"unless doing so is inconsistent with prior expressed preference" — negation required. Rule entirely missing.

### Category 4: Over-decomposition
No instances found. The formalization generally errs toward under-decomposition.

### Category 5: Oracle Granularity Issues

**15. `obtained_authorization_164_508`** — Single oracle hides validity check (508(b)(1)), defect check (508(b)(2)), core elements (508(c)(1)-(4)). Should decompose into validity + non-defective + elements.

**16. `has_not_objected_to_directory`** — Hides two-step process: (1) CE informed individual, (2) individual did not object. Should be two predicates.

**17. `has_lawful_process_with_assurance`** — Hides disjunction between (A) notice+opportunity and (B) qualified protective order. Should be two separate rules.

**18. `minor_acts_as_individual`** — Hides three conditions from 502(g)(3)(i)(A)-(C). Should be three predicates.

**19. `in_compliance_with_court_order`** — Hides three types: court order, grand jury subpoena, administrative request. Should be three rules.

**20. `meets_policies_and_criteria`** — Hides routine vs. non-routine distinction from 514(d)(3). Should be two predicates.

**21. `believes_victim_of_abuse` + purpose `"reports-of-abuse"`** — In §512(c), purpose is hardcoded. CFR allows broader purposes (protective services, not just reporting).

**22-23.** Additional minor granularity issues in §512(i)(2) waiver documentation and §514(f) fundraising PHI types.

## Recommendations

### High Priority (affect explanation quality and correctness)

1. **Split §512(c) into 3 rules** — one per ground (required by law, individual agrees, authorized+necessary)
2. **Split §510(b)(1)(i) into 2 rules** — agreement path vs. professional judgment path
3. **Add §502(a)(5)(i) negation** to authorization check
4. **Add defective authorization negation** to 508 validation
5. **Add DNA/dental prohibition** guard on §512(f)(2)

### Medium Priority (improve provenance/explanation)

6. Decompose `obtained_authorization_164_508` into validity + non-defective
7. Decompose `has_not_objected_to_directory` into informed + not-objected
8. Decompose `in_compliance_with_court_order` into 3 types
9. Split §510(b)(4) disaster relief disjunction into 3 rules
10. Decompose `minor_acts_as_individual` into 3 conditions

### Lower Priority (completeness)

11. Add missing §512(d)(2) oversight exception
12. Decompose `meets_policies_and_criteria` (routine vs. non-routine)
13. Broaden §512(c) purpose beyond "reports-of-abuse"
