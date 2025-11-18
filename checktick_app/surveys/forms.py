from django import forms

from .models import PublishedQuestionGroup


class PublishQuestionGroupForm(forms.ModelForm):
    """Form for publishing a QuestionGroup as a template."""

    class Meta:
        model = PublishedQuestionGroup
        fields = [
            "publication_level",
            "name",
            "description",
            "tags",
            "language",
            "version",
            "attribution",
            "show_publisher_credit",
        ]
        widgets = {
            "publication_level": forms.RadioSelect,
            "description": forms.Textarea(attrs={"rows": 3}),
            "tags": forms.HiddenInput(),  # Will use custom JS tag input
            "attribution": forms.HiddenInput(),  # Will use custom JS form
        }
        labels = {
            "show_publisher_credit": "Show my name in template listings",
        }
        help_texts = {
            "show_publisher_credit": "If checked, your name and organization (if applicable) will be shown as the publisher. Uncheck for anonymous publication.",
        }

    # Attribution fields (not in model, used for UI)
    authors_json = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
        help_text="Authors as JSON array",
    )
    citation = forms.CharField(
        required=False,
        max_length=1000,
        widget=forms.Textarea(attrs={"rows": 2}),
        label="Citation",
    )
    pmid = forms.CharField(required=False, max_length=50, label="PMID")
    doi = forms.CharField(required=False, max_length=200, label="DOI")
    license = forms.CharField(required=False, max_length=200, label="License")
    year = forms.IntegerField(required=False, label="Year")

    def __init__(self, *args, user=None, question_group=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.question_group = question_group

        # Limit publication level choices based on user permissions
        if question_group and question_group.organization:
            # Organization group - can publish to org or global
            choices = [
                (
                    PublishedQuestionGroup.PublicationLevel.ORGANIZATION,
                    f"Organization ({question_group.organization.name})",
                ),
                (PublishedQuestionGroup.PublicationLevel.GLOBAL, "Global (all users)"),
            ]
        else:
            # Individual group - can only publish globally
            choices = [
                (PublishedQuestionGroup.PublicationLevel.GLOBAL, "Global (all users)")
            ]

        self.fields["publication_level"].choices = choices
        self.fields["publication_level"].initial = choices[0][0]

        # Pre-fill name and description from source group
        if question_group and not self.instance.pk:
            self.fields["name"].initial = question_group.name
            self.fields["description"].initial = question_group.description

    def clean_publication_level(self):
        level = self.cleaned_data["publication_level"]

        # Verify user has permission for this level
        if self.user and self.question_group:
            from .permissions import can_publish_question_group

            if not can_publish_question_group(self.user, self.question_group, level):
                raise forms.ValidationError(
                    "You do not have permission to publish at this level."
                )

        return level

    def clean_tags(self):
        """Parse tags from JSON string."""
        tags_str = self.cleaned_data.get("tags")
        if not tags_str:
            return []

        import json

        try:
            tags = json.loads(tags_str) if isinstance(tags_str, str) else tags_str
            if not isinstance(tags, list):
                return []
            # Validate and clean tags
            cleaned_tags = []
            for tag in tags[:10]:  # Max 10 tags
                if isinstance(tag, str) and len(tag) <= 50:
                    # Lowercase, alphanumeric + hyphens only
                    clean_tag = "".join(
                        c.lower() if c.isalnum() or c == "-" else "-" for c in tag
                    ).strip("-")
                    if clean_tag:
                        cleaned_tags.append(clean_tag)
            return cleaned_tags
        except (json.JSONDecodeError, TypeError):
            return []

    def clean(self):
        cleaned_data = super().clean()

        # Build attribution JSON from individual fields
        attribution = {}

        # Parse authors
        authors_json = self.cleaned_data.get("authors_json")
        if authors_json:
            import json

            try:
                authors = (
                    json.loads(authors_json)
                    if isinstance(authors_json, str)
                    else authors_json
                )
                if isinstance(authors, list):
                    attribution["authors"] = authors
            except json.JSONDecodeError:
                pass

        # Add other attribution fields
        if self.cleaned_data.get("citation"):
            attribution["citation"] = self.cleaned_data["citation"]
        if self.cleaned_data.get("pmid"):
            attribution["pmid"] = self.cleaned_data["pmid"]
        if self.cleaned_data.get("doi"):
            attribution["doi"] = self.cleaned_data["doi"]
        if self.cleaned_data.get("license"):
            attribution["license"] = self.cleaned_data["license"]
        if self.cleaned_data.get("year"):
            attribution["year"] = self.cleaned_data["year"]

        cleaned_data["attribution"] = attribution

        return cleaned_data
