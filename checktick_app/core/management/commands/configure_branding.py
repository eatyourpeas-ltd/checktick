"""Management command to configure site branding from the CLI.

This command is primarily intended for self-hosted deployments where
administrators can configure branding without using the web UI.

For hosted SaaS deployments, Enterprise tier users should use the
web UI at /branding/ instead.
"""

from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from checktick_app.core.models import SiteBranding


class Command(BaseCommand):
    help = "Configure site branding (themes, logos, fonts) from command line"

    def add_arguments(self, parser):
        parser.add_argument(
            "--theme",
            type=str,
            help="Default theme: checktick-light or checktick-dark",
        )
        parser.add_argument(
            "--theme-light",
            type=str,
            help="DaisyUI preset for light mode (e.g., nord, cupcake, light)",
        )
        parser.add_argument(
            "--theme-dark",
            type=str,
            help="DaisyUI preset for dark mode (e.g., business, dark, synthwave)",
        )
        parser.add_argument(
            "--logo",
            type=str,
            help="Path to logo file for light mode",
        )
        parser.add_argument(
            "--logo-dark",
            type=str,
            help="Path to logo file for dark mode",
        )
        parser.add_argument(
            "--logo-url",
            type=str,
            help="URL to logo image for light mode",
        )
        parser.add_argument(
            "--logo-url-dark",
            type=str,
            help="URL to logo image for dark mode",
        )
        parser.add_argument(
            "--font-heading",
            type=str,
            help="CSS font family for headings (e.g., 'Roboto', sans-serif)",
        )
        parser.add_argument(
            "--font-body",
            type=str,
            help="CSS font family for body text (e.g., 'Open Sans', sans-serif)",
        )
        parser.add_argument(
            "--font-css-url",
            type=str,
            help="URL to font CSS (e.g., Google Fonts URL)",
        )
        parser.add_argument(
            "--show",
            action="store_true",
            help="Show current branding configuration",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Reset branding to defaults",
        )

    def handle(self, *args, **options):
        # Get or create singleton branding instance
        branding, created = SiteBranding.objects.get_or_create(pk=1)

        if created:
            self.stdout.write(
                self.style.SUCCESS("Created new SiteBranding configuration")
            )

        # Show current configuration
        if options["show"]:
            self.show_current_branding(branding)
            return

        # Reset to defaults
        if options["reset"]:
            self.reset_branding(branding)
            return

        # Track if any changes were made
        changes_made = False

        # Update theme settings
        if options["theme"]:
            if options["theme"] not in ["checktick-light", "checktick-dark"]:
                raise CommandError(
                    "Invalid theme. Must be 'checktick-light' or 'checktick-dark'"
                )
            branding.default_theme = options["theme"]
            changes_made = True
            self.stdout.write(f"  Setting default theme: {options['theme']}")

        if options["theme_light"]:
            branding.theme_preset_light = options["theme_light"]
            changes_made = True
            self.stdout.write(f"  Setting light theme preset: {options['theme_light']}")

        if options["theme_dark"]:
            branding.theme_preset_dark = options["theme_dark"]
            changes_made = True
            self.stdout.write(f"  Setting dark theme preset: {options['theme_dark']}")

        # Update logo files
        if options["logo"]:
            logo_path = Path(options["logo"])
            if not logo_path.exists():
                raise CommandError(f"Logo file not found: {logo_path}")

            with open(logo_path, "rb") as f:
                branding.icon_file.save(logo_path.name, File(f), save=False)
            changes_made = True
            self.stdout.write(f"  Uploaded logo: {logo_path.name}")

        if options["logo_dark"]:
            logo_dark_path = Path(options["logo_dark"])
            if not logo_dark_path.exists():
                raise CommandError(f"Logo file not found: {logo_dark_path}")

            with open(logo_dark_path, "rb") as f:
                branding.icon_file_dark.save(logo_dark_path.name, File(f), save=False)
            changes_made = True
            self.stdout.write(f"  Uploaded dark logo: {logo_dark_path.name}")

        # Update logo URLs
        if options["logo_url"]:
            branding.icon_url = options["logo_url"]
            changes_made = True
            self.stdout.write(f"  Setting logo URL: {options['logo_url']}")

        if options["logo_url_dark"]:
            branding.icon_url_dark = options["logo_url_dark"]
            changes_made = True
            self.stdout.write(f"  Setting dark logo URL: {options['logo_url_dark']}")

        # Update font settings
        if options["font_heading"]:
            branding.font_heading = options["font_heading"]
            changes_made = True
            self.stdout.write(f"  Setting heading font: {options['font_heading']}")

        if options["font_body"]:
            branding.font_body = options["font_body"]
            changes_made = True
            self.stdout.write(f"  Setting body font: {options['font_body']}")

        if options["font_css_url"]:
            branding.font_css_url = options["font_css_url"]
            changes_made = True
            self.stdout.write(f"  Setting font CSS URL: {options['font_css_url']}")

        # Save changes
        if changes_made:
            branding.save()
            self.stdout.write(
                self.style.SUCCESS("\nBranding configuration updated successfully!")
            )
            self.stdout.write("\nCurrent configuration:")
            self.show_current_branding(branding)
        else:
            self.stdout.write(
                self.style.WARNING(
                    "No changes specified. Use --help to see available options."
                )
            )

    def show_current_branding(self, branding):
        """Display current branding configuration."""
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("Current Branding Configuration"))
        self.stdout.write("=" * 60)

        self.stdout.write("\nTheme Settings:")
        self.stdout.write(f"  Default Theme: {branding.default_theme}")
        self.stdout.write(
            f"  Light Preset: {branding.theme_preset_light or '(not set)'}"
        )
        self.stdout.write(f"  Dark Preset: {branding.theme_preset_dark or '(not set)'}")

        self.stdout.write("\nLogo Settings:")
        if branding.icon_file:
            self.stdout.write(f"  Logo File: {branding.icon_file.url}")
        else:
            self.stdout.write("  Logo File: (not set)")

        if branding.icon_file_dark:
            self.stdout.write(f"  Dark Logo File: {branding.icon_file_dark.url}")
        else:
            self.stdout.write("  Dark Logo File: (not set)")

        self.stdout.write(f"  Logo URL: {branding.icon_url or '(not set)'}")
        self.stdout.write(f"  Dark Logo URL: {branding.icon_url_dark or '(not set)'}")

        self.stdout.write("\nTypography:")
        self.stdout.write(f"  Heading Font: {branding.font_heading or '(not set)'}")
        self.stdout.write(f"  Body Font: {branding.font_body or '(not set)'}")
        self.stdout.write(f"  Font CSS URL: {branding.font_css_url or '(not set)'}")

        self.stdout.write(f"\nLast Updated: {branding.updated_at}")
        self.stdout.write("=" * 60 + "\n")

    def reset_branding(self, branding):
        """Reset branding to default values."""
        self.stdout.write(
            self.style.WARNING("Resetting branding configuration to defaults...")
        )

        branding.default_theme = "checktick-light"
        branding.theme_preset_light = ""
        branding.theme_preset_dark = ""
        branding.icon_file = None
        branding.icon_file_dark = None
        branding.icon_url = ""
        branding.icon_url_dark = ""
        branding.font_heading = ""
        branding.font_body = ""
        branding.font_css_url = ""
        branding.theme_light_css = ""
        branding.theme_dark_css = ""
        branding.save()

        self.stdout.write(
            self.style.SUCCESS("Branding configuration reset to defaults!")
        )
        self.show_current_branding(branding)
