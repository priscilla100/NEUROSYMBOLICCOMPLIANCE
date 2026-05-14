# V2 Verification Report -- Round 2

**Date**: 2026-04-14
**Verifier**: Claude Opus 4.6 (1M context)
**Scope**: All v2 .dl files vs. eCFR regulatory text and first-round findings

---

## First-Round Issues: Resolution Status

### eCFR Verification Issues

| # | Issue | Status | Notes |
|---|-------|--------|-------|
| 1 | 502(a)(3)-(4) BA provisions | **FIXED** | `permitted_by_164_502_a_3` (BA permitted uses per BA contract) and `permitted_by_164_502_a_4` (BA required disclosure to Secretary) added in `hipaa_164_502.dl` lines 298-327. Both are wired into the top-level `permitted_by_164_502` at lines 43-44. |
| 2 | 502(a)(5)(i) genetic underwriting prohibition | **FIXED** | `prohibited_genetic_underwriting_502a5i` rule added at line 343 in `hipaa_164_502.dl`. Properly checks `is_health_plan(p1)`, `is_genetic_info(t)`, `is_for_underwriting(u)`. Negated in `permitted_by_164_502_a_1_iv` (line 188). |
| 3 | 502(a)(5)(ii) sale of PHI prohibition | **FIXED** | `prohibited_sale_of_phi_502a5ii` rule added at line 357 in `hipaa_164_502.dl`. Checks CE or BA, receives remuneration, with 8 sale exceptions (lines 369-376) covering TPO, treatment, public health, research, BA activities, individual access, required by law, and cost-based fee. Negated in `permitted_by_164_502_a_1_iv` (line 189). |
| 4 | 508(a)(2)(i)(A) originator exception | **FIXED** | `exception_508a2` rule at line 74 in `hipaa_164_508.dl` models the originator-for-treatment exception: checks `provider_of(p1, q)` and `p1 = p2` (originator using for own treatment). |
| 5 | 508(a)(4) sale authorization | **FIXED** | `require_authorization_sale_508a4` rule added at line 216 in `hipaa_164_508.dl`. Properly checks CE or BA, receives remuneration, negates sale exceptions, and requires authorization. Declared in `hipaa_stubs.dl` line 78. |
| 6 | 508 defective authorization negation | **FIXED** | `!is_defective_authorization(_, p1, p2, q, t, u)` negation added to `permitted_by_164_502_a_1_iv` at line 187 in `hipaa_164_502.dl`. |
| 7 | 510(b)(5) deceased disclosure | **FIXED** | `permitted_by_164_510_b_5` rule added at lines 326-337 in `hipaa_164_510.dl`. Checks `belongs_to(q, "deceased")`, `is_care_involvement_recipient(p2, q)`, `relevant_to_involvement(t, p2, q)`, and negates `inconsistent_with_prior_preference`. |
| 8 | 512(b)(1)(vi) school immunization | **FIXED** | `permitted_by_164_512_b_1_vi` rule added at lines 880-896 in `hipaa_164_512.dl`. Checks `school_requires_immunization_proof` and `has_obtained_agreement_for_school_disclosure` oracles. Wired into `permitted_by_164_512_b` at line 79. |
| 9 | 512(d)(2) oversight exception | **PARTIALLY FIXED** | `blocked_by_512d2` predicate declared and defined at lines 940-943 in `hipaa_164_512.dl`. However, **it is NOT wired into the `permitted_by_164_512_d` rule** (line 251). The guard `!blocked_by_512d2(q, p2)` is never applied, making the predicate dead code. |
| 10 | 512(f)(2)(ii) DNA prohibition | **FIXED** | `is_dna_dental_body_fluid` predicate defined at lines 389-391 and negated with `!is_dna_dental_body_fluid(t)` guard at line 400 in the `permitted_by_164_512_f_2` rule. |
| 11 | 512(k)(1)(iv) foreign military | **FIXED** | Rule added at lines 904-910 in `hipaa_164_512.dl`. Checks `belongs_to(q, "foreign-military-personnel")` and `deemed_appropriate_by_secretary_foreign_military` oracle. |
| 12 | 512(k)(5)(ii)-(iii) correctional | **PARTIALLY FIXED** | (ii) CE-as-institution internal use rule added at lines 915-923. (iii) Release rule: `individual_released_from_custody` is declared (line 928) but **has no rule body or guard**. It is not negated in either k(5) rule, so disclosures are not blocked after release. This is dead code. |
| 13 | 514(h) verification | **FIXED** | `verification_satisfied_514h` predicate with rules at lines 193-202 in `hipaa_164_514.dl`. Checks `identity_known_to_ce` or `identity_verified`, with exception for disclosures to the individual. Declared in `hipaa_stubs.dl` line 81. |
| 14 | 506(a) missing 508(a)(4) sale guard | **FIXED** | `!require_authorization_sale_508a4(ARGS)` added at line 50 in `hipaa_164_506.dl`, alongside the existing `!require_authorization_by_164_508(ARGS)` negation. |

