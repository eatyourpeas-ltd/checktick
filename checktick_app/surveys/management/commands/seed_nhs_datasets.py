"""
Management command to seed NHS Data Dictionary standard datasets.

Usage:
    python manage.py seed_nhs_datasets
    python manage.py seed_nhs_datasets --clear  # Clear existing NHS DD datasets first
"""

from django.core.management.base import BaseCommand
from checktick_app.surveys.models import DataSet


class Command(BaseCommand):
    help = "Seed NHS Data Dictionary standard datasets"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing NHS DD datasets before seeding",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            deleted_count = DataSet.objects.filter(category="nhs_dd").delete()[0]
            self.stdout.write(
                self.style.WARNING(f"Deleted {deleted_count} existing NHS DD datasets")
            )

        # NHS DD datasets to seed
        nhs_dd_datasets = [
            {
                "key": "main_specialty_code",
                "name": "Main Specialty Code",
                "description": "NHS Data Dictionary - Main Specialty Codes for medical practitioners",
                "category": "nhs_dd",
                "source_type": "manual",
                "is_custom": False,
                "is_global": True,
                "options": [
                    "100 - General Surgery",
                    "101 - Urology",
                    "110 - Trauma and Orthopaedic Surgery",
                    "120 - ENT",
                    "130 - Ophthalmology",
                    "140 - Oral Surgery",
                    "141 - Restorative Dentistry",
                    "142 - Paediatric Dentistry",
                    "143 - Orthodontics",
                    "170 - Cardiothoracic Surgery",
                    "180 - Emergency Medicine",
                    "190 - Anaesthetics",
                    "191 - Pain Management",
                    "300 - General Medicine",
                    "301 - Gastroenterology",
                    "302 - Endocrinology and Diabetes",
                    "303 - Clinical Haematology",
                    "304 - Clinical Physiology",
                    "305 - Clinical Pharmacology",
                    "310 - Audio Vestibular Medicine",
                    "320 - Cardiology",
                    "330 - Dermatology",
                    "340 - Respiratory Medicine (also known as Thoracic Medicine)",
                    "350 - Infectious Diseases",
                    "352 - Tropical Medicine",
                    "360 - Genitourinary Medicine",
                    "361 - Nephrology",
                    "370 - Medical Oncology",
                    "371 - Nuclear Medicine",
                    "400 - Neurology",
                    "401 - Clinical Neurophysiology",
                    "410 - Rheumatology",
                    "420 - Paediatrics",
                    "421 - Paediatric Neurology",
                    "430 - Geriatric Medicine",
                    "450 - Dental Medicine Specialties",
                    "451 - Special Care Dentistry",
                    "460 - Medical Ophthalmology",
                    "501 - Obstetrics",
                    "502 - Gynaecology",
                    "560 - Midwifery",
                    "650 - Physiotherapy",
                    "651 - Occupational Therapy",
                    "652 - Speech and Language Therapy",
                    "653 - Podiatry",
                    "654 - Dietetics",
                    "655 - Orthoptics",
                    "656 - Clinical Psychology",
                    "657 - Prosthetics",
                    "658 - Orthotics",
                    "659 - Dramatherapy",
                    "660 - Art Therapy",
                    "661 - Music Therapy",
                    "700 - Learning Disability",
                    "710 - Adult Mental Illness",
                    "711 - Child and Adolescent Psychiatry",
                    "712 - Forensic Psychiatry",
                    "713 - Medical Psychotherapy",
                    "715 - Old Age Psychiatry",
                    "800 - Clinical Oncology",
                    "810 - Radiology",
                    "820 - General Pathology",
                    "821 - Blood Transfusion",
                    "822 - Chemical Pathology",
                    "823 - Haematology",
                    "824 - Immunopathology",
                    "830 - Immunopathology",
                    "831 - Occupational Medicine",
                    "832 - Public Health Medicine",
                    "833 - Community Sexual and Reproductive Health",
                    "834 - Rehabilitation Medicine",
                    "900 - Community Medicine",
                    "901 - Occupational Health",
                    "950 - Nursing",
                    "960 - Allied Health Professional",
                ],
                "format_pattern": "code - description",
            },
            {
                "key": "treatment_function_code",
                "name": "Treatment Function Code",
                "description": "NHS Data Dictionary - Treatment Function Codes",
                "category": "nhs_dd",
                "source_type": "manual",
                "is_custom": False,
                "is_global": True,
                "options": [
                    "100 - General Surgery Service",
                    "101 - Urology Service",
                    "110 - Trauma & Orthopaedics Service",
                    "120 - Ear Nose and Throat Service",
                    "130 - Ophthalmology Service",
                    "140 - Oral Surgery Service",
                    "141 - Restorative Dentistry Service",
                    "142 - Paediatric Dentistry Service",
                    "143 - Orthodontics Service",
                    "160 - Plastic Surgery Service",
                    "170 - Cardiothoracic Surgery Service",
                    "180 - Emergency Medicine Service",
                    "190 - Anaesthetics Service",
                    "192 - Critical Care Medicine Service",
                    "300 - General Medicine Service",
                    "301 - Gastroenterology Service",
                    "302 - Endocrinology Service",
                    "303 - Clinical Haematology Service",
                    "305 - Clinical Pharmacology Service",
                    "310 - Audio Vestibular Medicine Service",
                    "320 - Cardiology Service",
                    "321 - Paediatric Cardiology Service",
                    "325 - Sport and Exercise Medicine Service",
                    "326 - Acute Internal Medicine Service",
                    "330 - Dermatology Service",
                    "340 - Respiratory Medicine Service",
                    "350 - Infectious Diseases Service",
                    "352 - Tropical Medicine Service",
                    "360 - Genitourinary Medicine Service",
                    "361 - Renal Medicine Service",
                    "370 - Medical Oncology Service",
                    "371 - Nuclear Medicine Service",
                    "400 - Neurology Service",
                    "401 - Clinical Neurophysiology Service",
                    "410 - Rheumatology Service",
                    "420 - Paediatrics Service",
                    "421 - Paediatric Neurology Service",
                    "430 - Geriatric Medicine Service",
                    "450 - Dental Medicine Service",
                    "451 - Special Care Dentistry Service",
                    "460 - Medical Ophthalmology Service",
                    "501 - Obstetrics Service",
                    "502 - Gynaecology Service",
                    "503 - Gynaecological Oncology Service",
                    "560 - Midwifery Service",
                    "650 - Physiotherapy Service",
                    "651 - Occupational Therapy Service",
                    "652 - Speech and Language Therapy Service",
                    "653 - Podiatry Service",
                    "654 - Dietetics Service",
                    "655 - Orthoptics Service",
                    "656 - Clinical Psychology Service",
                    "657 - Prosthetics Service",
                    "658 - Orthotics Service",
                    "700 - Learning Disability Service",
                    "710 - Adult Mental Illness Service",
                    "711 - Child and Adolescent Psychiatry Service",
                    "712 - Forensic Psychiatry Service",
                    "713 - Psychotherapy Service",
                    "715 - Old Age Psychiatry Service",
                    "800 - Clinical Oncology Service",
                    "810 - Radiology Service",
                    "812 - Diagnostic Imaging Service",
                    "820 - General Pathology Service",
                    "821 - Blood Transfusion Service",
                    "822 - Chemical Pathology Service",
                    "823 - Haematology Service",
                    "824 - Histopathology Service",
                    "830 - Immunopathology Service",
                    "831 - Medical Microbiology and Virology Service",
                    "834 - Medical Microbiology Service",
                    "840 - Audiology Service",
                    "920 - Diabetic Medicine Service",
                ],
                "format_pattern": "code - description",
            },
            {
                "key": "ethnic_category",
                "name": "Ethnic Category",
                "description": "NHS Data Dictionary - Ethnic Category codes",
                "category": "nhs_dd",
                "source_type": "manual",
                "is_custom": False,
                "is_global": True,
                "options": [
                    "A - White - British",
                    "B - White - Irish",
                    "C - White - Any other White background",
                    "D - Mixed - White and Black Caribbean",
                    "E - Mixed - White and Black African",
                    "F - Mixed - White and Asian",
                    "G - Mixed - Any other mixed background",
                    "H - Asian or Asian British - Indian",
                    "J - Asian or Asian British - Pakistani",
                    "K - Asian or Asian British - Bangladeshi",
                    "L - Asian or Asian British - Any other Asian background",
                    "M - Black or Black British - Caribbean",
                    "N - Black or Black British - African",
                    "P - Black or Black British - Any other Black background",
                    "R - Other Ethnic Groups - Chinese",
                    "S - Other Ethnic Groups - Any other ethnic group",
                    "Z - Not stated",
                ],
                "format_pattern": "code - description",
            },
        ]

        created_count = 0
        updated_count = 0

        for dataset_data in nhs_dd_datasets:
            dataset, created = DataSet.objects.update_or_create(
                key=dataset_data["key"],
                defaults=dataset_data,
            )
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Created: {dataset.name} ({dataset.key})")
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f"↻ Updated: {dataset.name} ({dataset.key})")
                )

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(
            self.style.SUCCESS(
                f"\n✓ Seeding complete: {created_count} created, {updated_count} updated"
            )
        )
        self.stdout.write(
            f"  Total NHS DD datasets: {DataSet.objects.filter(category='nhs_dd').count()}\n"
        )
