from __future__ import annotations

import re
from typing import Any, Dict, List
import unicodedata


class BulkParseError(Exception):
    pass


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
                        r"^(min|max|left|right|dataset)\s*:\s*(.*)$",
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
                # Check if options were provided for yes/no (unusual but supported)
                if len(q["options"]) >= 1:
                    opt = q["options"][0]
                    if isinstance(opt, tuple):
                        yes_option["followup_text"] = {"enabled": True, "label": opt[1]}
                if len(q["options"]) >= 2:
                    opt = q["options"][1]
                    if isinstance(opt, tuple):
                        no_option["followup_text"] = {"enabled": True, "label": opt[1]}
                q["final_options"] = [yes_option, no_option]
            elif t in {"image", "image choice", "image-choice"}:
                q["final_type"] = "image"
                q["final_options"] = _convert_options_to_dicts(q["options"])
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

        # REPEAT marker?
        m = _re.match(r"^REPEAT(?:-(\d+))?$", content.strip(), flags=_re.IGNORECASE)
        if m:
            maxv = int(m.group(1)) if m.group(1) else None
            pending_repeat[depth] = maxv
            # do not include this line in cleaned markdown
            continue

        # Group heading detection (top-level groups only: '# ')
        if content.strip().startswith("# ") and not content.strip().startswith("## "):
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
    return {"groups": groups, "repeats": repeats}
