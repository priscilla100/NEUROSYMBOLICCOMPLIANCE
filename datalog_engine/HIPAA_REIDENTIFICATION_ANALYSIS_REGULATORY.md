# HIPAA Regulatory Analysis: Re-Identification of Research Subject from Published Medical Images

## Scenario Summary

A medical research study publishes medical images (CT scans) in academic papers. The authors attempted de-identification by obscuring facial features, but the method was ineffective -- a different researcher later re-identified the patient's face using 3D facial reconstruction from volumetric CT data. The patient had given authorization/consent for the study, which had IRB approval.

---

## A. Does the Attempted (But Ineffective) De-Identification Change the HIPAA Analysis?

### A.1. Expert Determination Under Section 164.514(b)(1)

Section 164.514(b)(1) provides that a covered entity may determine health information is not individually identifiable only if:

> "A person with appropriate knowledge of and experience with generally accepted statistical and scientific principles and methods for rendering information not individually identifiable: (i) Applying such principles and methods, determines that the risk is very small that the information could be used, alone or in combination with other reasonably available information, by an anticipated recipient to identify an individual who is a subject of the information; and (ii) Documents the methods and results of the analysis that justify such determination."

**Critical analysis:** The statute uses a prospective, reasonable-judgment standard. The expert must determine that the risk is "very small" at the time of the determination, based on "generally accepted statistical and scientific principles." The key question is whether this is judged:

- **(a) Ex ante (at the time of determination):** If the expert used methods consistent with generally accepted principles and reasonably concluded the risk was very small, the de-identification may have been valid at the time, even if later technological advances enabled re-identification.

- **(b) Ex post (based on actual outcomes):** If the information was in fact re-identified, one could argue the determination was wrong -- the risk was not actually "very small."

**Regulatory interpretation:** The weight of regulatory guidance favors an **ex ante reasonableness standard**, but with important caveats:

1. The expert must have "appropriate knowledge of and experience with generally accepted statistical and scientific principles." If 3D facial reconstruction from volumetric CT data was a known capability at the time of publication (which it has been since at least the mid-2010s), then a competent expert *should have known* this risk existed. The expert determination would be **invalid** if the expert failed to account for reasonably foreseeable re-identification techniques.

2. The requirement to document "methods and results of the analysis" (Section 164.514(b)(1)(ii)) means the expert's reasoning is subject to scrutiny. If the documentation does not address volumetric facial reconstruction as a risk vector, this is a significant gap.

3. The phrase "reasonably available information" and "anticipated recipient" are key. Published academic images are available to the entire research community. The "anticipated recipient" is any researcher worldwide. 3D reconstruction capabilities are well-documented in the computer vision and medical imaging literature.

**Conclusion on Expert Determination:** If an expert certified de-identification of volumetric CT data without addressing 3D facial reconstruction risks, the expert determination was likely **deficient at the time it was made**, not merely wrong in hindsight. The de-identification would therefore not satisfy Section 164.514(b)(1), and the published images would remain PHI.

### A.2. Safe Harbor Under Section 164.514(b)(2)

Section 164.514(b)(2) requires removal of 18 specific identifiers. The relevant identifier is:

> Section 164.514(b)(2)(i)(Q): "Full face photographic images and any comparable images"

**Analysis of "removal":** The Safe Harbor method requires that identifiers be **removed**, not merely obscured. The critical questions are:

1. **Does "full face photographic images and any comparable images" encompass 3D facial geometry embedded in volumetric CT data?** The regulation says "full face photographic images **and any comparable images**." A volumetric CT scan from which a face can be reconstructed is arguably a "comparable image" -- it contains sufficient data to generate a full face image. The phrase "any comparable images" is deliberately broad.

2. **Does attempted-but-reversible removal count as "removal"?** No. The Safe Harbor method is binary: the identifier is either removed or it is not. If the facial geometry data remains in the volumetric CT scan and can be extracted to reconstruct a face, then the "full face photographic image" (or comparable image) has **not been removed** -- it has merely been superficially obscured while the underlying data persists.

