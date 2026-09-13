from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
import unicodedata


class BulkParseError(Exception):
    pass


def _text_datetime_options(q: Dict[str, Any], fmt: str) -> List[Dict[str, Any]]:
    """Build the options dict for a date/time/datetime text question.

    Picks up optional ``min:``/``max:`` key-value lines (same style as
    ``likert number``). Invalid values are dropped rather than persisted.
    """
    from datetime import date as _date, datetime as _datetime, time as _time

    option: Dict[str, Any] = {"type": "text", "format": fmt}

    def _clean(raw: Any) -> Optional[str]:
        if not raw:
            return None
        value = str(raw).strip()
        if not value:
            return None
        try:
            if fmt == "date":
                return _date.fromisoformat(value[:10]).isoformat()
            if fmt == "time":
                return _time.fromisoformat(value).isoformat()
            return _datetime.fromisoformat(value).isoformat()
        except ValueError:
            return None

    lo = _clean(q.get("kv", {}).get("min"))
    hi = _clean(q.get("kv", {}).get("max"))
    if lo and hi:
        # Drop contradictory ranges entirely.
        try:
            if fmt == "date":
                bad = _date.fromisoformat(lo[:10]) > _date.fromisoformat(hi[:10])
            elif fmt == "time":
                bad = _time.fromisoformat(lo) > _time.fromisoformat(hi)
            else:
                bad = _datetime.fromisoformat(lo) > _datetime.fromisoformat(hi)
        except ValueError:
            bad = True
        if bad:
            return [option]
    if lo:
        option["min"] = lo
    if hi:
        option["max"] = hi
    return [option]


