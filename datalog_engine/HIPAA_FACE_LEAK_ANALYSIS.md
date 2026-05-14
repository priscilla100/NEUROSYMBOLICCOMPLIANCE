# HIPAA Analysis: Inadvertent Patient Face Leaks in Published Medical Research Images

**Date:** April 14, 2026
**Disclaimer:** This analysis is for academic research purposes and does not constitute legal advice. Consult qualified legal counsel for specific compliance determinations.

---

## Scenario Summary

Medical research papers are published containing patient medical images (CT scans, X-rays, dermatology photos). Patients consented to publication ONLY on the condition that their faces are NOT visible. However, published images inadvertently reveal patient faces (e.g., 3D facial reconstructions from CT scan data, insufficiently anonymized photographs). Three parties are involved: patients, authors (researchers at hospitals/universities), and publishers (academic journals).

---

## Question 1: Does the Face Leak Constitute an Unintentional HIPAA Violation?

### 1A. Are Patient Photos with Visible Faces PHI?

**Yes, unambiguously.**

Under HIPAA, protected health information (PHI) is "individually identifiable health information" held or transmitted by a covered entity or its business associate. The de-identification standard at **42 CFR 164.514(b)(2)(i)(Q)** explicitly lists as an identifier that must be removed:

> *"Full face photographic images and any comparable images"*

This provision exists in both contexts:
- **Section 164.514(b)(2)(i)(Q)** -- the Safe Harbor de-identification method requires removal of "full face photographic images and any comparable images" as one of the 18 identifier types.
- **Section 164.514(e)(2)(xvi)** -- even the less restrictive "limited data set" standard excludes "full face photographic images and any comparable images."

A medical image that reveals a patient's face -- whether directly (a photograph) or indirectly (a 3D reconstruction from CT volumetric data) -- constitutes an identifier under both provisions. When combined with health information (the medical condition being studied, the treatment context, the diagnosis), this creates PHI. The regulation uses the phrase "any comparable images," which is broad enough to encompass 3D facial reconstructions derived from medical imaging data.

Furthermore, under the Expert Determination method at **Section 164.514(b)(1)**, a qualified expert would need to determine that the "risk is very small" that the information could identify an individual. A visible face -- the single most recognizable human biometric feature -- would almost certainly fail this test.

**Conclusion:** A medical image with a visible patient face is PHI. It is individually identifiable health information because the face is an identifier, and it is linked to health information (the medical context of the image).

### 1B. Does the Face Leak Violate the Patient's Authorization?

**Yes.**

Under **42 CFR 164.508(a)(1)**, the general rule states:

> *"When a covered entity obtains or receives a valid authorization for its use or disclosure of protected health information, such use or disclosure must be consistent with such authorization."*

The patients authorized publication of their images **subject to the condition** that their faces not be visible. This is a conditional authorization -- the scope of permitted disclosure is limited to de-identified or face-obscured versions of the images.

Key points from Section 164.508:

1. **Section 164.508(c)(1)(i)** requires that a valid authorization contain "a description of the information to be used or disclosed that identifies the information in a specific and meaningful fashion." If the authorization specified that images would have faces obscured, then the scope of the authorization is limited to face-obscured images.

2. **Section 164.508(c)(1)(iv)** requires "a description of each purpose of the requested use or disclosure." Publication for research with faces obscured is a different purpose/scope than publication with faces visible.

3. The disclosure of images with visible faces exceeds the scope of the authorization. Under Section 164.508(a)(1), the use or disclosure "must be consistent with such authorization." Publishing images where faces are visible when the authorization was conditioned on faces being hidden is **inconsistent** with the authorization.

**Conclusion:** The disclosure of face-revealing images violates the terms of the authorization under Section 164.508(a)(1). The covered entity made a disclosure that was not "consistent with" the authorization it received.

### 1C. Section 164.502(a)(5)(ii) -- Is This a "Sale" of PHI?

**Potentially yes, depending on remuneration flows.**

**Section 164.502(a)(5)(ii)(B)(1)** defines sale of PHI as:

