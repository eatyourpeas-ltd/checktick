"""Survey branching logic evaluation."""

from typing import Any

from .models import SurveyQuestion, SurveyQuestionCondition


def evaluate_condition(
    condition: SurveyQuestionCondition, answer: Any
) -> bool:
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

    for idx, question in enumerate(all_questions):
        question_id = str(question.id)

        # If we're in a skip mode (from JUMP_TO), check if we've reached the target
        if skip_until_idx is not None:
            if idx < skip_until_idx:
                continue  # Skip this question
            else:
                skip_until_idx = None  # Reached target, resume normal flow

        # Check if this question has been answered
        answer = answers.get(question_id)

        # Load conditions for this question (should be prefetched)
        try:
            conditions = list(question.conditions.all().order_by('order'))
        except Exception:
            conditions = []

        # Evaluate conditions
        triggered_action = None
        triggered_target = None

        for condition in conditions:
            if evaluate_condition(condition, answer):
                triggered_action = condition.action
                triggered_target = condition.target_question

                if condition.action == SurveyQuestionCondition.Action.END_SURVEY:
                    survey_ended = True
                    break  # Stop processing this question's conditions
                elif condition.action == SurveyQuestionCondition.Action.JUMP_TO:
                    # Find the index of the target question
                    if condition.target_question:
                        try:
                            target_idx = next(
                                i for i, q in enumerate(all_questions)
                                if q.id == condition.target_question.id
                            )
                            skip_until_idx = target_idx
                        except StopIteration:
                            pass
                    break  # First matching condition wins
                elif condition.action == SurveyQuestionCondition.Action.SKIP:
                    # Skip the target question (don't show it)
                    # This is handled by not adding the target to visible
                    break
                elif condition.action == SurveyQuestionCondition.Action.SHOW:
                    # Show the target question
                    # This will be handled when we reach that question
                    break

        # If survey ended, don't show any more questions
        if survey_ended:
            break

        # Add this question to visible list
        visible.append(question)

        # If SKIP was triggered, find and skip the target question
        if triggered_action == SurveyQuestionCondition.Action.SKIP and triggered_target:
            # Mark the target question to be skipped
            # We'll filter it out by not adding it when we reach it
            pass

    return visible, survey_ended


def should_show_question(
    question: SurveyQuestion,
    all_questions: list[SurveyQuestion],
    answers: dict[str, Any]
) -> bool:
    """
    Determine if a specific question should be shown based on branching logic.

    This handles SHOW conditions - a question with incoming SHOW conditions
    should only be visible if at least one of those conditions is met.

    Args:
        question: The question to check
        all_questions: All questions in the survey
        answers: Current answers

    Returns:
        True if the question should be shown
    """
    # Check if there are any incoming SHOW conditions
    try:
        show_conditions = SurveyQuestionCondition.objects.filter(
            target_question=question,
            action=SurveyQuestionCondition.Action.SHOW
        )

        if not show_conditions.exists():
            # No SHOW conditions, question is always visible
            return True

        # Check if any SHOW condition is met
        for condition in show_conditions:
            source_question_id = str(condition.question.id)
            answer = answers.get(source_question_id)
            if evaluate_condition(condition, answer):
                return True

        # No SHOW conditions were met
        return False
    except Exception:
        # If there's an error, default to showing the question
        return True