def parse_bulk_markdown(md_text: str) -> List[Dict[str, Any]]:
    """
    Parse markdown into groups and questions, capturing optional IDs and branching.

    Grammar additions compared to the original importer:
    - Group or question headings may end with `{custom-id}` to assign a stable reference.
      If omitted, a slugified identifier is generated automatically.
    - After the `(type)` line (and any options/likert metadata), branching lines may follow:
        `? when <operator> <value> -> {target-id}`
      Operators map to the SurveyQuestionCondition operators. Values may be quoted.
    """

    if not md_text or not md_text.strip():
        raise BulkParseError("Markdown is empty")

    # Import lazily to avoid Django model imports on module load in certain contexts
    from .models import SurveyQuestionCondition

    lines = md_text.splitlines()
    i = 0
    groups: List[Dict[str, Any]] = []
    current_group: Dict[str, Any] | None = None
    current_question: Dict[str, Any] | None = None
    all_refs: set[str] = set()

    def _normalize_token(value: str) -> str:
        base = (
            unicodedata.normalize("NFKD", (value or ""))
            .encode("ascii", "ignore")
            .decode("ascii")
        )
        base = re.sub(r"[^a-zA-Z0-9\s-]", " ", base).lower().strip()
        base = re.sub(r"[\s_-]+", "-", base).strip("-")
        return base

    def _allocate_ref(preferred: str | None, fallback: str) -> str:
        base = _normalize_token(preferred) if preferred else ""
        if not base:
            base = _normalize_token(fallback)
        candidate = base or fallback or "item"
        orig = candidate
        counter = 2
        while candidate in all_refs:
            candidate = f"{orig}-{counter}"
            counter += 1
        all_refs.add(candidate)
        return candidate

    def _extract_title_and_ref(raw_title: str, fallback: str) -> tuple[str, str]:
        title = raw_title
        explicit_ref = None
        match = re.search(r"\{([^{}]+)\}\s*$", title)
        if match:
            explicit_ref = match.group(1).strip()
            title = title[: match.start()].rstrip()
        title = title.strip()
        ref = _allocate_ref(explicit_ref, fallback)
        return title, ref

    def is_heading(s: str) -> bool:
        s_strip = s.lstrip()
        return s_strip.startswith("# ") or s_strip.startswith("## ")

    # Action keywords map to SurveyQuestionCondition.Action values.
    # The default (no keyword) is jump_to, preserving existing outlines.
    action_map = {
        "show": SurveyQuestionCondition.Action.SHOW,
        "hide": SurveyQuestionCondition.Action.HIDE,
        "end": SurveyQuestionCondition.Action.END_SURVEY,
        "jump_to": SurveyQuestionCondition.Action.JUMP_TO,
        "jump": SurveyQuestionCondition.Action.JUMP_TO,
    }

    def _parse_branch_line(line: str, line_number: int) -> Dict[str, Any]:
        # Target may be {question-id} or #section-name. The 'end' action has no target.
        section_match = re.search(r"#([A-Za-z0-9][\w\s-]*)\s*$", line)
        target_match = re.search(r"\{([^{}]+)\}\s*$", line)

        if not section_match and not target_match:
            # No target at all — only valid for the 'end' action.
            stripped = line.strip()
            # Check for an 'end when ...' line with no target.
            end_no_target = re.match(r"^end\s+when\s+.+$", stripped, re.IGNORECASE)
            if end_no_target:
                condition_part = re.sub(
                    r"^end\s+when\s+", "", stripped, flags=re.IGNORECASE
                )
                condition_part, operator, value, operator_key = _parse_condition_clause(
                    condition_part, line_number
                )
                description = f"end when {operator_key}"
                if value:
                    description = f"{description} {value}"
                return {
                    "operator": operator,
                    "value": value,
                    "description": description,
                    "target_ref": None,
                    "target_kind": None,
                    "action": SurveyQuestionCondition.Action.END_SURVEY,
                }
            raise BulkParseError(
                f"Branch is missing a target (use {{question-id}} or #section-name) "
                f"near line {line_number}, or use 'end when ...' to end the survey"
            )

        if section_match and target_match:
            raise BulkParseError(
                f"Branch has both a #section and a {{question}} target near line {line_number}"
            )

        if section_match:
            target_ref_raw = section_match.group(1).strip()
            target_ref = _normalize_token(target_ref_raw)
            if not target_ref:
                raise BulkParseError(
                    f"Branch section target cannot be empty near line {line_number}"
                )
            target_kind = "section"
            condition_part = line[: section_match.start()].strip()
        else:
            target_ref_raw = target_match.group(1).strip()  # type: ignore[union-attr]
            target_ref = _normalize_token(target_ref_raw)
            if not target_ref:
                raise BulkParseError(
                    f"Branch target id cannot be empty near line {line_number}"
                )
            target_kind = "question"
            condition_part = line[: target_match.start()].strip()  # type: ignore[union-attr]

        condition_part = re.sub(r"\s*->\s*$", "", condition_part)

        # Optional action keyword before 'when': show/hide/end/jump_to/jump.
        action = SurveyQuestionCondition.Action.JUMP_TO
        action_keyword_used = None
        kw_match = re.match(
            r"^(show|hide|end|jump_to|jump)\s+when\s+",
            condition_part,
            re.IGNORECASE,
        )
        if kw_match:
            action_keyword = kw_match.group(1).lower()
            action = action_map[action_keyword]
            action_keyword_used = action_keyword
            condition_part = condition_part[kw_match.end() :].strip()
        else:
            if condition_part.lower().startswith("when "):
                condition_part = condition_part[5:].strip()
            else:
                raise BulkParseError(
                    f"Branch must start with 'when' (or '<action> when') "
                    f"followed by an operator near line {line_number}"
                )

        condition_part, operator, value, operator_key = _parse_condition_clause(
            condition_part, line_number
        )

        # 'end' action must not have a target.
        if (
            action == SurveyQuestionCondition.Action.END_SURVEY
            and target_ref is not None
        ):
            raise BulkParseError(
                f"'end' action must not have a target near line {line_number}"
            )
        # show/hide cannot target a section.
        if (
            action
            in {
                SurveyQuestionCondition.Action.SHOW,
                SurveyQuestionCondition.Action.HIDE,
            }
            and target_kind == "section"
        ):
            raise BulkParseError(
                f"'{action_keyword_used}' action cannot target a section near line {line_number}; "
                f"only jump_to can target a section"
            )

        description = f"{action_keyword_used or 'jump_to'} when {operator_key}"
        if value:
            description = f"{description} {value}"

        return {
            "operator": operator,
            "value": value,
            "description": description,
            "target_ref": target_ref,
            "target_kind": target_kind,
            "action": action,
        }

    def _parse_condition_clause(
        condition_part: str, line_number: int
    ) -> tuple[str, Any, str, str]:
        """Parse the operator + value clause. Returns (clause, operator, value, operator_key)."""
        if not condition_part:
            raise BulkParseError(
                f"Branch is missing an operator near line {line_number}"
            )

        operator_tokens = condition_part.split(None, 1)
        operator_key = operator_tokens[0].replace("-", "_").lower()
        value_part = operator_tokens[1].strip() if len(operator_tokens) > 1 else ""

        operator_map = {
            "equals": SurveyQuestionCondition.Operator.EQUALS,
            "eq": SurveyQuestionCondition.Operator.EQUALS,
            "not_equals": SurveyQuestionCondition.Operator.NOT_EQUALS,
            "neq": SurveyQuestionCondition.Operator.NOT_EQUALS,
            "contains": SurveyQuestionCondition.Operator.CONTAINS,
            "not_contains": SurveyQuestionCondition.Operator.NOT_CONTAINS,
            "greater_than": SurveyQuestionCondition.Operator.GREATER_THAN,
            "gt": SurveyQuestionCondition.Operator.GREATER_THAN,
            "greater_equal": SurveyQuestionCondition.Operator.GREATER_EQUAL,
            "gte": SurveyQuestionCondition.Operator.GREATER_EQUAL,
            "less_than": SurveyQuestionCondition.Operator.LESS_THAN,
            "lt": SurveyQuestionCondition.Operator.LESS_THAN,
            "less_equal": SurveyQuestionCondition.Operator.LESS_EQUAL,
            "lte": SurveyQuestionCondition.Operator.LESS_EQUAL,
            "exists": SurveyQuestionCondition.Operator.EXISTS,
            "not_exists": SurveyQuestionCondition.Operator.NOT_EXISTS,
        }

        if operator_key not in operator_map:
            raise BulkParseError(
                f"Unsupported branch operator '{operator_key}' near line {line_number}"
            )

        operator = operator_map[operator_key]
        requires_value = operator not in {
            SurveyQuestionCondition.Operator.EXISTS,
            SurveyQuestionCondition.Operator.NOT_EXISTS,
        }

        if requires_value:
            if not value_part:
                raise BulkParseError(
                    f"Branch with operator '{operator_key}' requires a comparison value near line {line_number}"
                )
            value = _unquote_value(value_part)
        else:
            value = ""

        return condition_part, operator, value, operator_key

    while i < len(lines):
        raw = lines[i]
        line = raw.strip()
        if line.startswith("# ") and not line.startswith("## "):
            title_raw = line[2:].strip()
            title, ref = _extract_title_and_ref(title_raw, f"group-{len(groups) + 1}")
            desc = ""
            j = i + 1
            while j < len(lines) and lines[j].strip() == "":
                j += 1
            if j < len(lines) and not is_heading(lines[j]):
                desc = lines[j].strip()
                i = j
            current_group = {
                "name": title,
                "description": desc,
                "questions": [],
                "ref": ref,
            }
            groups.append(current_group)
            current_question = None
        elif line.startswith("## "):
            if not current_group:
                raise BulkParseError(
                    f"Question declared before any group at line {i+1}"
                )
            qtitle_raw = line[3:].strip()

            # Check for required indicator (trailing asterisk)
            # Note: Asterisk must come BEFORE any curly braces ID
            # e.g., "Title* {id}" or "Title*"
            is_required = False
            if qtitle_raw.endswith("*") or (
                "{" in qtitle_raw and qtitle_raw.split("{")[0].rstrip().endswith("*")
            ):
                is_required = True
                # Strip asterisk from before the ID if present
                if "{" in qtitle_raw and qtitle_raw.split("{")[0].rstrip().endswith(
                    "*"
                ):
                    parts = qtitle_raw.split("{")
                    parts[0] = parts[0].rstrip()[:-1].rstrip()
                    qtitle_raw = "{".join(parts)
                else:
                    qtitle_raw = qtitle_raw[:-1].strip()

            qtitle, qref = _extract_title_and_ref(
                qtitle_raw,
                f"{current_group['ref']}-{len(current_group['questions']) + 1}",
            )
            qdesc = ""
            j = i + 1
            while j < len(lines) and lines[j].strip() == "":
                j += 1
            if (
                j < len(lines)
                and not is_heading(lines[j])
                and not re.match(r"^\(.*\)$", lines[j].strip())
            ):
                qdesc = lines[j].strip()
                i = j
            k = i + 1
            while k < len(lines) and lines[k].strip() == "":
                k += 1
            if k >= len(lines) or not re.match(r"^\(.*\)$", lines[k].strip()):
                raise BulkParseError(
                    f"Missing (type) for question '{qtitle}' around line {i+1}"
                )
            type_line = lines[k].strip()[1:-1].strip().lower()
            i = k
            current_question = {
                "title": qtitle,
                "description": qdesc,
                "type": type_line,
                "options": [],
                "kv": {},
                "ref": qref,
                "branches": [],
                "required": is_required,
                "hidden_by_default": False,
            }
            current_group["questions"].append(current_question)
        else:
            if current_question:
                if line.startswith("? ") or line.startswith("?"):
                    branch = _parse_branch_line(line[1:].strip(), i + 1)
                    current_question["branches"].append(branch)
                elif line == "HIDDEN" or line.upper() == "HIDDEN":
                    current_question["hidden_by_default"] = True
                elif line.startswith("- "):
                    current_question["options"].append(line[2:].strip())
                elif line.startswith("+ "):
                    # Follow-up text for the most recent option
                    if current_question["options"]:
                        # Get the last option and mark it with follow-up metadata
                        last_idx = len(current_question["options"]) - 1
                        followup_label = line[2:].strip()
                        # Store follow-up as tuple (option_text, followup_label)
                        last_option = current_question["options"][last_idx]
                        # If it's already a tuple, update it; otherwise create tuple
                        if isinstance(last_option, tuple):
                            current_question["options"][last_idx] = (
                                last_option[0],
                                followup_label,
                            )
                        else:
                            current_question["options"][last_idx] = (
                                last_option,
                                followup_label,
                            )
                else:
                    m = re.match(
                        r"^(min|max|left|right|dataset|address_lookup)\s*:\s*(.*)$",
                        line,
                        re.IGNORECASE,
                    )
                    if m:
                        key = m.group(1).lower()
                        val = m.group(2).strip()
                        current_question["kv"][key] = val
            # else ignore stray text
        i += 1

    group_lookup = {g["ref"]: g for g in groups}
    question_lookup = {q["ref"]: q for g in groups for q in g["questions"]}

    def _convert_options_to_dicts(options_list):
        """Convert option list (strings or tuples) to dict format with follow-up support."""
        result = []
        for opt in options_list:
            if isinstance(opt, tuple):
                # (option_text, followup_label)
                opt_text, followup_label = opt
                result.append(
                    {
                        "label": opt_text,
                        "value": opt_text,
                        "followup_text": {"enabled": True, "label": followup_label},
                    }
                )
            else:
                # Simple string option
                result.append({"label": opt, "value": opt})
        return result

    for g in groups:
        if not g["name"]:
            raise BulkParseError("A group is missing a title")
        for q in g["questions"]:
            t = q["type"].lower()
            if t in {"text", "text free", "text freetext"}:
                q["final_type"] = "text"
                q["final_options"] = [{"type": "text", "format": "free"}]
            elif t in {"text number", "number", "numeric"}:
                q["final_type"] = "text"
                q["final_options"] = [{"type": "text", "format": "number"}]
            elif t in {"text date", "date"}:
                q["final_type"] = "text"
                q["final_options"] = _text_datetime_options(q, "date")
            elif t in {"text time", "time"}:
                q["final_type"] = "text"
                q["final_options"] = _text_datetime_options(q, "time")
            elif t in {"text datetime", "datetime", "date and time", "date/time"}:
                q["final_type"] = "text"
                q["final_options"] = _text_datetime_options(q, "datetime")
            elif t in {"mc_single", "single", "radio"}:
                q["final_type"] = "mc_single"
                q["final_options"] = _convert_options_to_dicts(q["options"])
            elif t in {"mc_multi", "multi", "checkbox"}:
                q["final_type"] = "mc_multi"
                q["final_options"] = _convert_options_to_dicts(q["options"])
            elif t in {"dropdown", "select"}:
                q["final_type"] = "dropdown"
                q["final_options"] = _convert_options_to_dicts(q["options"])
                if q["kv"].get("dataset"):
                    q["dataset_key"] = q["kv"]["dataset"].strip()
            elif t in {"orderable", "rank", "ranking"}:
                q["final_type"] = "orderable"
                q["final_options"] = _convert_options_to_dicts(q["options"])
            elif t in {"yesno", "yes/no", "boolean"}:
                q["final_type"] = "yesno"
                # YesNo can also have follow-up text
                yes_option: Dict[str, Any] = {"label": "Yes", "value": "yes"}
                no_option: Dict[str, Any] = {"label": "No", "value": "no"}
                # Plain option lines override the default display labels:
                # line 1 = yes label, line 2 = no label, line 3 = the optional
                # "Don't know" answer's label. Tuples carry follow-up labels.
                if len(q["options"]) >= 1:
                    opt = q["options"][0]
                    if isinstance(opt, tuple):
                        label = str(opt[0]).strip()
                        if label:
                            yes_option["label"] = label
                        yes_option["followup_text"] = {
                            "enabled": True,
                            "label": opt[1],
                        }
                    else:
                        # Plain option line overrides the default display label
                        label = str(opt).strip()
                        if label:
                            yes_option["label"] = label
                if len(q["options"]) >= 2:
                    opt = q["options"][1]
                    if isinstance(opt, tuple):
                        label = str(opt[0]).strip()
                        if label:
                            no_option["label"] = label
                        no_option["followup_text"] = {
                            "enabled": True,
                            "label": opt[1],
                        }
                    else:
                        label = str(opt).strip()
                        if label:
                            no_option["label"] = label
                q["final_options"] = [yes_option, no_option]
                # A third option line adds a "Don't know" answer (value
                # dont_know). A plain line overrides its default label; a
                # tuple (from a '+' follow-up line) also enables a follow-up.
                if len(q["options"]) >= 3:
                    opt = q["options"][2]
                    dontknow_option: Dict[str, Any] = {
                        "label": "Don't know",
                        "value": "dont_know",
                    }
                    if isinstance(opt, tuple):
                        label = str(opt[0]).strip()
                        if label:
                            dontknow_option["label"] = label
                        dontknow_option["followup_text"] = {
                            "enabled": True,
                            "label": opt[1],
                        }
                    else:
                        label = str(opt).strip()
                        if label:
                            dontknow_option["label"] = label
                    q["final_options"].append(dontknow_option)
            elif t in {"image", "image choice", "image-choice"}:
                q["final_type"] = "image"
                q["final_options"] = _convert_options_to_dicts(q["options"])
            elif t in {"long_text", "long text", "textarea", "paragraph"}:
                q["final_type"] = "long_text"
                q["final_options"] = []
            elif t in {
                "template_patient",
                "patient details",
                "patient_details",
                "patient template",
            }:
                q["final_type"] = "template_patient"
                # Field selection/defaults are filled in by the view normalizer
                # (_normalize_patient_template_options) at render time.
                q["final_options"] = {"template": "patient_details_encrypted"}
            elif t in {
                "template_professional",
                "professional details",
                "professional_details",
                "professional template",
            }:
                q["final_type"] = "template_professional"
                # Field selection/defaults are filled in by the view normalizer
                # (_normalize_professional_template_options) at render time.
                options: Dict[str, Any] = {"template": "professional_details"}
                if str(q["kv"].get("address_lookup", "")).strip().lower() in {
                    "true",
                    "yes",
                    "on",
                    "1",
                }:
                    options["address_lookup"] = True
                q["final_options"] = options
            elif t.startswith("likert"):
                if "categories" in t:
                    if not q["options"]:
                        raise BulkParseError(
                            f"Likert categories requires category lines for question '{q['title']}'"
                        )
                    q["final_type"] = "likert"
                    q["final_options"] = [
                        {"type": "categories", "labels": q["options"][:]}
                    ]
                else:

                    def _parse_int_kv(key: str, default: str) -> int:
                        raw = q["kv"].get(key, default)
                        # remove surrounding quotes and whitespace
                        raw = _unquote_value((raw or "")).strip()
                        # normalize common unicode minus to ascii hyphen
                        raw = raw.replace("\u2212", "-")
                        # allow integer strings like '1' or floats like '1.0'
                        if re.match(r"^[-+]?\d+$", raw):
                            return int(raw)
                        try:
                            f = float(raw)
                            if f.is_integer():
                                return int(f)
                        except Exception:
                            pass
                        raise BulkParseError(
                            f"Likert number requires integer min/max for question '{q['title']}'"
                        )

                    min_v = _parse_int_kv("min", "1")
                    max_v = _parse_int_kv("max", "5")
                    if min_v >= max_v:
                        raise BulkParseError(
                            f"Likert number min must be < max for question '{q['title']}'"
                        )
                    q["final_type"] = "likert"
                    q["final_options"] = [
                        {
                            "type": "number-scale",
                            "min": min_v,
                            "max": max_v,
                            "left_label": q["kv"].get("left", ""),
                            "right_label": q["kv"].get("right", ""),
                        }
                    ]
            else:
                raise BulkParseError(
                    f"Unsupported question type '{q['type']}' for '{q['title']}'"
                )

            validated_branches: List[Dict[str, Any]] = []
            for idx, branch in enumerate(q["branches"]):
                target_ref = branch["target_ref"]
                target_kind = branch.get("target_kind")
                action = branch.get("action", SurveyQuestionCondition.Action.JUMP_TO)

                # END_SURVEY has no target.
                if action == SurveyQuestionCondition.Action.END_SURVEY:
                    branch["target_type"] = None
                    branch["order"] = idx
                    validated_branches.append(branch)
                    continue

                # Resolve the target ref against groups and questions.
                if target_ref in group_lookup:
                    resolved_kind = "group"
                elif target_ref in question_lookup:
                    resolved_kind = "question"
                else:
                    raise BulkParseError(
                        f"Branch references unknown id '{target_ref}' in question '{q['title']}'"
                    )

                # If the parser declared a section target (#ref), it must resolve
                # to a group.
                if target_kind == "section" and resolved_kind != "group":
                    raise BulkParseError(
                        f"Branch target '#{target_ref}' is not a section in question '{q['title']}'"
                    )
                # A question target ({ref}) may resolve to either a question or
                # a group. The AI-output normalization wraps bare targets in
                # braces without knowing which kind they are, so {group-ref} is
                # a valid jump target (resolved to the group's first question
                # at import time). Only reject if the ref is genuinely unknown
                # (already caught above).

                branch["target_type"] = resolved_kind
                branch["order"] = idx
                validated_branches.append(branch)
            q["branches"] = validated_branches

    return groups


