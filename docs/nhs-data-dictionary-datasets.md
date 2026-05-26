---
title: NHS Clinical Datasets
category: getting-started
---

CheckTick provides ready-to-use clinical dropdown lists drawn from authoritative NHS sources. This page covers the two main categories: **NHS Data Dictionary** standard code lists and **SNOMED CT** refsets.

For a full overview of all dataset types (including RCPCH organisational data and community-published lists), see the [Datasets Overview](datasets.md).

---

## NHS Data Dictionary Datasets

The [NHS Data Dictionary](https://www.datadictionary.nhs.uk/) provides standardised definitions, codes, and value sets used across the NHS. CheckTick imports selected datasets and keeps them up-to-date through automated synchronisation.

### About NHS DD Datasets

- **Automated updates**: Datasets are automatically scraped and synchronised on a regular schedule
- **Source verification**: Each dataset includes a direct link to its NHS DD source page
- **Version tracking**: Last updated dates are tracked for transparency
- **Manual review**: New datasets are reviewed by maintainers before addition

### How to Request a New NHS DD Dataset

If you need an NHS DD list that isn't currently available:

1. Click the **"Request NHS DD List"** button on the [Datasets page](/surveys/datasets/)
2. Fill out the GitHub issue template with:
   - Dataset name and NHS DD URL
   - Your use case and expected frequency of use
   - Suggested tags for categorisation
3. Maintainers will review and add it if it's scrapable and beneficial to the community

## Available NHS DD Datasets

| Dataset Name                                   | NHS DD URL                                                                                                                           | Categories                            | Date Added | Last Scraped | NHS DD Published |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------- | ---------- | ------------ | ---------------- |
| Ethnic Category                                | [Link](https://www.datadictionary.nhs.uk/data_elements/ethnic_category.html)                                                         | demographics                          | 2024-11-15 | 2024-11-15   | -                |
| Main Specialty Code                            | [Link](https://www.datadictionary.nhs.uk/data_elements/main_specialty_code__mental_health_.html)                                     | medical, specialty                    | 2024-11-15 | 2024-11-15   | -                |
| Treatment Function Code                        | [Link](https://www.datadictionary.nhs.uk/data_elements/treatment_function_code__mental_health_.html)                                 | medical, treatment                    | 2024-11-15 | 2024-11-15   | -                |
| Accommodation Status                           | [Link](https://www.datadictionary.nhs.uk/data_elements/accommodation_status_code.html)                                               | administrative, demographic           | 2025-11-16 | Pending      | -                |
| Accommodation Type                             | [Link](https://www.datadictionary.nhs.uk/data_elements/accommodation_type.html)                                                      | administrative, demographic           | 2025-11-16 | Pending      | -                |
| Admission Source (Hospital Provider)           | [Link](https://www.datadictionary.nhs.uk/data_elements/admission_source__hospital_provider_spell_.html)                              | administrative, clinic                | 2025-11-16 | Pending      | -                |
| Admission Source (Mental Health Provider)      | [Link](https://www.datadictionary.nhs.uk/data_elements/admission_source__mental_health_hospital_provider_spell_.html)                | administrative, clinic, mental health | 2025-11-16 | Pending      | -                |
| Alcohol Use Indicator                          | [Link](https://www.datadictionary.nhs.uk/data_elements/alcohol_use_indicator.html)                                                   | clinic, medical                       | 2025-11-16 | Pending      | -                |
| ASA Physical Status Classification             | [Link](https://www.datadictionary.nhs.uk/data_elements/asa_physical_status_classification_system_code.html)                          | surgical, medical, procedural         | 2025-11-16 | Pending      | -                |
| Blood Group (Baby)                             | [Link](https://www.datadictionary.nhs.uk/data_elements/blood_group__baby_.html)                                                      | neonatal, paediatric, medical         | 2025-11-16 | Pending      | -                |
| Blood Transfusion Product Type                 | [Link](https://www.datadictionary.nhs.uk/data_elements/blood_transfusion_product_type.html)                                          | medical, procedural                   | 2025-11-16 | Pending      | -                |
| Care Professional Job Role Code                | [Link](https://www.datadictionary.nhs.uk/data_elements/care_professional__job_role_code_.html)                                       | administrative, clinic                | 2025-11-16 | Pending      | -                |
| Care Professional Main Specialty Code          | [Link](https://www.datadictionary.nhs.uk/data_elements/care_professional_main_specialty_code.html)                                   | administrative, clinic, medical       | 2025-11-16 | Pending      | -                |
| Childhood Immunisation Type (Cover)            | [Link](https://www.datadictionary.nhs.uk/data_elements/childhood_immunisation_type__cover_.html)                                     | paediatric, medical, clinic           | 2025-11-16 | Pending      | -                |
| Clinical Frailty Scale Point                   | [Link](https://www.datadictionary.nhs.uk/data_elements/clinical_frailty_scale_point.html)                                            | clinic, medical                       | 2025-11-16 | Pending      | -                |
| Consultation Type                              | [Link](https://www.datadictionary.nhs.uk/data_elements/consultation_type.html)                                                       | administrative, clinic                | 2025-11-16 | Pending      | -                |
| Consultation Medium Used                       | [Link](https://www.datadictionary.nhs.uk/data_elements/consultation_medium_used.html)                                                | administrative, clinic                | 2025-11-16 | Pending      | -                |
| Contraception Other Method                     | [Link](https://www.datadictionary.nhs.uk/data_elements/contraception_other_method.html)                                              | clinic, medical                       | 2025-11-16 | Pending      | -                |
| Death Location Type Code                       | [Link](https://www.datadictionary.nhs.uk/data_elements/death_location_type_code__actual_.html)                                       | administrative                        | 2025-11-16 | Pending      | -                |
| Delivery Method Code                           | [Link](https://www.datadictionary.nhs.uk/data_elements/delivery_method_code.html)                                                    | medical, procedural, maternity        | 2025-11-16 | Pending      | -                |
| Emergency Care Attendance Category             | [Link](https://www.datadictionary.nhs.uk/data_elements/emergency_care_attendance_category.html)                                      | administrative, clinic                | 2025-11-16 | Pending      | -                |
| Employee Absence Category                      | [Link](https://www.datadictionary.nhs.uk/data_elements/employee_absence_category.html)                                               | administrative                        | 2025-11-16 | Pending      | -                |
| Enteral Feeding Method                         | [Link](https://www.datadictionary.nhs.uk/data_elements/enteral_feeding_method.html)                                                  | medical, neonatal, paediatric         | 2025-11-16 | Pending      | -                |
| Gender Identity Code                           | [Link](https://www.datadictionary.nhs.uk/data_elements/gender_identity_code.html)                                                    | demographic                           | 2025-11-16 | Pending      | -                |
| Mental Health Absence Without Leave End Reason | [Link](https://www.datadictionary.nhs.uk/data_elements/mental_health_absence_without_leave_end_reason.html)                          | administrative, mental health         | 2025-11-16 | Pending      | -                |
| Mental Health Act Legal Status Code            | [Link](https://www.datadictionary.nhs.uk/data_elements/mental_health_act_legal_status_classification_code.html)                      | administrative, mental health         | 2025-11-16 | Pending      | -                |
| Mental Health Admitted Patient Classification  | [Link](https://www.datadictionary.nhs.uk/data_elements/mental_health_admitted_patient_classification_type.html)                      | administrative, mental health         | 2025-11-16 | Pending      | -                |
| Mode of Delivery                               | [Link](https://www.datadictionary.nhs.uk/data_elements/mode_of_delivery.html)                                                        | medical, procedural, maternity        | 2025-11-16 | Pending      | -                |
| Neonatal Consciousness Status                  | [Link](https://www.datadictionary.nhs.uk/data_elements/neonatal_consciousness_status.html)                                           | neonatal, paediatric, medical         | 2025-11-16 | Pending      | -                |
| Newborn Blood Spot Test Outcome Status Code    | [Link](https://www.datadictionary.nhs.uk/data_elements/newborn_blood_spot_test_outcome_status_code__congenital_hypothyroidism_.html) | neonatal, paediatric, medical         | 2025-11-16 | Pending      | -                |
| Newborn Hearing Screening Outcome              | [Link](https://www.datadictionary.nhs.uk/data_elements/newborn_hearing_screening_outcome.html)                                       | neonatal, paediatric, medical         | 2025-11-16 | Pending      | -                |
| Out-Patient Attendance Outcome                 | [Link](https://www.datadictionary.nhs.uk/data_elements/out-patient_attendance_outcome.html)                                          | administrative, clinic                | 2025-11-16 | Pending      | -                |
| Patient Classification Code                    | [Link](https://www.datadictionary.nhs.uk/data_elements/patient_classification_code.html)                                             | administrative, clinic                | 2025-11-16 | Pending      | -                |
| Person Stated Gender Code                      | [Link](https://www.datadictionary.nhs.uk/data_elements/person_stated_gender_code.html)                                               | demographic                           | 2025-11-16 | Pending      | -                |
| Person Stated Sexual Orientation               | [Link](https://www.datadictionary.nhs.uk/data_elements/person_stated_sexual_orientation_code.html)                                   | demographic                           | 2025-11-16 | Pending      | -                |
| Pregnancy Outcome                              | [Link](https://www.datadictionary.nhs.uk/data_elements/pregnancy_outcome.html)                                                       | medical, maternity                    | 2025-11-16 | Pending      | -                |
| Presentation of Fetus at Delivery              | [Link](https://www.datadictionary.nhs.uk/data_elements/presentation_of_fetus_at_delivery.html)                                       | medical, maternity                    | 2025-11-16 | Pending      | -                |
| Primitive Reflexes Status                      | [Link](https://www.datadictionary.nhs.uk/data_elements/primitive_reflexes_status.html)                                               | neonatal, paediatric, medical         | 2025-11-16 | Pending      | -                |
| Qualification Type                             | [Link](https://www.datadictionary.nhs.uk/data_elements/qualification_type.html)                                                      | administrative                        | 2025-11-16 | Pending      | -                |
| Restrictive Intervention Type                  | [Link](https://www.datadictionary.nhs.uk/data_elements/restrictive_intervention_type.html)                                           | mental health, clinic                 | 2025-11-16 | Pending      | -                |
| Retinopathy of Prematurity (Left Eye)          | [Link](https://www.datadictionary.nhs.uk/data_elements/retinopathy_of_prematurity_stage__left_eye_.html)                             | neonatal, paediatric, medical         | 2025-11-16 | Pending      | -                |
| Retinopathy of Prematurity (Right Eye)         | [Link](https://www.datadictionary.nhs.uk/data_elements/retinopathy_of_prematurity_stage__right_eye_.html)                            | neonatal, paediatric, medical         | 2025-11-16 | Pending      | -                |
| Smoking Status Code                            | [Link](https://www.datadictionary.nhs.uk/data_elements/smoking_status_code.html)                                                     | clinic, medical                       | 2025-11-16 | Pending      | -                |
| Special Educational Need Type                  | [Link](https://www.datadictionary.nhs.uk/data_elements/special_educational_need_type.html)                                           | paediatric, administrative            | 2025-11-16 | Pending      | -                |
| Specialist Radiotherapy Treatment Type         | [Link](https://www.datadictionary.nhs.uk/data_elements/specialist_radiotherapy_treatment_type.html)                                  | medical, procedural                   | 2025-11-16 | Pending      | -                |
| Surgical Access Type                           | [Link](https://www.datadictionary.nhs.uk/data_elements/surgical_access_type.html)                                                    | surgical, procedural                  | 2025-11-16 | Pending      | -                |
| Ward Security Level                            | [Link](https://www.datadictionary.nhs.uk/data_elements/ward_security_level.html)                                                     | administrative, mental health         | 2025-11-16 | Pending      | -                |
| Zygosity Status                                | [Link](https://www.datadictionary.nhs.uk/data_elements/zygosity_status.html)                                                         | neonatal, paediatric, medical         | 2025-11-16 | Pending      | -                |

## Dataset Categories

Datasets are tagged with one or more categories to aid discovery:

- **administrative**: Administrative and operational data
- **clinic**: Clinical consultation and care delivery
- **demographic**: Patient demographic information
- **procedural**: Procedures and interventions
- **surgical**: Surgical procedures
- **medical**: Medical treatments and conditions
- **neonatal**: Neonatal care
- **paediatric**: Paediatric care
- **mental health**: Mental health services
- **maternity**: Maternity and obstetric care

## Technical Details

### Sync Process

The NHS DD sync command (`sync_nhs_dd_datasets`):

1. Reads dataset definitions from `docs/nhs-data-dictionary-datasets.md`
2. Creates or updates dataset records in the database
3. For each dataset:
   - Fetches the HTML from the NHS DD URL
   - Parses tables containing codes and descriptions
   - Extracts key-value pairs
   - Updates the dataset options in the database
4. Records the last scraped timestamp
5. Logs any errors or changes

### Scheduling

The sync runs on a scheduled basis (configured in the deployment) to keep datasets up-to-date with NHS DD changes.

### Manual Sync

Administrators can manually trigger a sync:

```bash
python manage.py sync_nhs_dd_datasets
python manage.py sync_nhs_dd_datasets --dataset accommodation_status_code  # Single dataset
python manage.py sync_nhs_dd_datasets --force  # Force re-sync all
```

## Data Governance

### Source Attribution

All NHS DD datasets clearly attribute their source with:

- Link to official NHS DD page
- "NHS DD" badge in the dataset detail view
- Description noting "NHS Data Dictionary" origin

### Data Accuracy

While we strive for accuracy:

- **Primary Source**: Always refer to the official NHS DD website for authoritative data
- **Automated Sync**: Regular updates minimize drift from source
- **User Verification**: Users can click through to source URLs to verify data
- **Issue Reporting**: Report discrepancies via GitHub issues

### Usage in Surveys

NHS DD datasets can be used like any other dataset in CheckTick:

- Select in question configuration
- Clone to create custom variants
- Reference in survey logic

## Support

For questions or issues with NHS DD datasets:

1. Check the [official NHS DD website](https://www.datadictionary.nhs.uk/)
2. Search [existing GitHub issues](https://github.com/eatyourpeas/checktick/issues)
3. Create a new issue using the appropriate template
4. Contact the development team

---

## SNOMED CT Refsets

SNOMED CT (Systematised Nomenclature of Medicine — Clinical Terms) is the NHS standard clinical terminology. CheckTick integrates a curated subset of SNOMED CT **refsets** — expert-validated lists assembled for a specific clinical purpose — to power dropdown questions in surveys.

### What Is a Refset?

A refset is a curated subset of SNOMED CT concepts, assembled and maintained by clinical experts for a defined purpose. Examples include the QOF antiepileptic drug list (all antiepileptic medicines used in UK primary care for QOF purposes), or the UK Allergy Substances refset. These are fundamentally different from the raw SNOMED hierarchy (all 831k concepts, or all body structures): they are constrained, clinically meaningful lists that make sense as survey dropdown options.

CheckTick does **not** expose raw SNOMED hierarchies as survey dropdowns. Only validated refsets are surfaced.

### How It Works

SNOMED CT terminology is served live from a local SQLite database (`snomed.db`) generated from the NHS TRUD UK Monolith Edition. The actual terms are never copied into the CheckTick database — they are queried directly from `snomed.db` at render time. This means:

- Terms are always current with the installed SNOMED release
- Updating to a new SNOMED release updates every dropdown immediately
- Survey responses store the stable SCTID (concept identifier), not the display term — so responses remain valid across terminology updates

If `snomed.db` is not present (for example on a self-hosted instance that has not completed SNOMED setup), SNOMED datasets show as unavailable and surveys degrade gracefully — no errors, just an informative message.

### Available SNOMED Refsets

CheckTick ships the following featured refsets out of the box:

**QOF drug lists (NHS England)**
- Antiepileptic drug list
- Diabetes drug list
- Atrial fibrillation drug list
- COPD/Asthma drug list

**NHS clinical**
- UK Ethnic Categories
- UK Allergy Substances

**Paediatric specialty condition sets**
- Epilepsy syndromes, endocrine disorders, cardiac conditions, respiratory conditions, neuromuscular disorders, epilepsy genes, renal conditions, GI conditions, rare chromosomal conditions

### Requesting a New SNOMED Refset

Click the **"Request SNOMED Refset"** button on the [Datasets page](/surveys/datasets/) and fill in the GitHub issue template. The maintainer will review against the available refsets in the UK Monolith and add the descriptor if appropriate. Adding a new refset requires no data migration — only a single descriptor row and a re-seed.

### Self-Hosting SNOMED

SNOMED CT requires a one-time setup to download and build `snomed.db` from NHS TRUD. A TRUD account with a subscription to the UK Monolith Edition (item 1799) is required. See the [SNOMED CT Integration guide](snomed-integration.md) for full setup instructions, environment variables, and scheduled update configuration.

---

## See Also

- [Datasets Overview](datasets.md)
- [SNOMED CT Integration](snomed-integration.md)
- [Dataset Loading Architecture](dataset-loading-architecture.md)
- [Prefilled Datasets Setup](prefilled-datasets-setup.md)
- [Data Governance](data-governance.md)
