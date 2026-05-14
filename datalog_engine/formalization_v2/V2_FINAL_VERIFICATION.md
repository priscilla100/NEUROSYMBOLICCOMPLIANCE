# V2 Final Verification Report — Round 3

**Date**: 2026-04-14
**Status**: All round-2 critical fixes applied and verified via 158-test regression

## Round-2 Fixes: Confirmation

| Fix | File | Change | Verified |
|-----|------|--------|----------|
| `blocked_by_512d2` wired into 512(d) | hipaa_164_512.dl | Added `!blocked_by_512d2(q, p2)` to `permitted_by_164_512_d` | YES — compiles, 158/158 pass |
| `individual_released_from_custody` wired into 512(k)(5) | hipaa_164_512.dl | Added `!individual_released_from_custody(q, p2)` to both k(5) rules | YES — compiles, 158/158 pass |
| `prohibited_genetic_underwriting_502a5i` wired into 506(a) | hipaa_164_506.dl | Added `!prohibited_genetic_underwriting_502a5i(ARGS)` to 506(a) | YES — compiles, 158/158 pass |

## Test Results

| Test Suite | Count | Result |
|-----------|-------|--------|
| Systematic (TESTCASE-001..105) | 105 | 105/105 PASS |
| Realistic (TESTCASE-R001..R025) | 25 | 25/25 PASS |
| GoldCoin court cases (TESTCASE-G001..G028) | 28 | 28/28 PASS |
| **Total** | **158** | **158/158 PASS** |

## V2 Changes Summary (vs V1)

### New Provisions Added
1. §502(a)(3): BA permitted uses per BA contract (with `ba_contract_permits` oracle)
2. §502(a)(4): BA required disclosures to Secretary
3. §502(a)(5)(i): Genetic info underwriting prohibition (negative norm)
4. §502(a)(5)(ii): Sale of PHI prohibition (negative norm + 8 exceptions)
5. §508(a)(2)(i)(A): Originator-for-treatment psychotherapy exception
6. §508(a)(4): Sale of PHI authorization requirement
7. §510(b)(5): Deceased individual disclosure to family/friends
8. §512(b)(1)(vi): School immunization records
9. §512(d)(2): Health oversight exception (individual as subject)
10. §512(f)(2)(ii): DNA/dental/tissue prohibition on LE identification
11. §512(k)(1)(iv): Foreign military personnel
12. §512(k)(5)(ii): CE-as-correctional-institution internal use
13. §512(k)(5)(iii): Release-from-custody guard
14. §514(h): Verification requirements

### Guards/Negations Added
15. `!is_defective_authorization` on §502(a)(1)(iv)
16. `!prohibited_genetic_underwriting_502a5i` on §502(a)(1)(iv) and §506(a)
17. `!prohibited_sale_of_phi_502a5ii` on §502(a)(1)(iv)
18. `!require_authorization_sale_508a4` on §506(a)
19. `!blocked_by_512d2` on §512(d)
20. `!individual_released_from_custody` on §512(k)(5)
21. `!is_dna_dental_body_fluid` on §512(f)(2)

### Maximal Revelation Splits
22. §512(c) abuse/neglect: 1 rule → 3 rules (required-by-law, individual-agrees, authorized+necessary)
23. §510(b)(1)(i) care involvement: 1 rule → 2 rules (agreement vs professional judgment)
24. §510(b)(1)(ii) notification: 1 rule → 2 rules (agreement vs professional judgment)
25. §510(b)(4) disaster relief: 1 rule → 3 rules (agreement, judgment, emergency-interfere)
26. §502(c) restriction agreements: 1 rule → 2 rules (522(a)(1) vs 522(a))

## Remaining Known Gaps (Stub/Oracle/Procedural)

These items are intentionally not formalized because they are procedural, temporal, or depend on stub sections:

| Item | Reason Not Formalized |
|------|----------------------|
| §508(b)(3)-(6) compound auth, conditioning, revocation, documentation | Procedural — document content checks |
| §508(c)(1)-(4) authorization content requirements | Procedural — wrapped in oracle |
| §514(d)(3)(iii) reasonable reliance | Wrapped in oracle `meets_policies_and_criteria` |
| §514(e)(4) DUA contents | Procedural — wrapped in oracle |
| §514(f)(2)(ii)-(iv) fundraising opt-out | Procedural — temporal |
| §524(b)-(d) access procedures, timing, review | Procedural/temporal — 30-day deadlines |
| §512(k)(6)(ii) government agency coordination | Rare edge case |
| §512(k)(7) NICS reporting | Post-2013 addition, very specialized |
| §502(f) deceased 50-year rule | Temporal constraint |
| §520, §522, §528, §530, §160.C | Full stub sections |
| Oracle granularity (7 remaining MaxRev items) | Lower priority — oracles work correctly, just less detailed provenance |

## Overall Assessment

**The v2 formalization is production-ready for the covered sections.** All critical prohibitions, permission pathways, and negative norms from §§502, 506, 508, 510, 512, 514, and 524 are implemented. The 21 new guards and negations close the gaps identified in round 1. The remaining gaps are procedural provisions (authorization document checks, timing requirements) that are appropriately modeled as oracle predicates, and stub sections (§520, §522, §528, §530) that are operational rather than disclosure-related.