3. **The "actual knowledge" clause:** Section 164.514(b)(2)(ii) adds: "The covered entity does not have actual knowledge that the information could be used alone or in combination with other information to identify an individual who is a subject of the information." Even if one argued the facial features were "removed" from the visible slices, if the covered entity knew (or should have known, given published literature) that 3D reconstruction was possible, this clause would defeat the Safe Harbor claim.

**Conclusion on Safe Harbor:** Superficial defacing of CT image slices while retaining the underlying volumetric data from which a face can be reconstructed does **not** satisfy Safe Harbor removal of the identifier under Section 164.514(b)(2)(i)(Q). The images remain PHI.

### A.3. Temporal Standard: Reasonable at the Time vs. Actually Effective

The regulatory text does not contain an explicit temporal safe harbor (i.e., "if it was reasonable at the time, you are protected even if later technology defeats it"). However:

- For **Expert Determination**, the standard is what a qualified expert determines using "generally accepted" methods. This is inherently time-bound -- but the expert must account for foreseeable risks. If facial reconstruction from CT data was a known technique, the determination was unreasonable even at the time.

- For **Safe Harbor**, there is no temporal element. The identifiers must be removed. Period. If they were not actually removed, the method fails regardless of good intentions.

**Bottom line:** The distinction between "reasonable at the time" and "actually effective" matters primarily for penalty assessment (see Section E below), not for whether the de-identification was valid. Invalid de-identification means the data was PHI when published.

---

## B. The Role of Section 164.512(i) -- Research

### B.1. IRB Waiver of Authorization

Section 164.512(i)(1)(i) permits use or disclosure of PHI for research without individual authorization if an IRB (or privacy board) approves a waiver. The IRB must document that specific criteria are met (Section 164.512(i)(2)).

However, in this scenario, the patient **gave authorization/consent** for the research study. This means the study likely proceeded under Section 164.508 (valid authorization) rather than Section 164.512(i) (waiver of authorization). These are different legal pathways:

- **Section 164.508 authorization route:** The patient signed an authorization for the use/disclosure of PHI for the research. The authorization must describe "the information to be used or disclosed" in a "specific and meaningful fashion" (Section 164.508(c)(1)(i)). If the authorization covered disclosure of medical images in publications, the disclosure was authorized. But the authorization likely described disclosure of *de-identified* images, not identifiable ones. If the de-identification failed, the actual disclosure exceeded the scope of the authorization.

- **Section 164.512(i) waiver route (alternative scenario):** If the IRB granted a waiver of individual authorization, Section 164.512(i)(2)(ii)(A) requires the IRB to determine that the use involves "no more than a minimal risk to the privacy of individuals," based on:
  > "(1) An adequate plan to protect the identifiers from improper use and disclosure; (2) An adequate plan to destroy the identifiers at the earliest opportunity consistent with conduct of the research, unless there is a health or research justification for retaining the identifiers or such retention is otherwise required by law; and (3) Adequate written assurances that the protected health information will not be reused or disclosed to any other person or entity..."

### B.2. Was the Plan "Adequate" Under Section 164.512(i)(2)(ii)(A)?

Even if the study proceeded under an IRB waiver, the plan to protect identifiers must be "adequate." Publishing CT images with ineffective de-identification -- particularly when 3D facial reconstruction is a known risk -- means:

- **Section 164.512(i)(2)(ii)(A)(1):** The plan to protect identifiers from "improper use and disclosure" was **not adequate**. The identifiers (facial geometry) were disclosed publicly, which is the opposite of protection.

- **Section 164.512(i)(2)(ii)(A)(2):** There was no adequate plan to "destroy the identifiers at the earliest opportunity." The identifiers were published in a permanent academic record.

**Conclusion:** Whether the study operated under Section 164.508 authorization or Section 164.512(i) waiver, the inadequate de-identification creates a HIPAA problem:
- Under 164.508: the disclosure exceeded the scope of the authorization (the patient authorized disclosure of de-identified images, not identifiable ones).
- Under 164.512(i): the IRB's finding of "adequate" protection was objectively incorrect, undermining the waiver.

### B.3. Does IRB Approval Insulate the Covered Entity?