> *"a disclosure of protected health information by a covered entity or business associate, if applicable, where the covered entity or business associate directly or indirectly receives remuneration from or on behalf of the recipient of the protected health information in exchange for the protected health information."*

Analysis of the scenario:

- If the **authors/institution receive payment** from the publisher (e.g., consulting fees, grants tied to publication, or if the publisher pays for content), this could constitute a sale of PHI.
- If the **publisher profits** from the publication (subscription fees, article processing charges paid by authors, advertising revenue), the question is whether the covered entity "directly or indirectly receives remuneration... in exchange for the protected health information."

However, **Section 164.502(a)(5)(ii)(B)(2)(ii)** provides an exception:

> Sale of PHI does not include disclosure *"for research purposes pursuant to Section 164.512(i) or Section 164.514(e), where the only remuneration received by the covered entity or business associate is a reasonable cost-based fee to cover the cost to prepare and transmit the protected health information for such purposes."*

In typical academic publishing:
- Authors often PAY the publisher (article processing charges), not the reverse.
- If the covered entity receives no remuneration from the publisher for the PHI itself, the "sale" provision likely does not apply.
- If the institution receives grant funding that indirectly flows from the publication, this is likely too attenuated to constitute "remuneration... in exchange for the protected health information."

**Conclusion:** In a typical academic publishing scenario where authors pay article processing charges and receive no direct payment for the PHI, this is unlikely to constitute a "sale" under Section 164.502(a)(5)(ii). However, if there are unusual remuneration arrangements, this provision could be triggered, which would require a specific authorization under Section 164.508(a)(4) that states "the disclosure will result in remuneration to the covered entity."

### 1D. Section 164.514(a)-(b) -- De-identification Standards

**The data is NOT de-identified.**

**Section 164.514(a)** provides:

> *"Health information that does not identify an individual and with respect to which there is no reasonable basis to believe that the information can be used to identify an individual is not individually identifiable health information."*

Under the **Safe Harbor method** at **Section 164.514(b)(2)**, de-identification requires the removal of 18 types of identifiers. Item (Q) is:

> *"Full face photographic images and any comparable images"*

Additionally, **Section 164.514(b)(2)(ii)** requires:

> *"The covered entity does not have actual knowledge that the information could be used alone or in combination with other information to identify an individual who is a subject of the information."*

A published image from which a patient's face can be discerned or reconstructed fails de-identification on multiple grounds:

1. The "full face photographic images and any comparable images" identifier (Q) has not been removed.
2. The covered entity should have known (or had reason to know) that facial features in CT data or insufficiently cropped photographs could identify the patient.
3. Under the Expert Determination method at Section 164.514(b)(1), no qualified expert could certify that the "risk is very small" when a full face is visible.

**Conclusion:** Images with visible patient faces are definitively NOT de-identified under either the Safe Harbor or Expert Determination methods of Section 164.514(b). They remain PHI subject to the full HIPAA Privacy Rule.

### 1E. Does "Accidental" or "Unintentional" Matter?

**Yes, but it does not eliminate liability -- it affects the penalty tier.**

HIPAA's enforcement framework under **42 USC 1320d-5** (civil penalties) and **42 USC 1320d-6** (criminal penalties) establishes tiered penalties based on the level of culpability:

**Civil Penalty Tiers (per 42 USC 1320d-5, as amended by HITECH Act):**

| Tier | Culpability Level | Penalty Per Violation | Annual Maximum |
|------|------------------|----------------------|----------------|
| 1 | Did not know and, by exercising reasonable diligence, would not have known | $137 - $68,928 | $2,067,813 |
| 2 | Reasonable cause (not willful neglect) | $1,379 - $68,928 | $2,067,813 |
| 3 | Willful neglect, corrected within 30 days | $13,785 - $68,928 | $2,067,813 |
| 4 | Willful neglect, not timely corrected | $68,928 - $2,067,813 | $2,067,813 |

*(Note: penalty amounts are periodically adjusted for inflation; the above are approximate current figures.)*

For the face leak scenario:

- **Tier 1** would apply if the researchers genuinely did not know that CT scans could be used to reconstruct faces, and a reasonably diligent person would not have known either. This is increasingly difficult to argue, as the facial reconstruction risk from CT data has been well-documented in radiology and computer science literature since at least 2009.
- **Tier 2 (reasonable cause)** is the most likely classification: the researchers should have known about the risk but did not act with willful neglect. They attempted to comply (the patients gave conditional authorization, the images were intended to be de-identified) but failed in execution.
- **Tier 3 or 4** would apply if the researchers knew about the risk and consciously disregarded it.

**Criminal penalties** under 42 USC 1320d-6 require that the violation be committed "knowingly," with escalating penalties for violations done under false pretenses or with intent to sell/use PHI for personal gain. Accidental face leaks would generally not trigger criminal liability.

**Key point:** Under HIPAA, "I didn't mean to" does not excuse the violation. Even Tier 1 (no knowledge) carries penalties. The accidental nature reduces severity but does not eliminate the violation itself. The obligation exists regardless of intent: a covered entity must ensure PHI is properly de-identified before disclosure.

### 1F. Breach Notification Requirements

**This constitutes a breach requiring notification.**

Under the HITECH Act's Breach Notification Rule (**42 CFR 164.400-414**):

- A **breach** is defined as the acquisition, access, use, or disclosure of PHI in a manner not permitted by the Privacy Rule that compromises the security or privacy of the PHI (42 CFR 164.402).
- Publication of patient images with identifiable faces in a research paper is an **impermissible disclosure** of PHI (it exceeds the scope of the authorization and the images are not de-identified).
- The disclosure is to the general public (a published paper), making it an especially serious breach.

**Required notifications include:**

1. **Individual notification** (42 CFR 164.404): The covered entity must notify each affected individual "without unreasonable delay and in no case later than 60 calendar days from the discovery of the breach."

2. **HHS Secretary notification** (42 CFR 164.408): If the breach affects 500 or more individuals, notification to the Secretary must be made without unreasonable delay. For fewer than 500 individuals, notification may be made annually.

3. **Media notification** (42 CFR 164.406): If the breach affects more than 500 residents of a single state or jurisdiction, the covered entity must notify prominent media outlets.

4. **Business associate obligations** (42 CFR 164.410): If a business associate discovers the breach, it must notify the covered entity.

Additionally, **Section 164.530(c)** requires covered entities to have safeguards to protect PHI privacy. Failure to implement adequate image de-identification procedures could itself be an independent violation of the safeguards requirement.

**Conclusion:** The face leak is a reportable breach. The covered entity must conduct a risk assessment, notify affected patients, and report to HHS OCR. Given that published papers are publicly accessible, the breach is particularly serious because the PHI has been disseminated widely and cannot easily be "un-published."

---

## Question 2: Is It Necessary for All Three Parties to Be US-Based?

### 2A. Who HIPAA Applies To

**HIPAA applies to covered entities and their business associates, regardless of the nationality of the patient or the location of the recipient.**

HIPAA's jurisdictional reach is entity-based, not geography-based in the traditional sense:

**Covered Entities** are:
1. **Health care providers** who transmit health information electronically in connection with covered transactions (hospitals, physician practices, etc.)
2. **Health plans** (health insurers, HMOs, employer-sponsored health plans, government programs like Medicare/Medicaid)
3. **Health care clearinghouses**

**Business Associates** are persons or entities that perform functions or activities on behalf of, or provide services to, a covered entity that involve the use or disclosure of PHI (42 CFR 160.103).

### 2B. Are Academic Publishers "Business Associates"?

**It depends on the arrangement, but in many cases YES.**

A business associate is any entity that "creates, receives, maintains, or transmits protected health information on behalf of" a covered entity (42 CFR 160.103). Under **Section 164.502(e)(1)(i)**:

> *"A covered entity may disclose protected health information to a business associate and may allow a business associate to create, receive, maintain, or transmit protected health information on its behalf, if the covered entity obtains satisfactory assurance that the business associate will appropriately safeguard the information."*

