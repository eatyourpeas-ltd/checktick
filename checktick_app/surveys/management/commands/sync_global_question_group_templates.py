"""
Management command to sync global question group templates from the repository.

This command scans the docs/question-group-templates-*.md files for markdown files
containing question groups with YAML frontmatter metadata, and creates or updates
PublishedQuestionGroup entries with publication_level='global'.

Usage:
    python manage.py sync_global_question_group_templates [--dry-run] [--force]

Options:
    --dry-run: Show what would be synced without actually creating/updating records
    --force: Update templates even if they haven't changed
"""

import yaml
from pathlib import Path
from django.core.management.base import BaseCommand
from checktick_app.surveys.models import PublishedQuestionGroup
from checktick_app.surveys.views import parse_bulk_markdown_with_collections


class Command(BaseCommand):
    help = 'Sync global question group templates from repository markdown files'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be synced without making changes',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Update templates even if they haven\'t changed',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']

        # Get the base directory (project root) - go up from this file to project root
        # File is at: checktick_app/surveys/management/commands/
        # Need to go up 5 levels to reach project root
        base_dir = Path(__file__).resolve().parent.parent.parent.parent.parent
        docs_dir = base_dir / 'docs'

        if not docs_dir.exists():
            self.stdout.write(self.style.ERROR(f'Docs directory not found: {docs_dir}'))
            return

        # Find all question-group-templates-*.md files
        template_files = sorted(docs_dir.glob('question-group-templates-*.md'))

        if not template_files:
            self.stdout.write(self.style.WARNING('No template files found matching pattern: question-group-templates-*.md'))
            return

        self.stdout.write(self.style.SUCCESS(f'Found {len(template_files)} template file(s)'))

        synced_count = 0
        skipped_count = 0
        error_count = 0

        for template_file in template_files:
            try:
                result = self._process_template(template_file, dry_run, force)
                if result == 'synced':
                    synced_count += 1
                elif result == 'skipped':
                    skipped_count += 1
                elif result == 'error':
                    error_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error processing {template_file.name}: {str(e)}'))
                error_count += 1

        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=== Sync Summary ==='))
        if dry_run:
            self.stdout.write(f'Would sync: {synced_count}')
        else:
            self.stdout.write(f'Synced: {synced_count}')
        self.stdout.write(f'Skipped: {skipped_count}')
        self.stdout.write(f'Errors: {error_count}')

    def _process_template(self, template_file, dry_run, force):
        """Process a single template file."""
        self.stdout.write(f'\nProcessing: {template_file.name}')

        # Read the file
        content = template_file.read_text(encoding='utf-8')

        # Check for YAML frontmatter
        if not content.startswith('---\n'):
            self.stdout.write(self.style.WARNING('  Skipping: No YAML frontmatter found'))
            return 'skipped'

        # Extract YAML frontmatter
        try:
            parts = content.split('---\n', 2)
            if len(parts) < 3:
                self.stdout.write(self.style.WARNING('  Skipping: Invalid frontmatter format'))
                return 'skipped'

            yaml_content = parts[1]
            markdown_content = parts[2].strip()

            metadata = yaml.safe_load(yaml_content)
            if not isinstance(metadata, dict):
                self.stdout.write(self.style.WARNING('  Skipping: Invalid YAML metadata'))
                return 'skipped'

        except yaml.YAMLError as e:
            self.stdout.write(self.style.ERROR(f'  Error parsing YAML: {str(e)}'))
            return 'error'

        # Validate required fields
        required_fields = ['title', 'description', 'attribution']
        missing_fields = [f for f in required_fields if f not in metadata]
        if missing_fields:
            self.stdout.write(self.style.ERROR(f'  Error: Missing required fields: {", ".join(missing_fields)}'))
            return 'error'

        # Validate markdown can be parsed
        try:
            # Test parsing without actually saving
            parsed = parse_bulk_markdown_with_collections(markdown_content)
            if not parsed or 'groups' not in parsed:
                self.stdout.write(self.style.ERROR('  Error: Failed to parse markdown content'))
                return 'error'

            question_count = sum(len(g.get('questions', [])) for g in parsed['groups'])
            self.stdout.write(f'  Validated: {question_count} question(s) in {len(parsed["groups"])} group(s)')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  Error validating markdown: {str(e)}'))
            return 'error'

        # Check if template already exists
        title = metadata['title']
        try:
            existing = PublishedQuestionGroup.objects.get(
                name=title,
                publication_level='global'
            )

            # Check if content or metadata has changed
            content_changed = existing.markdown != markdown_content
            metadata_changed = (
                existing.description != metadata['description'] or
                existing.attribution != metadata['attribution'] or
                existing.tags != metadata.get('tags', [])
            )

            if not force and not content_changed and not metadata_changed:
                self.stdout.write(self.style.WARNING('  Skipping: Template unchanged'))
                return 'skipped'

            if dry_run:
                self.stdout.write(self.style.SUCCESS(f'  Would update: {title}'))
            else:
                # Update existing template
                existing.name = title
                existing.description = metadata['description']
                existing.attribution = metadata['attribution']
                existing.tags = metadata.get('tags', [])
                existing.markdown = markdown_content
                existing.version = metadata.get('version', '')
                existing.save()
                self.stdout.write(self.style.SUCCESS(f'  Updated: {title}'))

            return 'synced'

        except PublishedQuestionGroup.DoesNotExist:
            # Create new template
            if dry_run:
                self.stdout.write(self.style.SUCCESS(f'  Would create: {title}'))
            else:
                # Global templates need a publisher - use first superuser or create system user
                from django.contrib.auth import get_user_model
                User = get_user_model()
                admin_user = User.objects.filter(is_superuser=True).first()

                if not admin_user:
                    self.stdout.write(self.style.WARNING('  No superuser found, creating system user'))
                    admin_user, created = User.objects.get_or_create(
                        email='system@checktick.local',
                        defaults={
                            'first_name': 'System',
                            'is_active': False,  # Inactive system account
                        }
                    )

                PublishedQuestionGroup.objects.create(
                    name=title,
                    description=metadata['description'],
                    publication_level='global',
                    status='active',
                    attribution=metadata['attribution'],
                    tags=metadata.get('tags', []),
                    markdown=markdown_content,
                    version=metadata.get('version', ''),
                    publisher=admin_user,
                )
                self.stdout.write(self.style.SUCCESS(f'  Created: {title}'))

            return 'synced'
