---
title: "360° GMC Patient Feedback Questionnaire"
description: "The GMC-recommended multi-rater (360°) patient feedback questionnaire for clinician appraisal — 9 questions rating patients' experience of care and their views on their clinician's competence and communication."
tags:
  - "360"
  - "multi-rater"
  - "appraisal"
  - "patient"
  - "feedback"
  - "professional-behaviours"
attribution:
  authors: "CheckTick"
  title: "360° GMC Patient Feedback Questionnaire (CheckTick generic item bank)"
  year: 2026
  license: "Released under the CheckTick project licence (MIT). Original items written for CheckTick — no third-party instrument."
---

CATEGORIES
  rater_role:
    label: Rater Role
    values: self, clinician, patient
    source: token

# Patient Introduction {patient-introduction}    ~ cat:rater_role:patient
Patient Introduction

## Content block {content-block}
(content_block)
heading: Patient questionnaire

Licensed doctors are expected to seek feedback from colleagues and patients and review and act upon that feedback where
appropriate.
The purpose of this exercise is to provide doctors with information about their work through the eyes of those they work with and treat, and is intended to help inform their further development.
Please base your answers only on the consultation you have had today.

## Are you filling in this questionnaire for:* {are-you-filling-in-this-questi}
(mc_single)
- Yourself
- Your child
- Your spouse or partner
- Another relative or friend

## Which of the following best describes the reason you saw the doctor today? (Please tick all the boxes that apply)* {which-of-the-following-best-de}
(mc_multi)
- To ask for advice
- Because of an ongoing problem
- For treatment (including prescriptions)
- Because of a one-off problem
- For a routine check
- Other (please give details)

## On a scale of 1 to 5, how important to your health and wellbeing was your reason for visiting the doctor today? {on-a-scale-of-1-to-5,-how-impo}
(grid likert number)
min: 1
max: 5
left: Not very important
right: Not very important
na: Does not apply
### Being polite*
### Making you feel at ease*
### Listening to you*
### Assessing your medical condition*
### Explaining your condition and treatment*
### Involving you in decisions about your treatment*
### Providing or arranging treatment for you*
### This doctor will keep information about me confidential*
### This doctor is honest and trustworthy*

## I am confident about this doctor’s ability to provide care* {i-am-confident-about-this-doct}
(yesno)
- Yes
- No

## I would be completely happy to see this doctor again {i-would-be-completely-happy-to}
(yesno)
- Yes
- No

## Was this visit with your usual doctor?* {was-this-visit-with-your-usual}
(yesno)
- Yes
- No

## Please add any other comments you want to make about this doctor. Please note: No patients will be identified when this information is given to the doctor. {please-add-any-other-comments}
(long_text)

# Self-assessment {self-assessment}    ~ cat:rater_role:self
Self Assessment

## Content block {content-block-self}
(content_block)
heading: Self assessment

Please rate yourself in each of the following areas by ticking one box in each line.
Your own ratings are compared with the feedback from your colleagues and patients in your appraisal report.

## Please rate yourself in each of the following areas by ticking one box in each line. {please-rate-yourself-in}
(grid likert categories)
- Poor
- Less than Satisfactory
- Satisfactory
- Good
- Very Good
na: Don't know
### Clinical Knowledge*
### Diagnosis*
### Clinical decision making*
### Treatment (including practical procedures)*
### Prescribing*
### Medical record keeping*
### Recognising and working within limitations*
### Keeping knowledge and skills up to date*
### Reviewing and reflecting on own performance*
### Teaching (students, trainees, others)*
### Supervising colleagues*
### Commitment to care and wellbeing of patients*
### Communication with patients and relatives*
### Working effectively with colleagues*
### Effective time management*
### I respect patient confidentiality*
### I am honest and trustworthy*
### My performance is not impaired by ill health*

## Do you consider yourself fit to practise medicine?* {do-you-consider-yourself-fit}
(yesno)
- Yes
- No

# Colleague Introduction {colleague-introduction}    ~ cat:rater_role:clinician
Colleague Introduction

## Content block {content-block}
(content_block)
heading: Colleague Feedback

Licensed doctors are expected to seek feedback from colleagues and patients and review and act upon that feedback where
appropriate.
The purpose of this exercise is to provide doctors with information about their work through the eyes of those they work with and
treat, and is intended to help inform their further development.
Please do not write your name on this questionnaire.
Please answer all the questions. If you feel you cannot answer any question, please tick ‘Don’t know’

## Please rate your colleague in each of the following areas by ticking one box in each line. {please-rate-your-colleague-in}
(grid likert categories)
- Poor
- Less than Satisfactory
- Satisfactory
- Good
- Very Good
na: Don't know
### Clinical Knowledge*
### Diagnosis*
### Clinical decision making*
### Treatment (including practical procedures)*
### Prescribing*
### Medical record keeping*
### Recognising and working within limitations*
### Keeping knowledge and skills up to date*
### Reviewing and reflecting on own performance*
### Teaching (students, trainees, others)*
### Supervising colleagues*
### Commitment to care and wellbeing of patients*
### Communication with patients and relatives*
### Working effectively with colleagues*
### Effective time management*
### This doctor respects patient confidentiality*
### This doctor is honest and trustworthy*
### This doctor’s performance is not impaired by ill health*

## This doctor is fit to practise medicine* {this-doctor-is-fit-to-practise}
(yesno)
- Yes
- No
- Don't know

## Please add any other comments you want to make about this doctor. Please note: No one will be identified when this information is given back to the doctor. {please-add-any-other-comments}
(long_text)

# Ethnicity Questions {ethnicity-questions}    ~ cat:rater_role:clinician, cat:rater_role:patient

## What is your ethnic group? Please choose one section from A to E, and then tick the appropriate box to indicate your cultural background {what-is-your-ethnic-group?-ple}
(mc_single)
- [A White]
- British
- Irish
- Any other white background
- [B Mixed]
- White and black Caribbean
- White and black African
- White and Asian
- Any other Mixed background
- [C Asian or Asian British]
- Indian
- Pakistani
- Bangladeshi
- Any other Asian background
- [D Black or Black British]
- Caribbean
- African
- Any other Black background
- [E Chinese or other ethnic group]
- Chinese
- Any other
render: cascading_radios

# Sex/Gender Questions {sex/gender-questions}    ~ cat:rater_role:clinician, cat:rater_role:patient

## Are you: {are-you:}
(yesno)
- Female
- Male

# Age Questions {age-questions}    ~ cat:rater_role:clinician, cat:rater_role:patient

## Age* {age}
(mc_single)
- 16 - 19
- 20 - 29
- 30 - 39
- 40 - 49
- 50 - 59
- 60 or over

# Professional Role {professional-role}    ~ cat:rater_role:clinician

## Your professional role (please tick only one box):* {your-professional-role-(please}
(mc_single)
- Doctor
  + If you are a doctor, are you in a training grade? (yesno, required)
- Registered Nurse
- Health Visitor/Midwife
- Pharmacist
- Administrator/Receptionist/Secretary
- Allied Healthcare Professional
- Health Care Assistant
- Non-clinical Manager
- Other
  + Please specify

# Professional Relationship {professional-relationship}    ~ cat:rater_role:clinician

## How recently have you been familiar with this doctor’s clinical practice?* {how-recently-have-you-been-fam}
(mc_single)
- Current colleague
- Within the last two years
- Between two and five years ago
- Between six and ten years ago
- More than ten years ago

## During this period of your familiarity with this doctor’s clinical practice, how often did you have contact with the doctor?* {during-this-period-of-your-fam}
(mc_single)
- Most days
- Weekly
- Monthly
- Less often