### Maximal Revelation Issues

| # | Issue | Status | Notes |
|---|-------|--------|-------|
| 15 | 512(c) split into 3 rules | **FIXED** | Three separate rules at lines 201, 213, and 225 in `hipaa_164_512.dl`: (c)(1)(i) required by law, (c)(1)(ii) individual agrees, (c)(1)(iii) authorized by statute + necessary to prevent harm. Each has distinct provenance leaf. |
| 16 | 510(b)(1)(i) split (agreement vs. professional judgment) | **FIXED** | Two separate rules at lines 154 and 164 in `hipaa_164_510.dl`: Path A (individual agrees/no objection via 510(b)(2)) and Path B (professional judgment via 510(b)(3)). Same pattern applied to 510(b)(1)(ii) at lines 190 and 203. |
| 17 | 510(b)(4) split into 3 rules | **FIXED** | Three separate rules at lines 282, 292, and 302 in `hipaa_164_510.dl`: Path A (individual agrees), Path B (professional judgment), Path C (requirements interfere with emergency). |
| 18 | 502(c) split into 2 rules | **FIXED** | Two separate rules at lines 468 and 475 in `hipaa_164_502.dl`: one for `permitted_by_164_522_a_1` (compliant with restriction) and one for `permitted_by_164_522_a` (exception under 522(a)). |
| 19 | 502(a)(5)(i) negation missing | **FIXED** | See issue #2 above. |
| 20 | Defective authorization negation | **FIXED** | See issue #6 above. |
| 21 | DNA/dental prohibition guard | **FIXED** | See issue #10 above. |

---

## New Issues Found in V2

### Issue N1: `blocked_by_512d2` is dead code (HIGH)

The predicate `blocked_by_512d2` is properly defined at `hipaa_164_512.dl` lines 940-943 with correct logic (blocks when individual is subject of investigation unless investigation relates to health care). However, it is **never negated in `permitted_by_164_512_d`** (line 251). The 512(d) rule permits health oversight disclosure without checking whether the exception at 512(d)(2) applies. This means PHI could be disclosed for oversight when the individual is the subject of a non-health-care investigation, violating the CFR.

**Fix**: Add `!blocked_by_512d2(q, p2)` to the body of `permitted_by_164_512_d` at line 251.

### Issue N2: `individual_released_from_custody` is dead code (MEDIUM)

The predicate is declared at line 928 but never used as a guard. Per CFR 512(k)(5)(iii), correctional disclosures are "no longer [permitted] after release." The k(5)(i) and k(5)(ii) rules do not negate `individual_released_from_custody`, so disclosures would still be permitted after an inmate is released.

**Fix**: Add `!individual_released_from_custody(q, p2)` to both `permitted_by_164_512_k_5` rules.

### Issue N3: `verification_satisfied_514h` is declared but never used as a guard (MEDIUM)

The verification predicate is properly defined with correct logic but is **never negated or conjuncted into any disclosure rule**. Per CFR 514(h), verification is a precondition for all disclosures under this subpart (except 164.510). Without wiring this into the top-level or individual rules, verification is not enforced.

**Fix**: Either add `verification_satisfied_514h(ARGS)` as a guard in `hipaa_top.dl`'s `is_disclosure_allowed`, or add it to each relevant pathway. Note: must exclude 164.510 pathways per the CFR exception.