No. IRB approval of a research protocol does not create a HIPAA safe harbor. The covered entity remains independently responsible for complying with the Privacy Rule. The IRB's role under HIPAA (Section 164.512(i)) is to make specific findings that the covered entity may rely upon, but if those findings are objectively wrong (the plan was not adequate, the risk was not minimal), the covered entity's reliance may be challenged. The covered entity has an independent obligation under Section 164.502(a) not to disclose PHI except as permitted.

---

## C. Application of Section 164.502(d)(2) -- De-Identified Information and Re-Identification

### C.1. The De-Identification Gateway

Section 164.502(d)(2) states:

> "Health information that meets the standard and implementation specifications for de-identification under Section 164.514(a) and (b) is considered not to be individually identifiable health information, i.e., de-identified. The requirements of this subpart do not apply to information that has been de-identified in accordance with the applicable requirements of Section 164.514..."

**Critical threshold question:** Did the information **ever** meet the de-identification standard? As analyzed in Section A above, the answer is likely **no** -- the de-identification was invalid because the facial identifier was not actually removed (Safe Harbor) or the expert determination was deficient. If the information never qualified as de-identified, then Section 164.502(d)(2) never applied, and the information was PHI from the moment of publication. HIPAA applied all along.

### C.2. If De-Identification Was Arguably Valid

Even assuming arguendo that the de-identification was valid at the time:

Section 164.502(d)(2)(ii) states:

> "If de-identified information is re-identified, a covered entity may use or disclose such re-identified information only as permitted or required by this subpart."

This provision contemplates that de-identified information can become re-identified, at which point it reverts to PHI status for the covered entity. The re-identification by another researcher demonstrates that the information is re-identifiable. Once re-identified, the covered entity can only use/disclose the re-identified information as permitted by the Privacy Rule.

However, note the limitation: Section 164.502(d)(2)(ii) applies to "a covered entity." It governs what the covered entity does with re-identified information -- it does not retroactively make the original publication a violation if the de-identification was valid at the time.

### C.3. Section 164.502(d)(2)(i) -- Disclosure of Re-Identification Codes

Section 164.502(d)(2)(i) states:

> "Disclosure of a code or other means of record identification designed to enable coded or otherwise de-identified information to be re-identified constitutes disclosure of protected health information."

This provision addresses **intentional** re-identification mechanisms (codes, keys). In this scenario, the re-identification was not through a disclosed code but through inherent data properties (facial geometry in volumetric data). This clause is not directly triggered, but it illustrates the principle that anything enabling re-identification is treated as PHI.

### C.4. Practical Implication

The most likely regulatory interpretation is that the de-identification was **never valid** (the facial identifier was not removed), meaning the published images were PHI from day one. Section 164.502(d)(2) provides a backstop but is probably not the primary analytical pathway.

---

## D. The Researcher Who Performed the Re-Identification

### D.1. Is the Re-Identifying Researcher Subject to HIPAA?

HIPAA applies to **covered entities** (health plans, health care clearinghouses, and health care providers who transmit health information electronically) and their **business associates**. See 45 CFR Section 160.103.

The re-identifying researcher is subject to HIPAA **only if**:
- They are employed by or affiliated with a covered entity (e.g., an academic medical center), OR
- They are a business associate of a covered entity.

If the re-identifying researcher is:
- An independent academic researcher at a university that is not a covered entity: **HIPAA does not apply** to them directly. However, if they are at a university with a health system component that is a covered entity and they receive data through that entity, HIPAA may apply through the institution's hybrid entity designation.
- A researcher at an academic medical center (which is a covered entity): HIPAA applies, and their use of PHI must be authorized or fall within a permitted exception.

### D.2. Section 164.514(c) -- Re-Identification Controls

Section 164.514(c) permits a covered entity to assign a code for re-identification, provided:

> "(1) Derivation. The code or other means of record identification is not derived from or related to information about the individual and is not otherwise capable of being translated so as to identify the individual; and (2) Security. The covered entity does not use or disclose the code or other means of record identification for any other purpose, and does not disclose the mechanism for re-identification."

This section governs **intentional re-identification mechanisms** maintained by the covered entity. It does not directly address a third party who re-identifies data through independent technical means. However:

