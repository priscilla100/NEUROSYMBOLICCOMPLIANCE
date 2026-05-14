# Claude Failed Test Cases (Adjudication Errors)

**Date**: 2026-04-13
**Scope**: §164.502 and §164.506

These are test cases where Claude's independent HIPAA adjudication was wrong
(i.e., the formalization was correct but Claude's analysis was incorrect).

---

## Results

**No adjudication errors found.** All 30 test cases matched the expected
HIPAA analysis against the Datalog formalization output.

---

## GoldCoin Dataset Testing (2026-04-13)

**Scope**: Full formalization (502, 506, 508, 510, 512, 514, 524)
**Dataset**: HKUST-KnowComp/GoldCoin (EMNLP 2024) — 25 real HIPAA court cases

**No adjudication errors found.** All 25 GoldCoin test cases matched the
expected HIPAA analysis (25/25 = 100% match rate).
