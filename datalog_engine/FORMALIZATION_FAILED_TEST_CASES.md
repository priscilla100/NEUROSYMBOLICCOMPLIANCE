# Formalization Failed Test Cases

**Date**: 2026-04-13
**Scope**: §164.502 and §164.506

These are test cases where the Soufflé Datalog formalization produced an
incorrect result, indicating a bug in the formalization that needed fixing.

---

## Results

**No formalization bugs found in the 30-test-case run.**

All 20 expected-ALLOW cases were correctly allowed with the proper HIPAA
section cited in the explanation tree. All 10 expected-DENY cases were
correctly denied.

## Scope Limitations (Not Bugs)

The following test cases produced DENY due to unformalized stubs, not bugs:

- **TC29** (Hospital → Researcher for research): Would potentially be allowed
  under §164.512(i) with IRB waiver. §164.512 is a stub.
- **TC30** (Hospital → Law enforcement): Would potentially be allowed under
  §164.512(f) with court order. §164.512 is a stub.

These should be retested when §164.512 is formalized.

## PDF Cross-Reference Notes

The formalization of §164.502 and §164.506 (PDF pages 28-55) was previously
verified by a dedicated verification agent. Six issues were found and fixed:

1. §502(a)(2)(i): Missing `is_reply_to_request` oracle — fixed
2. §502(a)(2)(ii): Missing `secretary_investigation_authorized` oracle — fixed
3. §502(e)(1)(i): Missing `is_for_ba_purpose` check — fixed
4. §506(c)(4): Missing `pertains_to` joins — fixed
5. §502(i): Missing from top-level OR — fixed
6. §502(d)(2): False positive (was actually correct)

No additional mismatches found in this testing round.

---

## GoldCoin Dataset Testing (2026-04-13)

**Scope**: Full formalization (502, 506, 508, 510, 512, 514, 524)
**Dataset**: HKUST-KnowComp/GoldCoin (EMNLP 2024) — 25 real HIPAA court cases

**No formalization bugs found.** All 25 GoldCoin test cases produced correct
results (19 Permit correctly allowed, 6 Forbid correctly denied).

Previously stubbed sections (512, 514) that blocked TC29/TC30 are now fully
formalized and correctly handle the GoldCoin cases involving those sections.