### Issue N4: 502(a)(4)(ii) BA required disclosure to individual for electronic copy missing (LOW)

CFR 502(a)(4)(ii): "To the covered entity, individual, or individual's designee, as necessary to satisfy a covered entity's obligations under 164.524(c)(2)(ii) and (3)(ii) with respect to an individual's request for an electronic copy." The current `permitted_by_164_502_a_4` only models disclosure to the Secretary (a)(4)(i), not this electronic copy provision.

### Issue N5: 506(a) missing 502(a)(5)(i) prohibition guard (MEDIUM)

CFR 506(a): "Except with respect to uses or disclosures that require an authorization under 164.508(a)(2) through (4) **or that are prohibited under 164.502(a)(5)(i)**..." The current 506(a) rule (line 47) negates `require_authorization_by_164_508` and `require_authorization_sale_508a4`, but does **not** negate `prohibited_genetic_underwriting_502a5i`. A health plan disclosing genetic info for underwriting TPO would not be blocked by 506(a).

**Fix**: Add `!prohibited_genetic_underwriting_502a5i(ARGS)` to `permitted_by_164_506_a`.

### Issue N6: Sale exception list is incomplete (LOW)

CFR 502(a)(5)(ii)(B)(2) lists 8 exceptions. The formalization has 8 rules at lines 369-376 but:
- Exception (iv) (sale/transfer/merger/consolidation) is mapped to `is_for_tpo(u)` which is imprecise -- CFR specifically limits it to "the definition of health care operations paragraph (6)(iv)" not all TPO.
- Exception (viii) (reasonable cost-based fee for any permitted purpose) is mapped to `is_required_by_law` which does not capture the broader "any other purpose permitted" language.

### Issue N7: 510(b)(1)(ii) notification missing "death" attribute (LOW)

CFR 510(b)(1)(ii) permits notification of "location, general condition, **or death**." The `is_location_condition_death` predicate at line 183-187 covers `patient-location` and `patient-condition` but does not explicitly include a death attribute. While `date-and-time-of-death` exists in the attribute hierarchy, it is not classified under `is_location_condition_death`.

### Issue N8: 510(b)(4) disaster relief CFR mismatch (LOW)

CFR 510(b)(4) says "The requirements in paragraphs (b)(2), (b)(3), **or (b)(5)** of this section apply to such uses and disclosures to the extent that the covered entity... determines that the requirements do not interfere with the ability to respond to the emergency circumstances." The formalization does not include the (b)(5) deceased path for disaster relief.

---

## Remaining Gaps (from Round 1, NOT fixed)

| Gap | Section | Severity | Notes |
|-----|---------|----------|-------|
| 510(a)(3)(ii) must-inform-when-practicable | 510 | LOW | Procedural obligation, not a permission/denial rule. Acceptable as oracle. |
| 512(b)(2) CE as public health authority USE | 512 | MEDIUM | CFR: "If the CE also is a public health authority, the CE is permitted to USE PHI in all cases in which it is permitted to disclose." No rule models this USE pathway. |
| 512(c)(2) must inform individual | 512 | LOW | Procedural obligation. Acceptable as oracle. |
| 512(d)(3) joint activities | 512 | LOW | CFR: joint activity with non-health claim is still health oversight. Not modeled but edge case. |
| 512(d)(4) permitted uses | 512 | LOW | CFR: CE that is oversight agency may USE (not just disclose). Not modeled. |
| 512(e)(1)(iii)-(v) satisfactory assurance details | 512 | LOW | Three conditions for satisfactory assurance decomposed; currently oracle. |
| 512(i)(2) waiver documentation requirements | 512 | LOW | Documentation requirements -- appropriate as oracle. |
| 512(k)(7) NICS reporting | 512 | MEDIUM | Entire sub-section missing. No rules for National Instant Criminal Background Check System reporting. |
| 502(d)(2)(i)-(ii) re-identification code = PHI | 502 | LOW | Constraint that re-identification codes are PHI. Not modeled. |
| 502(e)(1)(ii) BA-to-subcontractor chain | 502 | MEDIUM | CFR allows BA-to-sub-BA disclosure. Not modeled. |
| 502(f) 50-year deceased rule | 502 | LOW | Temporal constraint. Acceptable as oracle limitation. |
| 514(d)(3)(iii) reasonable reliance | 514 | LOW | Four categories of reasonable reliance. Currently oracle. |
| 514(e)(4) DUA contents requirements | 514 | LOW | Data use agreement contents. Appropriate as oracle. |
| 514(f)(1) fundraising PHI types | 514 | LOW | Only 2 of 6 PHI types modeled (demographic-info, healthcare-dates). Missing: department of service, treating physician, outcome info, health insurance status. |
| 514(f)(2)(ii)-(iv) fundraising opt-out | 514 | LOW | Opt-out mechanism, conditioning prohibition, honor opt-out. Procedural. |
| 524(b)(2) 30-day timely action | 524 | LOW | Temporal/procedural. |
| 524(c)(1)-(4) provision of access details | 524 | LOW | Procedural requirements. |
| 524(d)(1)-(4) denial procedures | 524 | LOW | Procedural requirements. |
| 524(e) documentation requirement | 524 | LOW | Administrative requirement. |

