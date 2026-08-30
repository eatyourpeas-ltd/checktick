"""Survey branching logic evaluation."""

from typing import Any

from .models import SurveyQuestion, SurveyQuestionCondition


def resolved_question_order(survey) -> list[int]:
    """Return question IDs in the resolved runtime order.

    Mirrors the ordering pipeline in ``views.py``
    (``_resolved_group_order_ids`` + ``_order_questions_by_group``) so that
    ``SurveyQuestionCondition.clean()`` can validate forward-only jumps without
    importing from views (which would create a circular dependency).
    """
    groups = list(survey.question_groups.only("id", "name").all())
    groups_map = {g.id: g for g in groups}

    style = survey.style or {}
    raw_order = style.get("group_order", [])
    explicit_ids: list[int] = []
    if isinstance(raw_order, list):
        for gid in raw_order:
            if str(gid).isdigit():
                gid_int = int(gid)
                if gid_int in groups_map and gid_int not in explicit_ids:
                    explicit_ids.append(gid_int)

    remaining = sorted(
        (g for g in groups if g.id not in explicit_ids),
        key=lambda g: ((g.name or "").lower(), g.id),
    )
    group_order = explicit_ids + [g.id for g in remaining]

    questions = list(survey.questions.all())
    grouped: dict[int | None, list[SurveyQuestion]] = {}
    ungrouped: list[SurveyQuestion] = []
    for q in questions:
        if q.group_id:
            grouped.setdefault(q.group_id, []).append(q)
        else:
            ungrouped.append(q)

    for gid in grouped:
        grouped[gid].sort(key=lambda q: (q.order, q.id))

    ordered: list[SurveyQuestion] = []
    for gid in group_order:
        if gid in grouped:
            ordered.extend(grouped[gid])
            del grouped[gid]

    # Orphaned group refs (group was deleted but questions still reference it)
    for gid in sorted(grouped.keys()):
        ordered.extend(grouped[gid])

    ungrouped.sort(key=lambda q: (q.order, q.id))
    ordered.extend(ungrouped)

    return [q.id for q in ordered]


def evaluate_condition(condition: SurveyQuestionCondition, answer: Any) -> bool:
    """
    Evaluate whether a condition is met based on the user's answer.

    Args:
        condition: The condition to evaluate
        answer: The user's answer to the question

    Returns:
        True if the condition is met, False otherwise
    """
    # Handle empty/missing answers
    if answer is None or answer == "" or answer == []:
        has_answer = False
    else:
        has_answer = True

    # Operators that don't require a value
    if condition.operator == SurveyQuestionCondition.Operator.EXISTS:
        return has_answer
    elif condition.operator == SurveyQuestionCondition.Operator.NOT_EXISTS:
        return not has_answer

    # All other operators require an answer to compare against
    if not has_answer:
        return False

    # Convert answer to string for comparison
    # Handle multiple choice (list) by joining
    if isinstance(answer, list):
        answer_str = ",".join(str(a) for a in answer)
    else:
        answer_str = str(answer)

    value = condition.value or ""

    # String comparisons (case-insensitive)
    if condition.operator == SurveyQuestionCondition.Operator.EQUALS:
        return answer_str.lower().strip() == value.lower().strip()
    elif condition.operator == SurveyQuestionCondition.Operator.NOT_EQUALS:
        return answer_str.lower().strip() != value.lower().strip()
    elif condition.operator == SurveyQuestionCondition.Operator.CONTAINS:
        return value.lower() in answer_str.lower()
    elif condition.operator == SurveyQuestionCondition.Operator.NOT_CONTAINS:
        return value.lower() not in answer_str.lower()

    # Numeric comparisons
    try:
        answer_num = float(answer_str)
        value_num = float(value)

        if condition.operator == SurveyQuestionCondition.Operator.GREATER_THAN:
            return answer_num > value_num
        elif condition.operator == SurveyQuestionCondition.Operator.GREATER_EQUAL:
            return answer_num >= value_num
        elif condition.operator == SurveyQuestionCondition.Operator.LESS_THAN:
            return answer_num < value_num
        elif condition.operator == SurveyQuestionCondition.Operator.LESS_EQUAL:
            return answer_num <= value_num
    except (ValueError, TypeError):
        # If conversion fails, comparison fails
        return False

    return False


