# Round 5 Verification Report — Fresh Independent eCFR Comparison

**Date**: 2026-04-14
**Method**: Manual line-by-line reading of eCFR text (fetched 2024-04-26 via API) against every rule in every v2 .dl file
**Approach**: Fresh independent review — did not reference any previous round's analysis. Re-read all eCFR sections and all .dl files from scratch.
**Test Results**: 158/158 PASS (105 systematic + 25 realistic + 28 GoldCoin)

---

## Findings and Fixes

### Finding 1: §502(a)(1)(iv) — Incorrect sale prohibition guard (FIXED)

**CFR text**: "Except for uses and disclosures prohibited under § 164.502(a)(5)(i), pursuant to and in compliance with a valid authorization under § 164.508"

**Issue**: The rule had `!prohibited_sale_of_phi_502a5ii(ARGS)` as a guard. But the CFR only says "prohibited under (a)(5)(i)" — the genetic underwriting prohibition. The sale prohibition (a)(5)(ii) is a separate mechanism that requires authorization under §508(a)(4); it does NOT block the authorization pathway itself. If you HAVE a valid authorization, a sale is permitted via §502(a)(1)(iv).

**Fix**: Removed `!prohibited_sale_of_phi_502a5ii(ARGS)` from `permitted_by_164_502_a_1_iv`. Only `!prohibited_genetic_underwriting_502a5i(ARGS)` remains as the guard, matching the CFR exactly.

### Finding 2: §502(j)(2)(ii) — Missing info limitation constraint (FIXED)

**CFR text**: "The protected health information disclosed is limited to the information listed in § 164.512(f)(2)(i)."

**Issue**: The rule had a comment saying "stubbed for now" — the constraint was not enforced. Per maximal revelation, this explicit limitation should be an explicit guard.

**Fix**: Added `is_limited_identifying_info(t)` to the body of `permitted_by_164_502_j_2`. This restricts crime victim disclosures to the 8 limited identifying types (name-and-address, date-and-place-of-birth, SSN, blood type, type of injury, treatment date/time, death date/time, physical characteristics).

### Finding 3: §512(f)(2)(ii) — Incomplete DNA/dental prohibition (FIXED)

**CFR text**: "the covered entity may not disclose... any protected health information related to the individual's DNA or DNA analysis, dental records, or typing, samples or analysis of body fluids or tissue."

**Issue**: `is_dna_dental_body_fluid` only covered `"genetic-info"`. The CFR also prohibits dental records and body fluid/tissue analysis.

**Fix**: Added `"dental-records"` and `"body-fluid-tissue-analysis"` to `is_dna_dental_body_fluid` predicate. Added corresponding `attr_isa` entries in `hipaa_hierarchies.dl`.

### Finding 4: No other missing clauses found

After re-reading all 7 eCFR sections clause-by-clause against the v2 formalization, I confirm that every disclosure-related provision has a corresponding Datalog rule or oracle predicate. The remaining unformalized items are all procedural (document content, timing, format).

---

## Maximal Revelation Check

After re-reading every rule in every .dl file:

| Check | Result |
|-------|--------|
| Conjunctions properly decomposed | YES — all AND conditions are separate body literals |
| Disjunctions properly split into separate rules | YES — §512(c) has 3 rules, §510(b)(1) has 2 rules each, §510(b)(4) has 3 rules, §502(c) has 2 rules |
| Negations explicitly exposed | YES — `!blocked_by_512d2`, `!individual_released_from_custody`, `!prohibited_genetic_underwriting`, `!is_defective_authorization`, `!is_dna_dental_body_fluid`, `!believes_emergency_result_of_abuse`, `!learned_while_treating_propensity`, `!learned_through_request_for_treatment`, `!abuse_exception`, `!minor_acts_as_individual` |
| No over-decomposition | CORRECT — no semantic units are inappropriately split |
| Oracle granularity | ACCEPTABLE — 7 composite oracles remain (e.g., `has_lawful_process_with_assurance`, `obtained_authorization_164_508`) that wrap multiple sub-conditions. These function correctly; further decomposition is a documentation enhancement, not a correctness issue. |

---

## Constraint Verification

| Constraint | Section | Implemented? |
|-----------|---------|-------------|
| Minimum necessary | §502(b) | YES — `minimum_necessary_satisfied` with 6 exceptions |
| Authorization validity | §508(b) | YES — `!is_defective_authorization` guard |
| Genetic underwriting prohibition | §502(a)(5)(i) | YES — blocks §502(a)(1)(iv) and §506(a) |
| Sale of PHI prohibition | §502(a)(5)(ii) | YES — blocks via `require_authorization_sale_508a4` on §506(a) |
| DNA/dental prohibition on LE ID | §512(f)(2)(ii) | YES — `!is_dna_dental_body_fluid` guard |
| Crime victim info limit | §502(j)(2)(ii) | YES — `is_limited_identifying_info(t)` (newly enforced) |
| Learned-in-treatment prohibition | §512(j)(2) | YES — 2 negation guards |
| Abuse-based emergency LE block | §512(f)(6)(ii) | YES — `!believes_emergency_result_of_abuse` |
| Individual release from custody | §512(k)(5)(iii) | YES — `!individual_released_from_custody` |
| Health oversight exception | §512(d)(2) | YES — `!blocked_by_512d2` |
| Fundraising opt-out | §514(f)(2)(ii)-(iv) | YES — `blocked_fundraising_opt_out` |
| Verification requirements | §514(h) | YES — `verification_satisfied_514h` |

---

## Final Assessment

The v2 formalization is **verified complete** for disclosure-decision purposes. Three fixes were applied in this round:

1. Corrected an over-restrictive guard on §502(a)(1)(iv) (sale prohibition was incorrectly blocking the authorization pathway)
2. Enforced the §502(j)(2)(ii) info limitation constraint (was previously stubbed)
3. Expanded the §512(f)(2)(ii) DNA/dental prohibition to cover all 3 prohibited categories

All 158 test cases pass. Every disclosure-related clause in the CFR has been accounted for. The formalization correctly implements the permission/prohibition/constraint architecture of HIPAA's Privacy Rule.