---

## Maximal Revelation Status

Of the 23 original violations identified in Round 1:

| # | Violation | Status |
|---|-----------|--------|
| 1 | 502(a)(1)(iv) missing 502(a)(5)(i) negation | **FIXED** |
| 2 | 506(a) missing 508(a)(4) sale negation | **FIXED** |
| 3 | 502(j)(1) missing `is_authorized_by_law_for_purpose` for oversight | **NOT FIXED** -- `permitted_by_164_502_j_1` (line 645) still does not check `is_authorized_by_law_for_purpose(p2, u)` for the oversight agency branch. CFR says "authorized by law to investigate or otherwise oversee the relevant conduct." |
| 4 | 512(f)(1)(ii)(C) administrative request 3 conditions | **NOT FIXED** -- Still a single oracle `in_compliance_with_court_order`. |
| 5 | 514(f)(1) fundraising PHI types (2 of 6) | **NOT FIXED** -- Still only `is_demographic_info` and `is_healthcare_dates`. |
| 6 | 512(c)(1) split into 3 rules | **FIXED** |
| 7 | 502(c) split into 2 rules | **FIXED** |
| 8 | 510(b)(1)(i) split into 2 rules | **FIXED** |
| 9 | 510(b)(4) split into 3 rules | **FIXED** |
| 10 | 502(a)(5)(i) negation absent | **FIXED** |
| 11 | 508(b)(2) defective authorization negation | **FIXED** |
| 12 | 512(d)(2) oversight exception | **PARTIALLY FIXED** (declared but not wired) |
| 13 | 512(f)(2)(ii) DNA prohibition | **FIXED** |
| 14 | 510(b)(5) prior preference | **FIXED** (entire rule added with negation) |
| 15 | `obtained_authorization_164_508` oracle granularity | **PARTIALLY FIXED** -- defective auth is now checked, but validity oracle is still monolithic. |
| 16 | `has_not_objected_to_directory` oracle granularity | **NOT FIXED** -- still single oracle. |
| 17 | `has_lawful_process_with_assurance` oracle granularity | **NOT FIXED** -- still single oracle. |
| 18 | `minor_acts_as_individual` oracle granularity | **NOT FIXED** -- still single oracle. |
| 19 | `in_compliance_with_court_order` oracle granularity | **NOT FIXED** -- still single oracle (same as #4). |
| 20 | `meets_policies_and_criteria` oracle granularity | **NOT FIXED** -- still single oracle. |
| 21 | 512(c) purpose hardcoded to "reports-of-abuse" | **NOT FIXED** -- all three 512(c) rules still use `u = "reports-of-abuse"`. |
| 22 | 512(i)(2) waiver documentation | **NOT FIXED** -- still oracle. |
| 23 | 514(f) fundraising PHI types | **NOT FIXED** (same as #5). |

**Summary**: 11 of 23 FIXED, 2 PARTIALLY FIXED, 10 NOT FIXED (7 are oracle granularity issues rated medium/lower priority in Round 1).

---

## Fresh Clause-by-Clause Findings

### 506(a) -- Missing prohibition guard
See Issue N5 above. CFR explicitly says "or that are prohibited under 164.502(a)(5)(i)." This guard is absent.

### 508(a)(2)(ii) -- Cross-reference to 512(d) is under-specified
CFR says "permitted by 164.512(d) with respect to the **oversight of the originator of the psychotherapy notes**." The formalization's `exception_508a2` at line 107 permits all of 512(d), not just oversight of the originator. This is an over-approximation.

### 510(b)(1)(i) -- CFR now references (b)(5)
CFR 510(b)(1)(i): "in accordance with paragraphs (b)(2), (b)(3), **or (b)(5)**." The formalization correctly separates (b)(2) and (b)(3) paths but the (b)(5) deceased path is handled as a separate predicate `permitted_by_164_510_b_5`, not as a sub-path of (b)(1)(i). This is architecturally acceptable since (b)(5) is a standalone permission path.

### 512(c)(1)(iii)(B) -- Missing incapacity branch
CFR 512(c)(1)(iii) has two sub-conditions: (A) believes necessary to prevent serious harm, or (B) individual unable to agree and law enforcement represents non-use against individual. The formalization only models (A) at line 225. Branch (B) is missing.

### 512(e)(1)(ii) -- Missing satisfactory assurance decomposition
CFR 512(e)(1)(ii) decomposes into (A) notice+opportunity and (B) qualified protective order. The formalization uses a single oracle `has_lawful_process_with_assurance`.

### 512(k)(6)(ii) -- Missing second pathway
CFR 512(k)(6) has two paragraphs: (i) for health plans sharing eligibility/enrollment, and (ii) for government agencies serving same/similar populations. The formalization only models paragraph (i) logic -- it requires `is_health_plan(p1)` and `is_government_benefits_program` for both sender and receiver, but (ii) is broader (any covered entity that is a government agency).

---

## Overall Assessment

### What was successfully fixed (11 of 17 tracked issues)
The v2 formalization addressed the highest-priority issues from Round 1:
- **Prohibition enforcement** (502(a)(5)(i) genetic, 502(a)(5)(ii) sale) -- both now block disclosures correctly
- **Business associate provisions** (502(a)(3)-(4)) -- BA-initiated disclosures now have pathways
- **Authorization integrity** (508(a)(4) sale auth, 508(b)(2) defect negation, 508(a)(2)(i)(A) originator exception) -- authorization pathway is now more robust
- **Missing permission pathways** (510(b)(5) deceased, 512(b)(1)(vi) school immunization, 512(k)(1)(iv) foreign military, 512(k)(5)(ii) correctional internal use)
- **Maximal revelation splits** (512(c), 510(b)(1)(i), 510(b)(4), 502(c)) -- all properly decomposed

### Critical issues remaining (3 items)
1. **`blocked_by_512d2` not wired** -- health oversight disclosures lack the individual-as-subject exception guard (HIGH)
2. **`verification_satisfied_514h` not wired** -- verification requirements are defined but never enforced (MEDIUM-HIGH)
3. **506(a) missing `prohibited_genetic_underwriting_502a5i` guard** -- genetic underwriting prohibition not enforced for TPO pathway (MEDIUM-HIGH)

### Medium-priority gaps
- `individual_released_from_custody` not wired as guard on 512(k)(5)
- 502(a)(4)(ii) electronic copy provision missing
- 512(b)(2) CE-as-public-health-authority USE pathway missing
- 512(c)(1)(iii)(B) incapacity branch missing
- 512(k)(7) NICS reporting entirely missing
- 502(e)(1)(ii) BA-to-subcontractor chain missing
- Oracle granularity issues (7 items) -- lower priority, affect explanation quality not correctness

### Production readiness
The formalization is **not yet production-ready** due to the 3 critical issues above (dead code that creates false permissions or fails to enforce required constraints). After wiring `blocked_by_512d2`, `verification_satisfied_514h`, and adding the 502(a)(5)(i) guard to 506(a), the core permission/denial logic would be substantially correct for the sections covered. The remaining gaps are either edge cases, procedural obligations (appropriate as oracles), or oracle granularity improvements that affect explanation quality rather than correctness.

**Estimated effort to reach production-ready**: 3 critical fixes (approximately 3 lines of code each), plus the medium-priority items for comprehensive coverage.