- If the original covered entity retained a re-identification key and that key was somehow disclosed or discoverable, Section 164.514(c)(2) would be violated.
- The re-identifying researcher's actions fall outside Section 164.514(c) unless they obtained a re-identification code from the covered entity.

### D.3. Other Legal Frameworks for the Re-Identifying Researcher

Even if HIPAA does not directly apply to the re-identifying researcher, other legal and ethical frameworks may:
- **Common Rule (45 CFR Part 46):** If the re-identification constitutes human subjects research, IRB approval would be required.
- **State privacy laws:** Many states have independent health privacy statutes.
- **Institutional policies:** Most research institutions have policies governing the handling of identifiable health information.
- **Data use agreements:** If the re-identifying researcher obtained the images under a data use agreement (Section 164.514(e)(4)(ii)(C)(5)), that agreement likely prohibits re-identification: "Not identify the information or contact the individuals."

---

## E. Penalty Tier Analysis

### E.1. HIPAA Penalty Framework

The HITECH Act (codified at 42 U.S.C. Section 1320d-5) establishes four penalty tiers for HIPAA violations:

| Tier | Mental State | Minimum Penalty per Violation | Maximum Penalty per Violation | Annual Cap |
|------|-------------|-------------------------------|-------------------------------|------------|
| 1 | Did not know (and by exercising reasonable diligence would not have known) | $137 | $68,928 | $2,067,813 |
| 2 | Reasonable cause (not willful neglect) | $1,379 | $68,928 | $2,067,813 |
| 3 | Willful neglect, corrected within 30 days | $13,785 | $68,928 | $2,067,813 |
| 4 | Willful neglect, not timely corrected | $68,928 | $2,067,813 | $2,067,813 |

*(Penalty amounts adjusted for inflation; exact amounts vary by year.)*

### E.2. Application to This Scenario

**Tier 1 -- "Did not know and by exercising reasonable diligence would not have known":**

This tier applies only if the covered entity could not have known, even with reasonable diligence, that the de-identification was ineffective. This is a **high bar** in this scenario because:
- 3D facial reconstruction from CT data is well-documented in published literature.
- A reasonably diligent covered entity publishing CT images should be aware of this risk.
- The "reasonable diligence" standard likely requires consulting with imaging experts familiar with re-identification risks.

**Tier 1 is unlikely to apply** unless the specific re-identification technique was truly novel and unforeseeable at the time of publication.

**Tier 2 -- "Reasonable cause, not willful neglect":**

This is the most likely tier. "Reasonable cause" means the covered entity had reason to know of the violation but did not act with willful neglect. In this scenario:
- The authors attempted de-identification (showing good faith).
- The IRB reviewed and approved the protocol (showing institutional process).
- But the de-identification method was inadequate for the type of data involved.
- The covered entity *should have known* that superficial defacing of volumetric CT data was insufficient, but this failure represents a **knowledge gap or negligence**, not willful disregard.

**Tier 2 is the most probable classification.**

**Tier 3/4 -- "Willful neglect":**

These tiers would apply if the covered entity knew the de-identification was inadequate and proceeded anyway, or if it had been warned about the risk and ignored the warning. Absent evidence of such knowledge or warnings, willful neglect is unlikely.

### E.3. Effect of IRB Approval on Penalty Analysis

IRB approval is a **mitigating factor** but not a defense:
- It demonstrates that the covered entity submitted its protocol for independent review (evidence of good faith and institutional compliance efforts).
- However, IRB approval does not shift HIPAA liability. The covered entity remains the responsible party.
- If the IRB itself was negligent in evaluating de-identification adequacy, this may affect the IRB's institution separately.
- OCR (the enforcement agency) may consider IRB approval as evidence that the violation was not willful neglect, supporting a Tier 2 classification.

### E.4. Breach Notification

Under the Breach Notification Rule (45 CFR Sections 164.400-414), if the published images constitute unsecured PHI and the incident affects 500 or more individuals, the covered entity must:
- Notify affected individuals without unreasonable delay (no later than 60 days from discovery).
- Notify HHS.
- Notify prominent media outlets if 500+ individuals in a state are affected.