If a publisher receives patient images from a covered entity (the hospital/university) for the purpose of publishing research, the publisher **receives PHI on behalf of** the covered entity's research/publication activities. This would make the publisher a business associate if:

- The images are PHI (which they are, if faces are visible), AND
- The publisher is performing a function involving PHI on behalf of the covered entity.

**However**, if the images have been **properly de-identified** before submission to the publisher, HIPAA does not apply to de-identified information (Section 164.502(d)(2)). The problem in this scenario is that the de-identification failed.

**Important nuance:** If the authorization from the patient permits disclosure to the publisher (and the publisher is named or is within a named class of recipients per Section 164.508(c)(1)(iii)), and the authorization's conditions are met, the publisher may receive the PHI under the authorization rather than as a business associate. But in this scenario, the authorization conditions were NOT met (faces were supposed to be hidden), so this pathway fails.

In practice, most academic publishers do NOT enter into Business Associate Agreements (BAAs) with submitting authors or their institutions. Publishers typically assume they are receiving de-identified data or data authorized for publication. **The absence of a BAA is itself a potential violation** if the publisher is receiving PHI -- Section 164.502(e)(2) requires written documentation (a BAA) as satisfactory assurance.

### 2C. Jurisdictional Analysis by Party Location

**Scenario 1: All US-based (baseline)**
- HIPAA fully applies. The hospital/university is a covered entity. Authors act as workforce members of the covered entity. The publisher may be a business associate. Full HIPAA jurisdiction.

**Scenario 2: Non-US publisher, US-based authors/patients**
- **HIPAA still applies to the covered entity (hospital/university).** The covered entity's obligation to protect PHI does not end when PHI crosses borders. The covered entity violated HIPAA by making an impermissible disclosure.
- **The non-US publisher** presents a complicated enforcement question. If the publisher has no US presence, HHS OCR has limited practical enforcement power over the publisher directly. However:
  - If there is a BAA, the publisher has contractually agreed to comply with HIPAA requirements.
  - The covered entity remains liable for disclosing PHI to a business associate without adequate safeguards.
  - Under Section 164.508(c)(2)(iii), the authorization must warn that "information disclosed pursuant to the authorization [may] be subject to redisclosure by the recipient and no longer be protected by this subpart." This acknowledges that once PHI leaves the covered entity, HIPAA's direct protections may be limited.

**Scenario 3: Non-US patients at US hospitals**
- **HIPAA applies.** HIPAA protects all patients of covered entities, regardless of nationality or citizenship. A non-US patient treated at a US hospital has the same HIPAA protections as a US patient. HIPAA's definition of "individual" is not limited to US citizens or residents.

**Scenario 4: US patients, data sent to non-US publishers**
- **HIPAA applies to the covered entity's disclosure.** The covered entity cannot escape HIPAA obligations by sending PHI overseas. The covered entity must ensure proper authorization and de-identification regardless of where the recipient is located.
- Section 164.502(a) flatly prohibits use or disclosure of PHI "except as permitted or required by this subpart." There is no geographic exception.

### 2D. Summary of Jurisdictional Requirements

| Party | Location | HIPAA Applies? |
|-------|----------|---------------|
| Hospital/University (CE) | US | YES -- always |
| Hospital/University (CE) | Non-US | Generally NO (not a US covered entity) |
| Authors (workforce of CE) | US | YES -- through their CE |
| Authors (workforce of CE) | Non-US, employed by US CE | YES -- CE remains responsible |
| Publisher (potential BA) | US | YES -- if BA relationship exists |
| Publisher (potential BA) | Non-US | Limited direct enforcement, but CE remains liable |
| Patients | US | Protected |
| Patients | Non-US, treated at US CE | Protected |

**Conclusion:** It is NOT necessary for all three parties to be US-based. HIPAA applies as long as the covered entity is a US covered entity. The nationality of the patient is irrelevant (all patients of US covered entities are protected). The location of the publisher affects enforcement practicality but does not relieve the covered entity of its obligations.

---

## Question 3: Who Is to Blame?

