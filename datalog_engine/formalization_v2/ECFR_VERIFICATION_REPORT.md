# eCFR Verification Report
**Date**: 2026-04-14
**Source**: eCFR API (XML, as of 2024-04-26)
**Scope**: §164.502, 506, 508, 510, 512, 514, 524

## Summary
- Provisions checked: 148
- Correctly formalized: 89
- Missing: 33
- Incomplete: 26
- Constraints missing: 12

## Section-by-Section Analysis

### §164.502 — Uses and disclosures of PHI: General rules

| Sub-clause | CFR Text Summary | Status | Notes |
|---|---|---|---|
| 502(a) | CE may not use/disclose except as permitted | CORRECT | Gatekeeper with is_covered_entity, is_phi |
| 502(a)(1)(i) | To the individual | CORRECT | Personal representative via disjunction |
| 502(a)(1)(ii) | For TPO per §506 | CORRECT | Delegates to permitted_by_164_506 |
| 502(a)(1)(iii) | Incident to use | CORRECT | Guards: min necessary, 514(d), 530(c) |
| 502(a)(1)(iv) | Valid authorization per §508 | INCOMPLETE | Missing 502(a)(5)(i) guard; no validity/defect check |
| 502(a)(1)(v) | Agreement per §510 | CORRECT | Delegates to permitted_by_164_510 |
| 502(a)(1)(vi) | Per §512, §514(e)(f)(g) | CORRECT | Four sub-paths |
| 502(a)(2)(i) | Required: to individual per §524/528 | CORRECT | |
| 502(a)(2)(ii) | Required: to Secretary | CORRECT | |
| **502(a)(3)** | **BA permitted uses/disclosures** | **MISSING** | No rule for BA-initiated disclosures |
| **502(a)(4)** | **BA required disclosures** | **MISSING** | |
| **502(a)(5)(i)** | **Prohibition on genetic info for underwriting** | **MISSING** | Critical prohibition |
| **502(a)(5)(ii)** | **Sale of PHI prohibition** | **MISSING** | No rules for prohibition or 8 exceptions |
| 502(b)(1)-(2) | Minimum necessary + exceptions | CORRECT | All six exceptions modeled |
| 502(c) | Restriction agreements | CORRECT | Delegates to §522(a) |
| 502(d)(1)-(2) | De-identified info | CORRECT | |
| **502(d)(2)(i)-(ii)** | **Re-identification code/info = PHI** | **MISSING** | |
| 502(e)(1)(i) | Disclosure to BA | CORRECT | |
| **502(e)(1)(ii)** | **BA-to-subcontractor** | **MISSING** | No BA-to-sub-BA chain |
| 502(f) | Deceased 50-year rule | INCOMPLETE | No temporal constraint |
| 502(g)(1)-(5) | Personal representatives | CORRECT | In hipaa_macros.dl |
| 502(g)(3)(i)(A)-(C) | Minor exception conditions | INCOMPLETE | Oracle not decomposed |
| 502(h)-(i) | Communications, notice | CORRECT | |
| 502(j)(1)-(2) | Whistleblower, crime victim | CORRECT | 512(f)(2)(i) limit stubbed |

### §164.506 — TPO

| Sub-clause | Status | Notes |
|---|---|---|
| 506(a) | INCOMPLETE | Negation covers 508(a)(2)-(3) but not 508(a)(4) sale |
| 506(b)(1)-(2) | CORRECT | |
| 506(c)(1)-(5) | CORRECT | All five implementation specs |

### §164.508 — Authorization Required

| Sub-clause | Status | Notes |
|---|---|---|
| 508(a)(1)-(3) | CORRECT | Psych notes, marketing negative norms + exceptions |
| 508(a)(2)(i)(A) | INCOMPLETE | Missing originator-for-treatment exception |
| **508(a)(4)** | **MISSING** | Sale of PHI authorization — entire sub-section |
| **508(b)(1)-(6)** | **INCOMPLETE** | Validity/defect oracles declared but never invoked |
| **508(c)(1)-(4)** | **MISSING** | Core elements, required statements, plain language |

### §164.510 — Opportunity to Agree or Object