Even for a single individual, individual notification is required. The publication of identifiable medical images in an academic paper is a **reportable breach** unless the covered entity can demonstrate through a risk assessment that there is a low probability the PHI was compromised -- which is difficult when the images are publicly available and someone has already demonstrated re-identification.

---

## F. Allocation of Responsibility

### F.1. The Authors (Researchers)

**Primary responsibility for the de-identification failure.** The authors selected and applied the de-identification method. As researchers handling PHI, they are either:
- Workforce members of the covered entity, in which case their actions are attributed to the covered entity under HIPAA.
- Operating under a business associate agreement, in which case they have independent HIPAA obligations.

The authors had a duty to use de-identification methods appropriate to the data type. Applying 2D facial defacing to 3D volumetric data reflects a failure to understand the re-identification risks inherent in the data they were publishing.

### F.2. The IRB

**Secondary responsibility.** The IRB's role is to evaluate whether the research protocol adequately protects human subjects, including their privacy. Under Section 164.512(i)(2)(ii)(A), if a waiver was granted, the IRB was required to find "an adequate plan to protect the identifiers from improper use and disclosure." If the IRB approved a protocol with inadequate de-identification:
- The IRB failed in its evaluative function.
- However, the IRB is not a covered entity and is not directly subject to HIPAA enforcement (it is part of the institutional infrastructure).
- The IRB's failure may expose the institution to liability under the Common Rule and institutional policies.

### F.3. The Institution / Covered Entity

**Bears ultimate HIPAA liability.** Under HIPAA, the covered entity is responsible for the actions of its workforce (Section 164.530(c) requires training; Section 164.530(b) requires sanctions for violations). The institution:
- Failed to implement adequate de-identification protocols for medical imaging data.
- Failed to train researchers on the specific risks of volumetric imaging data.
- Failed to have policies requiring expert review of de-identification methods for complex data types.
- Is the entity that will face OCR enforcement, penalties, and breach notification obligations.

### F.4. The Publisher (Journal)

**Generally not subject to HIPAA.** Academic publishers are typically not covered entities or business associates. They do not provide healthcare, process claims, or handle PHI in a HIPAA-regulated capacity. However:
- Some journals have their own policies requiring confirmation of de-identification or IRB approval.
- A journal's failure to catch identifiable images is an editorial failure, not a HIPAA violation.
- If a journal becomes aware that published images contain identifiable PHI, ethical obligations (and potentially contractual ones) may require retraction or remediation.

### F.5. The Re-Identifying Researcher

**Generally the least culpable under HIPAA, but potentially culpable under other frameworks.**

- If the re-identifying researcher is not affiliated with a covered entity, HIPAA does not apply to them.
- If they are affiliated with a covered entity, their re-identification activity may itself require IRB approval and must comply with HIPAA's research provisions.
- The re-identifying researcher may have acted in furtherance of legitimate research (e.g., demonstrating privacy vulnerabilities in medical imaging -- a recognized research area).
- If they obtained the published images under a data use agreement that prohibited re-identification (Section 164.514(e)(4)(ii)(C)(5)), they would be in violation of that agreement.
- Under the Common Rule, if the re-identification constitutes human subjects research, IRB approval is required.

### F.6. Responsibility Hierarchy (Summary)

1. **Covered Entity / Institution** -- bears ultimate HIPAA liability; responsible for policies, training, and oversight.
2. **Authors / Researchers** -- directly caused the de-identification failure; liable as workforce members or business associates.
3. **IRB** -- failed in evaluative function; institutional (not direct HIPAA) liability.
4. **Publisher** -- generally outside HIPAA jurisdiction; editorial/ethical responsibility only.
5. **Re-Identifying Researcher** -- HIPAA liability depends on covered entity status; potential liability under data use agreements, Common Rule, and institutional policies.

---

## G. Synthesis and Key Regulatory Conclusions

### G.1. The De-Identification Was Likely Invalid