### 3A. The Authors/Researchers

**Primary operational responsibility for the de-identification failure.**

The authors are typically members of the workforce of the covered entity (the hospital or university). Under HIPAA:

- **Section 164.502(a)** prohibits a covered entity from using or disclosing PHI except as permitted. The authors, acting on behalf of the covered entity, are the ones who prepared and submitted the images.
- **Section 164.514(b)** places the de-identification obligation on the covered entity. The authors, as the individuals performing the de-identification, bear direct responsibility for its adequacy.
- The authors had **the most knowledge and control** over the images. They selected which images to include, determined what de-identification steps to take, and submitted the images to the publisher.
- For CT scan face reconstruction risks specifically, researchers in radiology and medical imaging are increasingly expected to be aware of this risk. Numerous publications have documented that volumetric CT data can be used for facial reconstruction. Failure to address this known risk could push the violation from Tier 1 to Tier 2 (reasonable cause) or even Tier 3 (willful neglect) depending on the circumstances.

**The authors are the most directly culpable party for the de-identification failure itself.**

### 3B. The Hospital/Institution (Covered Entity)

**Ultimate legal liability under HIPAA.**

The institution bears the heaviest LEGAL responsibility because HIPAA's obligations fall on the covered entity:

- **Section 164.530(b)** (training): The covered entity must train all workforce members on PHI policies and procedures. If the institution failed to train researchers on proper image de-identification (including the CT facial reconstruction risk), the institution is independently liable.
- **Section 164.530(c)** (safeguards): The covered entity must have "appropriate administrative, technical, and physical safeguards to protect the privacy of protected health information." This includes having procedures for de-identifying images before publication. If no such procedures existed, the institution violated this independent requirement.
- **Section 164.530(a)** (policies and procedures): The covered entity must implement policies and procedures to comply with the Privacy Rule. This includes policies governing research publication involving patient data.
- **Section 164.530(d)** (complaints): The covered entity must have a process for receiving complaints about privacy practices.
- **Section 164.530(e)** (sanctions): The covered entity must have sanctions against workforce members who violate privacy policies.
- The covered entity is **vicariously liable** for the acts of its workforce members. Under HIPAA, the entity -- not the individual researcher -- is the regulated party for civil penalties.
- The institution is responsible for **breach notification** under 42 CFR 164.400-414.

**The institution bears ultimate legal liability and the breach notification obligation.** OCR enforcement actions and civil monetary penalties are directed at the covered entity.

### 3C. The Publisher

**Potentially liable, but to a lesser degree, and only if a business associate relationship exists.**

The publisher's liability depends on its relationship to the covered entity:

**If the publisher IS a business associate (BAA in place):**
- Under **Section 164.502(a)(3)**, a business associate "may use or disclose protected health information only as permitted or required by its business associate contract."
- The publisher would have an independent obligation to safeguard PHI and could be directly liable for HIPAA violations under HITECH Act provisions that extended direct liability to business associates.
- However, the publisher's responsibility is primarily to safeguard PHI it receives, not to perform the initial de-identification. The publisher could argue it reasonably relied on the authors/institution to provide properly de-identified images.

**If the publisher is NOT a business associate (no BAA):**
- The publisher has no direct HIPAA obligations (HIPAA only regulates covered entities and business associates).
- However, the **absence** of a BAA when one was required is itself a violation -- by the covered entity, not the publisher.
- The publisher may have other legal exposure (state privacy laws, common law negligence, contractual obligations to patients via the consent/authorization chain) but not directly under HIPAA.

**Practical considerations for publishers:**
- Many journals have editorial policies requiring confirmation that images are properly de-identified and that appropriate consent/authorization has been obtained. Failure to enforce these policies could create non-HIPAA liability (negligence, breach of editorial standards).
- Some publishers have begun implementing automated facial detection in submitted images as a safeguard. Failure to use available technology could be relevant to a negligence analysis, though this is outside HIPAA's scope.
- The publisher's peer review process is not a HIPAA-mandated safeguard, but it represents an opportunity to catch de-identification failures.