def _unquote_value(raw: str) -> str:
    if len(raw) >= 2 and (
        (raw.startswith('"') and raw.endswith('"'))
        or (raw.startswith("'") and raw.endswith("'"))
    ):
        return raw[1:-1]
    return raw


def parse_bulk_markdown_with_collections(md_text: str) -> Dict[str, Any]:
    """
    Parse markdown into groups/questions and detect simple REPEAT markers for collections.

    Rules:
    - A line (optionally prefixed by ">" for nesting) that equals "REPEAT" or "REPEAT-<N>"
      applies to the next group heading at the same nesting depth.
    - Nesting depth is the count of leading ">" characters before the REPEAT line and/or group heading.
    - REPEAT without a number means unlimited (no max); REPEAT-5 means max_count=5.

    Returns dict: {"groups": [...], "repeats": [{group_index, depth, max_count, parent_index} ...]}
    """
    if not md_text or not md_text.strip():
        raise BulkParseError("Markdown is empty")

    raw_lines = md_text.splitlines()

    # Normalize AI output: if branch lines use '-> target' without curly braces,
    # wrap the target in braces so the downstream parser can resolve it.
    def _slugify_target(value: str) -> str:
        import unicodedata

        base = (
            unicodedata.normalize("NFKD", (value or ""))
            .encode("ascii", "ignore")
            .decode("ascii")
        )
        base = re.sub(r"[^a-zA-Z0-9\s-]", " ", base).lower().strip()
        base = re.sub(r"[\s_-]+", "-", base).strip("-")
        return base or "target"

    normalized_lines: List[str] = []
    for raw in raw_lines:
        line = raw
        if "->" in line:
            parts = line.split("->", 1)
            left = parts[0]
            right = parts[1].strip()
            # If right already contains a brace-delimited id or a #section target, leave as-is
            if not (("{" in right and "}" in right) or right.startswith("#")):
                # Remove surrounding quotes if present
                if (right.startswith('"') and right.endswith('"')) or (
                    right.startswith("'") and right.endswith("'")
                ):
                    right = right[1:-1].strip()
                slug = _slugify_target(right)
                line = f"{left}-> {{{slug}}}"
        normalized_lines.append(line)

    raw_lines = normalized_lines
    cleaned_lines: List[str] = []
    pending_repeat: Dict[int, int | None] = {}  # depth -> max or None
    repeats: List[Dict[str, int | None]] = []
    import re as _re

    # Track a stack of the most recent repeated group indices at each depth
    repeat_stack: List[int] = []  # stores group_index at each depth
    group_count_seen = 0

    # SECTION_MENU block parsing (see docs/survey-layouts.md §Outline syntax).
    # The block appears before any group headings and contains only config
    # lines (prompt, min, max, order, etc.). The ``~ pickable`` suffix is
    # placed on the actual content group headings themselves, e.g.::
    #
    #     # Medical {medical}    ~ pickable, 5 min
    #
    # This avoids duplicate group headings and keeps the parser single-pass.
    section_menu: Dict[str, Any] | None = None
    in_section_menu_block = False
    # Map group name -> {is_pickable, estimated_minutes} collected from
    # ``~ pickable`` suffixes on content group headings.
    section_menu_items: Dict[str, Dict[str, Any]] = {}

    # RANDOMISED block parsing (see docs/survey-layouts-technical.md
    # §Randomised (RCT) layout §Outline grammar). Analogous to
    # SECTION_MENU: the block appears before any group headings and
    # contains only config lines (strategy, seed). The ``~ arm:<name>``
    # suffix is placed on the actual content group headings, e.g.::
    #
    #     # Intervention {intervention}    ~ arm:intervention
    #
    # A group may be in multiple arms: ``~ arm:intervention, arm:control``.
    randomised: Dict[str, Any] | None = None
    in_randomised_block = False
    # Map group name -> list of arm names collected from ``~ arm:`` suffixes.
    randomised_arm_items: Dict[str, List[str]] = {}
    # Ordered list of arm names seen in the outline (for arm creation order).
    randomised_arm_order: List[str] = []

    # STAGED block parsing (see docs/survey-layouts-technical.md §Staged
    # (longitudinal) layout §Outline grammar). Analogous to RANDOMISED: the
    # block appears before any group headings and contains only config lines
    # (anchor). The ``~ phase:<name>`` suffix is placed on the actual
    # content group headings, e.g.::
    #
    #     # Baseline {baseline}    ~ phase:baseline
    #
    # A group may be in multiple phases:
    # ``~ phase:baseline, phase:followup``.
    staged: Dict[str, Any] | None = None
    in_staged_block = False
    # Map group name -> list of phase names collected from ``~ phase:`` suffixes.
    staged_phase_items: Dict[str, List[str]] = {}
    # Ordered list of phase names seen in the outline (for phase creation order).
    staged_phase_order: List[str] = []
    # Map phase name -> {start_offset_days, end_offset_days} from the
    # optional ``phase:`` config lines in the STAGED block.
    staged_phase_windows: Dict[str, Dict[str, Any]] = {}

    # MATRIX block parsing (see docs/survey-layouts-technical.md §Matrix
    # (free navigation) layout §Outline grammar). Analogous to the other
    # layout blocks: appears before any group headings and contains only
    # config lines (prompt, order_mode, allow_revisit). No ``~`` suffixes
    # are needed — every section in the survey is a card on the matrix
    # landing page by default.
    matrix: Dict[str, Any] | None = None
    in_matrix_block = False

    for raw in raw_lines:
        # Count leading '>' as depth
        s = raw
        depth = 0
        i = 0
        while i < len(s):
            if s[i] == ">":
                depth += 1
                i += 1
                # optional space after '>'
                if i < len(s) and s[i] == " ":
                    i += 1
                continue
            elif s[i] == " ":
                # allow leading spaces between blockquotes
                i += 1
                continue
            break
        content = s[i:].rstrip()
        stripped = content.strip()

        # SECTION_MENU block start
        if _re.match(r"^SECTION_MENU$", stripped, flags=_re.IGNORECASE):
            in_section_menu_block = True
            section_menu = {
                "prompt_text": "Which sections would you like to complete?",
                "min_selected": 1,
                "max_selected": None,
                "order_mode": "authored",
                "show_select_all": False,
                "show_estimated_time": False,
            }
            continue

        # SECTION_MENU config lines (indented under the block header).
        if in_section_menu_block and (depth > 0 or raw[:1].isspace()):
            cfg_match = _re.match(r"^(\w+)\s*:\s*(.+)$", stripped)
            if cfg_match and section_menu is not None:
                key = cfg_match.group(1).lower()
                val_raw = cfg_match.group(2).strip()
                if (val_raw.startswith('"') and val_raw.endswith('"')) or (
                    val_raw.startswith("'") and val_raw.endswith("'")
                ):
                    val_raw = val_raw[1:-1]
                if key == "prompt":
                    section_menu["prompt_text"] = val_raw
                elif key == "min":
                    try:
                        section_menu["min_selected"] = int(val_raw)
                    except ValueError:
                        pass
                elif key == "max":
                    try:
                        section_menu["max_selected"] = int(val_raw) or None
                    except ValueError:
                        pass
                elif key == "order":
                    if val_raw in ("authored", "participant"):
                        section_menu["order_mode"] = val_raw
                elif key == "select_all":
                    section_menu["show_select_all"] = val_raw.lower() in (
                        "true",
                        "yes",
                        "on",
                    )
                elif key == "estimated_time":
                    section_menu["show_estimated_time"] = val_raw.lower() in (
                        "true",
                        "yes",
                        "on",
                    )
                continue
            # Blank line inside indented block — skip
            if not stripped:
                continue
            # Unknown indented line — skip
            continue

        # Blank line ends the SECTION_MENU config block
        if in_section_menu_block and not stripped:
            in_section_menu_block = False
            continue

        # Unknown non-indented line inside SECTION_MENU block also ends it
        if in_section_menu_block and depth == 0 and not raw[:1].isspace():
            in_section_menu_block = False
            # Fall through to regular parsing for this line

        # RANDOMISED block start (see docs/survey-layouts-technical.md
        # §Randomised (RCT) layout §Outline grammar).
        if _re.match(r"^RANDOMISED$", stripped, flags=_re.IGNORECASE):
            in_randomised_block = True
            randomised = {
                "allocation_strategy": "balanced",
                "seed": None,
            }
            continue

        # RANDOMISED config lines (indented under the block header).
        if in_randomised_block and (depth > 0 or raw[:1].isspace()):
            cfg_match = _re.match(r"^(\w+)\s*:\s*(.+)$", stripped)
            if cfg_match and randomised is not None:
                key = cfg_match.group(1).lower()
                val_raw = cfg_match.group(2).strip()
                if key == "strategy":
                    if val_raw in ("balanced", "simple"):
                        randomised["allocation_strategy"] = val_raw
                elif key == "seed":
                    try:
                        randomised["seed"] = int(val_raw)
                    except ValueError:
                        pass
                continue
            # Blank line inside indented block — skip
            if not stripped:
                continue
            continue

        # Blank line ends the RANDOMISED config block
        if in_randomised_block and not stripped:
            in_randomised_block = False
            continue

        # Unknown non-indented line inside RANDOMISED block also ends it
        if in_randomised_block and depth == 0 and not raw[:1].isspace():
            in_randomised_block = False
            # Fall through to regular parsing for this line

        # STAGED block start (see docs/survey-layouts-technical.md §Staged
        # (longitudinal) layout §Outline grammar).
        if _re.match(r"^STAGED$", stripped, flags=_re.IGNORECASE):
            in_staged_block = True
            staged = {
                "anchor": "enrolment",
            }
            continue

        # STAGED config lines (indented under the block header). Two forms:
        #   anchor: enrolment|survey_open
        #   phase <name>: <start> [.. <end>]   (day offsets; end optional)
        if in_staged_block and (depth > 0 or raw[:1].isspace()):
            cfg_match = _re.match(r"^(\w+)\s*:\s*(.+)$", stripped)
            if cfg_match and staged is not None:
                key = cfg_match.group(1).lower()
                val_raw = cfg_match.group(2).strip()
                if key == "anchor":
                    if val_raw in ("enrolment", "survey_open"):
                        staged["anchor"] = val_raw
                continue
            # Phase window definition: ``phase <name>: <start> [.. <end>]``.
            phase_match = _re.match(
                r"^phase\s+([\w\s-]+?)\s*:\s*(.+)$", stripped, flags=_re.IGNORECASE
            )
            if phase_match and staged is not None:
                pname = phase_match.group(1).strip()
                window_raw = phase_match.group(2).strip()
                # ``<start>`` or ``<start> .. <end>``.
                range_match = _re.match(r"^(\d+)\s*(?:\.\.)?\s*(\d*)$", window_raw)
                if range_match:
                    start_off = int(range_match.group(1))
                    end_off_raw = range_match.group(2)
                    end_off = int(end_off_raw) if end_off_raw else None
                    staged_phase_windows[pname] = {
                        "start_offset_days": start_off,
                        "end_offset_days": end_off,
                    }
                    if pname not in staged_phase_order:
                        staged_phase_order.append(pname)
                continue
            # Blank line inside indented block — skip
            if not stripped:
                continue
            continue

        # Blank line ends the STAGED config block
        if in_staged_block and not stripped:
            in_staged_block = False
            continue

        # Unknown non-indented line inside STAGED block also ends it
        if in_staged_block and depth == 0 and not raw[:1].isspace():
            in_staged_block = False
            # Fall through to regular parsing for this line

        # MATRIX block start (see docs/survey-layouts-technical.md §Matrix
        # (free navigation) layout §Outline grammar).
        if _re.match(r"^MATRIX$", stripped, flags=_re.IGNORECASE):
            in_matrix_block = True
            matrix = {
                "prompt_text": (
                    "Click a section to begin. You can complete them in any order."
                ),
                "order_mode": "authored",
                "allow_revisit": True,
            }
            continue

        # MATRIX config lines (indented under the block header).
        #   prompt: "<text>"
        #   order: authored|participant
        #   allow_revisit: true|false
        if in_matrix_block and (depth > 0 or raw[:1].isspace()):
            cfg_match = _re.match(r"^(\w+)\s*:\s*(.+)$", stripped)
            if cfg_match and matrix is not None:
                key = cfg_match.group(1).lower()
                val_raw = cfg_match.group(2).strip()
                if (val_raw.startswith('"') and val_raw.endswith('"')) or (
                    val_raw.startswith("'") and val_raw.endswith("'")
                ):
                    val_raw = val_raw[1:-1]
                if key == "prompt":
                    matrix["prompt_text"] = val_raw
                elif key == "order":
                    if val_raw in ("authored", "participant"):
                        matrix["order_mode"] = val_raw
                elif key == "allow_revisit":
                    matrix["allow_revisit"] = val_raw.lower() in (
                        "true",
                        "yes",
                        "on",
                    )
            continue

        # Blank line ends the MATRIX config block
        if in_matrix_block and not stripped:
            in_matrix_block = False
            continue

        # Unknown non-indented line inside MATRIX block also ends it
        if in_matrix_block and depth == 0 and not raw[:1].isspace():
            in_matrix_block = False
            # Fall through to regular parsing for this line

        # REPEAT marker?
        m = _re.match(r"^REPEAT(?:-(\d+))?$", content.strip(), flags=_re.IGNORECASE)
        if m:
            maxv = int(m.group(1)) if m.group(1) else None
            pending_repeat[depth] = maxv
            # do not include this line in cleaned markdown
            continue

        # Group heading detection (top-level groups only: '# ')
        if content.strip().startswith("# ") and not content.strip().startswith("## "):
            # Detect and strip ``~`` suffix (section_menu ``~ pickable`` or
            # RCT ``~ arm:<name>``). The suffix is recorded and stripped from
            # the heading before it reaches the regular parser.
            heading_content = content
            tilde_idx = heading_content.find("~")
            if tilde_idx != -1 and section_menu is not None:
                # ``~ pickable[, N min]`` for section_menu layout.
                suffix = heading_content[tilde_idx + 1 :].strip()
                heading_content = heading_content[:tilde_idx].rstrip()
                is_pickable = True
                estimated_minutes = None
                min_match = _re.search(r"(\d+)\s*min", suffix, flags=_re.IGNORECASE)
                if min_match:
                    estimated_minutes = int(min_match.group(1))
                # Extract group name from the cleaned heading
                heading_text = heading_content.strip()[2:]  # remove "# "
                ref_match = _re.search(r"\{([^{}]+)\}\s*$", heading_text)
                if ref_match:
                    heading_text = heading_text[: ref_match.start()].rstrip()
                section_menu_items[heading_text] = {
                    "is_pickable": is_pickable,
                    "estimated_minutes": estimated_minutes,
                }
                content = heading_content
            elif tilde_idx != -1 and randomised is not None:
                # ``~ arm:<name>[, arm:<name>...]`` for RCT layout.
                suffix = heading_content[tilde_idx + 1 :].strip()
                heading_content = heading_content[:tilde_idx].rstrip()
                # Extract all arm: tokens (comma-separated).
                arm_matches = _re.findall(
                    r"arm:([\w\s-]+?)\s*(?:,|$)", suffix, flags=_re.IGNORECASE
                )
                arm_names = [a.strip() for a in arm_matches if a.strip()]
                # Extract group name from the cleaned heading
                heading_text = heading_content.strip()[2:]  # remove "# "
                ref_match = _re.search(r"\{([^{}]+)\}\s*$", heading_text)
                if ref_match:
                    heading_text = heading_text[: ref_match.start()].rstrip()
                randomised_arm_items[heading_text] = arm_names
                for an in arm_names:
                    if an not in randomised_arm_order:
                        randomised_arm_order.append(an)
                content = heading_content
            elif tilde_idx != -1 and staged is not None:
                # ``~ phase:<name>[, phase:<name>...]`` for staged layout.
                suffix = heading_content[tilde_idx + 1 :].strip()
                heading_content = heading_content[:tilde_idx].rstrip()
                # Extract all phase: tokens (comma-separated).
                phase_matches = _re.findall(
                    r"phase:([\w\s-]+?)\s*(?:,|$)", suffix, flags=_re.IGNORECASE
                )
                phase_names = [p.strip() for p in phase_matches if p.strip()]
                # Extract group name from the cleaned heading
                heading_text = heading_content.strip()[2:]  # remove "# "
                ref_match = _re.search(r"\{([^{}]+)\}\s*$", heading_text)
                if ref_match:
                    heading_text = heading_text[: ref_match.start()].rstrip()
                staged_phase_items[heading_text] = phase_names
                for pn in phase_names:
                    if pn not in staged_phase_order:
                        staged_phase_order.append(pn)
                content = heading_content
            elif section_menu is not None:
                # Group without ~ suffix under section_menu → mandatory
                heading_text = content.strip()[2:]
                ref_match = _re.search(r"\{([^{}]+)\}\s*$", heading_text)
                if ref_match:
                    heading_text = heading_text[: ref_match.start()].rstrip()
                section_menu_items[heading_text] = {
                    "is_pickable": False,
                    "estimated_minutes": None,
                }
            elif randomised is not None:
                # Group without ~ suffix under RANDOMISED → reachable by all
                # arms (the union of all arm group sets). Record as empty list
                # so the bulk upload view knows it was seen under the block.
                heading_text = content.strip()[2:]
                ref_match = _re.search(r"\{([^{}]+)\}\s*$", heading_text)
                if ref_match:
                    heading_text = heading_text[: ref_match.start()].rstrip()
                randomised_arm_items[heading_text] = []  # all arms
            elif staged is not None:
                # Group without ~ suffix under STAGED → not in any phase
                # (unreachable; the Organise-page warnings flag this).
                heading_text = content.strip()[2:]
                ref_match = _re.search(r"\{([^{}]+)\}\s*$", heading_text)
                if ref_match:
                    heading_text = heading_text[: ref_match.start()].rstrip()
                staged_phase_items[heading_text] = []  # no phases
            # Trim or expand repeat_stack to current depth
            while len(repeat_stack) > depth:
                repeat_stack.pop()
            # add cleaned heading line (without blockquote)
            cleaned_lines.append(content)
            # If a repeat is pending at this depth, register it for this group index
            if depth in pending_repeat:
                parent_index = repeat_stack[-1] if repeat_stack else None
                repeats.append(
                    {
                        "group_index": group_count_seen,
                        "depth": depth,
                        "max_count": pending_repeat[depth],
                        "parent_index": parent_index,
                    }
                )
                # Update stack: this group becomes the latest repeated group at this depth
                repeat_stack.append(group_count_seen)
                del pending_repeat[depth]
            else:
                # non-repeated group at this depth trims deeper stack but doesn't extend
                pass
            group_count_seen += 1
            continue

        # For all other lines, strip blockquote markers for parsing and include
        cleaned_lines.append(content)

    cleaned_md = "\n".join(cleaned_lines)
    groups = parse_bulk_markdown(cleaned_md)

    # Apply section_menu item flags to parsed groups by name.
    if section_menu is not None and section_menu_items:
        for g in groups:
            item_info = section_menu_items.get(g["name"])
            if item_info:
                g["section_menu_pickable"] = item_info["is_pickable"]
                g["section_menu_estimated_minutes"] = item_info["estimated_minutes"]
            else:
                # Groups not listed in the SECTION_MENU block default to
                # mandatory (is_pickable=False).
                g["section_menu_pickable"] = False
                g["section_menu_estimated_minutes"] = None

    # Apply randomised arm items to parsed groups by name.
    if randomised is not None:
        randomised["arm_order"] = randomised_arm_order
        for g in groups:
            arm_names = randomised_arm_items.get(g["name"])
            if arm_names is not None:
                g["randomised_arms"] = arm_names
            else:
                # Groups not in the RANDOMISED block default to all arms.
                g["randomised_arms"] = []

    # Apply staged phase items to parsed groups by name.
    if staged is not None:
        staged["phase_order"] = staged_phase_order
        staged["phase_windows"] = staged_phase_windows
        for g in groups:
            phase_names = staged_phase_items.get(g["name"])
            if phase_names is not None:
                g["staged_phases"] = phase_names
            else:
                # Groups not in the STAGED block default to no phases
                # (unreachable; warned on the Organise page).
                g["staged_phases"] = []

    return {
        "groups": groups,
        "repeats": repeats,
        "section_menu": section_menu,
        "randomised": randomised,
        "staged": staged,
        "matrix": matrix,
    }