def get_visible_questions(
    all_questions: list[SurveyQuestion], answers: dict[str, Any]
) -> tuple[list[SurveyQuestion], bool]:
    """
    Determine which questions should be visible based on branching logic.

    Args:
        all_questions: All questions in the survey (in order)
        answers: Dictionary mapping question IDs to answers

    Returns:
        Tuple of (visible_questions, survey_ended)
        - visible_questions: List of questions that should be shown
        - survey_ended: True if END_SURVEY condition was triggered
    """
    visible = []
    survey_ended = False
    skip_until_idx = None  # Used for JUMP_TO logic
    hidden_targets: set[int] = set()  # Question IDs hidden by HIDE conditions

    for idx, question in enumerate(all_questions):
        question_id = str(question.id)

        # If we're in a skip mode (from JUMP_TO), check if we've reached the target
        if skip_until_idx is not None:
            if idx < skip_until_idx:
                continue  # Skip this question
            else:
                skip_until_idx = None  # Reached target, resume normal flow

        # Skip questions hidden by a HIDE condition triggered earlier
        if question.id in hidden_targets:
            continue

        # Check if this question has been answered
        answer = answers.get(question_id)

        # Load conditions for this question (should be prefetched)
        try:
            conditions = list(question.conditions.all().order_by("order"))
        except Exception:
            conditions = []

        # Evaluate conditions
        for condition in conditions:
            if evaluate_condition(condition, answer):
                if condition.action == SurveyQuestionCondition.Action.END_SURVEY:
                    survey_ended = True
                    break  # Stop processing this question's conditions
                elif condition.action == SurveyQuestionCondition.Action.JUMP_TO:
                    # Find the index of the target question
                    if condition.target_question:
                        try:
                            target_idx = next(
                                i
                                for i, q in enumerate(all_questions)
                                if q.id == condition.target_question.id
                            )
                            skip_until_idx = target_idx
                        except StopIteration:
                            pass
                    break  # First matching condition wins
                elif condition.action == SurveyQuestionCondition.Action.HIDE:
                    # Mark the target question to be hidden when we reach it
                    if condition.target_question:
                        hidden_targets.add(condition.target_question.id)
                    break
                elif condition.action == SurveyQuestionCondition.Action.SHOW:
                    # Show the target question
                    # This will be handled when we reach that question
                    break

        # If survey ended, don't show any more questions
        if survey_ended:
            break

        # Add this question to visible list (unless hidden by default with no
        # matching SHOW condition — handled by should_show_question at render time)
        visible.append(question)

    return visible, survey_ended


def should_show_question(
    question: SurveyQuestion,
    all_questions: list[SurveyQuestion],
    answers: dict[str, Any],
) -> bool:
    """
    Determine if a specific question should be shown based on branching logic.

    Uses the question's ``hidden_by_default`` toggle as the starting point:

    - **Shown by default** (``hidden_by_default = False``): visible unless an
      incoming HIDE condition matches.
    - **Hidden by default** (``hidden_by_default = True``): hidden unless an
      incoming SHOW condition matches.

    Args:
        question: The question to check
        all_questions: All questions in the survey (unused, kept for API compat)
        answers: Current answers

    Returns:
        True if the question should be shown
    """
    try:
        if not question.hidden_by_default:
            # Shown by default — check for incoming HIDE conditions
            hide_conditions = SurveyQuestionCondition.objects.filter(
                target_question=question,
                action=SurveyQuestionCondition.Action.HIDE,
            )
            for condition in hide_conditions:
                source_question_id = str(condition.question.id)
                answer = answers.get(source_question_id)
                if evaluate_condition(condition, answer):
                    return False
            return True
        else:
            # Hidden by default — check for incoming SHOW conditions
            show_conditions = SurveyQuestionCondition.objects.filter(
                target_question=question,
                action=SurveyQuestionCondition.Action.SHOW,
            )
            for condition in show_conditions:
                source_question_id = str(condition.question.id)
                answer = answers.get(source_question_id)
                if evaluate_condition(condition, answer):
                    return True
            return False
    except Exception:
        # If there's an error, default to showing the question
        return True