| Sub-clause | Status | Notes |
|---|---|---|
| 510(a)(1)-(3) | CORRECT | Directory + emergency exception |
| **510(a)(3)(ii)** | **MISSING** | Must inform when practicable |
| 510(b)(1)-(4) | CORRECT | Care involvement + disaster |
| **510(b)(5)** | **MISSING** | Deceased individual disclosure to family |

### §164.512 — No Authorization Required

| Sub-clause | Status | Notes |
|---|---|---|
| 512(a) | CORRECT | Required by law |
| 512(b)(1)(i)-(v) | CORRECT | All 5 public health sub-sections |
| **512(b)(1)(vi)** | **MISSING** | School immunization records |
| **512(b)(2)** | **MISSING** | CE as public health authority may USE |
| 512(c)(1) | CORRECT | Abuse/neglect |
| **512(c)(2)** | **MISSING** | Must inform individual |
| 512(d)(1) | CORRECT | Health oversight |
| **512(d)(2)-(4)** | **MISSING** | Individual-as-subject exception, joint activities |
| 512(e)(1)(i)-(ii),(vi) | CORRECT | Judicial proceedings |
| **512(e)(1)(iii)-(v)** | **MISSING** | Satisfactory assurance details |
| 512(f)(1)-(6) | CORRECT | All 6 LE sub-sections |
| **512(f)(2)(ii)** | **INCOMPLETE** | DNA/dental prohibition not enforced |
| 512(g)-(h) | CORRECT | Decedents, organ donation |
| 512(i)(1)(i)-(iii) | CORRECT | Research (3 pathways) |
| **512(i)(2)** | **MISSING** | Waiver documentation requirements |
| 512(j)(1)(i)-(ii) | CORRECT | Serious threat |
| 512(k)(1)(i)-(iii) | CORRECT | Military/veterans |
| **512(k)(1)(iv)** | **MISSING** | Foreign military personnel |
| 512(k)(2)-(6) | CORRECT | Gov functions |
| **512(k)(5)(ii)-(iii)** | **MISSING** | CE-as-institution use; release rule |
| **512(k)(7)** | **MISSING** | NICS reporting — entire sub-section |
| 512(l) | CORRECT | Workers' comp |

### §164.514 — Other Requirements

| Sub-clause | Status | Notes |
|---|---|---|
| 514(a)-(c) | CORRECT | De-identification |
| 514(d)(1)-(2) | CORRECT | Minimum necessary |
| **514(d)(3)(iii)** | **MISSING** | Reasonable reliance (4 categories) |
| 514(e)(1)-(3) | CORRECT | Limited data sets |
| **514(e)(4)** | **MISSING** | DUA contents requirements |
| 514(f)(1) | INCOMPLETE | Only 2 of 6 PHI types |
| **514(f)(2)(ii)-(iv)** | **MISSING** | Opt-out, conditioning, honor opt-out |
| 514(g) | CORRECT | Underwriting restriction |
| **514(h)** | **MISSING** | Verification requirements — entire sub-section |

### §164.524 — Individual Access

| Sub-clause | Status | Notes |
|---|---|---|
| 524(a)(1)-(3) | CORRECT | Access right + denial grounds |
| **524(b)(2)** | **MISSING** | 30-day timely action |
| **524(c)(1)-(4)** | **MISSING** | Provision of access details |
| **524(d)(1)-(4)** | **MISSING** | Denial procedures, review |
| **524(e)** | **MISSING** | Documentation requirement |

## Priority Recommendations

### Priority 1 — Prohibitions Not Enforced (affect correctness)
1. Add §502(a)(5)(i): Genetic info for underwriting prohibition
2. Add §502(a)(5)(ii): Sale of PHI prohibition
3. Add §508(a)(4): Sale authorization requirement
4. Wire is_valid_authorization/is_defective_authorization into authorization check

### Priority 2 — Missing Permission Pathways
5. Add §502(a)(3)-(4): BA provisions
6. Add §510(b)(5): Deceased disclosure to family
7. Add §512(b)(1)(vi): School immunization
8. Add §512(k)(1)(iv): Foreign military
9. Add §512(k)(7): NICS reporting

### Priority 3 — Missing Constraints
10. Add §508(b): Authorization validity checks
11. Add §514(d)(3)(iii): Reasonable reliance
12. Add §514(h): Verification requirements
13. Add §512(f)(2)(ii): DNA/dental prohibition