Under either the Expert Determination (Section 164.514(b)(1)) or Safe Harbor (Section 164.514(b)(2)) method, the de-identification of volumetric CT data by superficial facial defacing is almost certainly invalid:
- Safe Harbor requires **removal** of "full face photographic images and any comparable images" -- facial geometry embedded in volumetric data is a "comparable image" that was not removed.
- Expert Determination requires that the risk be "very small" considering "reasonably available information" and "anticipated recipients" -- the risk of 3D facial reconstruction from published CT data is well-documented and foreseeable.

### G.2. The Published Images Were PHI

Because the de-identification was invalid, the published images constituted PHI. Their publication was a disclosure of PHI that must be justified under the Privacy Rule.

### G.3. The Disclosure May or May Not Have Been Authorized

If the patient's authorization (Section 164.508) specifically covered publication of medical images, and if the authorization's description of the information was broad enough to encompass images from which the patient could be identified, then the disclosure was authorized -- even though the authors believed it was de-identified. However, most research authorizations describe the disclosure of de-identified or anonymized data in publications, which would not cover identifiable images.

### G.4. This Is a Reportable Breach

The publication of identifiable PHI in an academic journal constitutes a breach under the Breach Notification Rule. The covered entity must conduct a risk assessment and, in most cases, notify the affected individual, HHS, and (if applicable) the media.

### G.5. The Likely Penalty Tier Is Tier 2

The covered entity's good faith effort at de-identification and IRB oversight, combined with the failure to recognize a foreseeable risk, places this in Tier 2 ("reasonable cause, not willful neglect"). OCR would consider the totality of circumstances, including institutional compliance programs, training, and response to the breach.

---

## H. Regulatory Citations Index

| Section | Topic | Relevance |
|---------|-------|-----------|
| 164.502(a) | General prohibition on PHI disclosure | Foundation: PHI may not be disclosed except as permitted |
| 164.502(d)(1) | Creating de-identified information | Permits use of PHI to create de-identified data |
| 164.502(d)(2) | De-identified information standard | De-identified data is not PHI; re-identified data reverts to PHI |
| 164.502(d)(2)(i) | Re-identification codes as PHI | Disclosure of re-identification means = PHI disclosure |
| 164.502(d)(2)(ii) | Re-identified information | Once re-identified, data is PHI again |
| 164.508 | Authorization requirements | Patient authorization for research use/disclosure |
| 164.508(b)(4)(i) | Conditioning treatment on authorization | Permitted for research-related treatment |
| 164.508(c)(1)(i) | Description of information | Authorization must specifically describe PHI |
| 164.512(i)(1) | Research without authorization | Permits PHI use for research with IRB waiver |
| 164.512(i)(2)(ii)(A) | Waiver criteria | Requires adequate plan to protect identifiers |
| 164.512(i)(2)(ii)(A)(1) | Adequate protection plan | Plan must protect identifiers from improper use/disclosure |
| 164.512(i)(2)(ii)(A)(2) | Identifier destruction | Plan must destroy identifiers at earliest opportunity |
| 164.514(a) | De-identification standard | Information not individually identifiable = not PHI |
| 164.514(b)(1) | Expert Determination method | Expert certifies "very small" re-identification risk |
| 164.514(b)(1)(ii) | Documentation requirement | Expert must document methods and results |
| 164.514(b)(2) | Safe Harbor method | 18 identifiers must be removed |
| 164.514(b)(2)(i)(Q) | Full face images | "Full face photographic images and any comparable images" |
| 164.514(b)(2)(ii) | Actual knowledge | CE must not have actual knowledge of identifiability |
| 164.514(c) | Re-identification controls | Rules for codes/keys enabling re-identification |
| 164.514(c)(2) | Security of re-identification means | CE must not disclose mechanism for re-identification |
| 42 U.S.C. 1320d-5 | Civil penalties | HITECH penalty tiers |
| 45 CFR 164.400-414 | Breach Notification Rule | Notification requirements for PHI breaches |

---

*Analysis prepared for the ComplianceGPT / HIPAA Formalization research project. Based on regulatory text of 45 CFR Parts 160 and 164 (HIPAA Privacy Rule) as codified in the eCFR. This analysis is for academic research purposes and does not constitute legal advice.*
