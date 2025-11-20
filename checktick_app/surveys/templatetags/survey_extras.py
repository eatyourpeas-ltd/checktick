import json

from django import template

register = template.Library()


@register.filter(name="dict_get")
def dict_get(d, key):
    """Safely get a value from a dict-like using a dynamic key in templates.

    Usage in templates:
        {{ mydict|dict_get:key }}
    """
    try:
        if d is None:
            return ""
        # Prefer mapping .get to avoid KeyError; fallback to [] if needed
        return d.get(key, "") if hasattr(d, "get") else d[key]
    except Exception:
        return ""


@register.filter(name="get_item")
def get_item(d, key):
    """Alias of dict_get but preserves objects when present.

    Useful in templates: {% with info=repeat_info|get_item:g.id %}
    """
    try:
        if d is None:
            return None
        return d.get(key) if hasattr(d, "get") else d[key]
    except Exception:
        return None


@register.simple_tag
def int_range(start: int, end: int):
    """Return a Python range inclusive of both start and end for template loops.

    Example:
      {% int_range 1 10 as nums %}
      {% for n in nums %} ... {% endfor %}
    """
    try:
        s = int(start)
        e = int(end)
        if e < s:
            s, e = e, s
        return range(s, e + 1)
    except Exception:
        return range(0)


@register.filter(name="as_list")
def as_list(value):
    """Normalize a value to a list for template iteration.

    - If it's already a list, return as-is
    - If it's a dict and has a 'values' key, return that
    - If it's a JSON string representing a list or dict, parse accordingly
    - Otherwise, return an empty list
    """
    try:
        if isinstance(value, list):
            # Unwrap common wrapper: a single dict that contains a list under a known key
            if len(value) == 1 and isinstance(value[0], dict):
                first = value[0]
                if "labels" in first and isinstance(first["labels"], list):
                    return first["labels"]
                if "values" in first and isinstance(first["values"], list):
                    return first["values"]
                if "options" in first and isinstance(first["options"], list):
                    return first["options"]
                if "categories" in first and isinstance(first["categories"], list):
                    return first["categories"]
            return value
        if isinstance(value, dict):
            # Direct wrappers
            if "labels" in value and isinstance(value["labels"], list):
                return value["labels"]
            if "values" in value and isinstance(value["values"], list):
                return value["values"]
            # Sometimes options may be wrapped under 'options'
            if "options" in value and isinstance(value["options"], list):
                return value["options"]
            # Support 'categories' wrapper
            if "categories" in value and isinstance(value["categories"], list):
                return value["categories"]
            return []
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    # Unwrap single-dict wrapper if present
                    if len(parsed) == 1 and isinstance(parsed[0], dict):
                        first = parsed[0]
                        if "labels" in first and isinstance(first["labels"], list):
                            return first["labels"]
                        if "values" in first and isinstance(first["values"], list):
                            return first["values"]
                        if "options" in first and isinstance(first["options"], list):
                            return first["options"]
                        if "categories" in first and isinstance(
                            first["categories"], list
                        ):
                            return first["categories"]
                    return parsed
                if isinstance(parsed, dict):
                    if "labels" in parsed and isinstance(parsed["labels"], list):
                        return parsed["labels"]
                    if "values" in parsed and isinstance(parsed["values"], list):
                        return parsed["values"]
                    if "options" in parsed and isinstance(parsed["options"], list):
                        return parsed["options"]
                    if "categories" in parsed and isinstance(
                        parsed["categories"], list
                    ):
                        return parsed["categories"]
                return []
            except Exception:
                return []
    except Exception:
        return []
    return []


@register.filter(name="option_label")
def option_label(opt):
    """Return a human label for an option that may be a string/number/dict.

    Dict precedence: 'label' > 'text' > 'name' > 'value'
    """
    try:
        if isinstance(opt, (str, int, float)):
            return str(opt)
        if isinstance(opt, dict):
            for k in ("label", "text", "name", "value"):
                if k in opt and opt[k] is not None:
                    return str(opt[k])
    except Exception:
        pass
    return ""


@register.filter(name="option_value")
def option_value(opt):
    """Return a value for an option. Defaults to the label when missing."""
    try:
        if isinstance(opt, (str, int, float)):
            return str(opt)
        if isinstance(opt, dict):
            if "value" in opt and opt["value"] is not None:
                return str(opt["value"])
            # fallback to label-like fields
            return option_label(opt)
    except Exception:
        pass
    return ""


@register.filter(name="options_meta")
def options_meta(value):
    """Return a metadata dict for options.

    - If value is a list and first item is a dict, return that first dict
    - If value is a dict, return as-is
    - If value is a JSON string, parse then apply the above
    - Else return empty dict
    """

    try:
        if isinstance(value, list):
            if value and isinstance(value[0], dict):
                return value[0]
            return {}
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    if parsed and isinstance(parsed[0], dict):
                        return parsed[0]
                    return {}
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                return {}
    except Exception:
        return {}
    return {}


@register.filter(name="has_followup")
def has_followup(question):
    """Check if a question has follow-up text inputs configured.

    Returns a list of tuples (option_label, followup_label) for display.
    """
    try:
        if not hasattr(question, "type") or not hasattr(question, "options"):
            return []

        qtype = question.type
        options = question.options

        # Only these types support follow-up text
        if qtype not in ("mc_single", "mc_multi", "dropdown", "orderable", "yesno"):
            return []

        followups = []

        if isinstance(options, list):
            for opt in options:
                if isinstance(opt, dict):
                    # Check for followup_text config
                    if (
                        "followup_text" in opt
                        and isinstance(opt["followup_text"], dict)
                        and opt["followup_text"].get("enabled")
                    ):
                        opt_label = option_label(opt)
                        followup_label = opt["followup_text"].get(
                            "label", "Please elaborate"
                        )
                        followups.append((opt_label, followup_label))

        return followups
    except Exception:
        return []


@register.filter(name="language_flag")
def language_flag(language_code):
    """Return flag emoji for language code."""
    flags = {
        "en": "🇬🇧",
        "es": "🇪🇸",
        "fr": "🇫🇷",
        "de": "🇩🇪",
        "it": "🇮🇹",
        "pt": "🇵🇹",
        "ar": "🇸🇦",
        "zh-hans": "🇨🇳",
        "hi": "🇮🇳",
        "ur": "🇵🇰",
        "cy": "🏴󠁧󠁢󠁷󠁬󠁳󠁿",
        "pl": "🇵🇱",
    }
    return flags.get(language_code, "🌐")


@register.filter(name="language_name")
def language_name(language_code):
    """Return language name for language code."""
    from checktick_app.surveys.models import Survey

    lang_dict = dict(Survey.SUPPORTED_SURVEY_LANGUAGES)
    return lang_dict.get(language_code, language_code)