### 3D. Allocation of Blame -- Summary

| Party | Type of Responsibility | HIPAA Liability | Severity |
|-------|----------------------|-----------------|----------|
| **Authors/Researchers** | Operational (performed inadequate de-identification) | Indirect (through CE) | HIGH -- proximate cause of failure |
| **Hospital/Institution** | Legal (covered entity obligations) | Direct (CE is the regulated entity) | HIGHEST -- ultimate legal liability, breach notification, civil penalties |
| **Publisher** | Secondary (received and published PHI) | Conditional (only if BA) | MODERATE to LOW -- depending on BA status and editorial safeguards |

### 3E. Practical Enforcement Implications

HHS OCR enforcement typically targets the **covered entity** (the institution), not individual researchers. However:

1. The institution may impose **internal sanctions** on the researchers under Section 164.530(e).
2. If the violation involved **knowing** disclosure of PHI, individual criminal liability under 42 USC 1320d-6 could theoretically attach, though this is exceedingly rare for research publication scenarios.
3. The institution cannot delegate away its HIPAA obligations. Even if the researchers were negligent, the institution is liable for failing to have adequate safeguards, training, and oversight.
4. State attorneys general can also bring HIPAA enforcement actions under the HITECH Act, which could target any party within their jurisdiction.

---

## Key Regulatory Citations Summary

| Section | Topic | Relevance |
|---------|-------|-----------|
| 42 CFR 164.502(a) | General rule on PHI use/disclosure | Prohibits disclosure except as permitted; establishes framework |
| 42 CFR 164.502(a)(5)(ii) | Sale of PHI | May apply if remuneration flows to CE from publisher |
| 42 CFR 164.502(d) | De-identified information | De-identified data is exempt from HIPAA; face-visible images fail this test |
| 42 CFR 164.502(e) | Business associate disclosures | Requires BAA for PHI disclosures to BAs |
| 42 CFR 164.508(a)(1) | Authorization requirement | Disclosure must be "consistent with" authorization; conditional auth violated |
| 42 CFR 164.508(c)(1) | Core authorization elements | Authorization must describe information and purpose specifically |
| 42 CFR 164.514(a) | De-identification standard | Defines when health information is not individually identifiable |
| 42 CFR 164.514(b)(1) | Expert Determination method | Expert must certify "very small" re-identification risk |
| 42 CFR 164.514(b)(2)(i)(Q) | Safe Harbor -- facial images | "Full face photographic images and any comparable images" are identifiers |
| 42 CFR 164.514(e)(2)(xvi) | Limited data set -- facial images | Even limited data sets exclude full face images |
| 42 CFR 164.530 | Administrative requirements | Training, safeguards, policies, sanctions, breach notification |
| 42 CFR 164.400-414 | Breach Notification Rule | Requires notification to individuals, HHS, and media (if applicable) |
| 42 USC 1320d-5 | Civil penalties | Tiered penalties based on culpability level |
| 42 USC 1320d-6 | Criminal penalties | Applies to knowing violations |

---

## Recommendations for Researchers and Institutions

1. **Treat all volumetric medical imaging data (CT, MRI) as containing facial identifiers** unless expert determination confirms otherwise. 3D facial reconstruction from CT data is a well-documented risk.

2. **Implement institutional policies** specifically addressing image de-identification for research publication, including:
   - Defacing algorithms for volumetric data
   - Automated face detection on all images prior to submission
   - Independent review of de-identification adequacy

3. **Obtain specific, informed authorization** that clearly describes what images will be published and in what form. Conditional authorizations (e.g., "only if face is not visible") create compliance risk if the condition is not reliably met.

4. **Execute Business Associate Agreements** with publishers when there is any possibility that submitted images contain PHI (i.e., before de-identification is confirmed).

5. **Train all research personnel** on HIPAA de-identification requirements, specifically including the 18 Safe Harbor identifiers and the specific risks of medical imaging data.

6. **Establish breach response procedures** for publication-related PHI disclosures, including rapid communication with publishers to retract or redact images if a face leak is discovered post-publication.
