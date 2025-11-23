/**
 * Survey branching logic - dynamically show/hide questions based on conditions
 */

(function () {
  "use strict";

  // Get branching configuration from data attribute
  const form = document.querySelector("[data-survey-form]");
  if (!form) return;

  const branchingData = form.dataset.branchingConfig;
  if (!branchingData) return;

  let config;
  try {
    config = JSON.parse(branchingData);
  } catch (e) {
    console.error("Failed to parse branching config:", e);
    return;
  }

  /**
   * Evaluate a single condition based on current answer
   */
  function evaluateCondition(condition, answer) {
    // Handle empty/missing answers
    const hasAnswer =
      answer !== null &&
      answer !== undefined &&
      answer !== "" &&
      !(Array.isArray(answer) && answer.length === 0);

    // Operators that don't require a value
    if (condition.operator === "exists") {
      return hasAnswer;
    } else if (condition.operator === "not_exists") {
      return !hasAnswer;
    }

    // All other operators require an answer
    if (!hasAnswer) return false;

    // Convert answer to string for comparison
    let answerStr;
    if (Array.isArray(answer)) {
      answerStr = answer.join(",");
    } else {
      answerStr = String(answer);
    }

    const value = condition.value || "";

    // String comparisons (case-insensitive)
    const answerLower = answerStr.toLowerCase().trim();
    const valueLower = value.toLowerCase().trim();

    switch (condition.operator) {
      case "eq":
        return answerLower === valueLower;
      case "neq":
        return answerLower !== valueLower;
      case "contains":
        return answerLower.includes(valueLower);
      case "not_contains":
        return !answerLower.includes(valueLower);

      // Numeric comparisons
      case "gt":
      case "gte":
      case "lt":
      case "lte":
        try {
          const answerNum = parseFloat(answerStr);
          const valueNum = parseFloat(value);
          if (isNaN(answerNum) || isNaN(valueNum)) return false;

          switch (condition.operator) {
            case "gt":
              return answerNum > valueNum;
            case "gte":
              return answerNum >= valueNum;
            case "lt":
              return answerNum < valueNum;
            case "lte":
              return answerNum <= valueNum;
          }
        } catch (e) {
          return false;
        }
        break;
    }

    return false;
  }

  /**
   * Get current answer for a question
   */
  function getAnswer(questionId) {
    const inputs = form.querySelectorAll(`[name="q_${questionId}"]`);
    if (inputs.length === 0) return null;

    const firstInput = inputs[0];

    if (firstInput.type === "checkbox") {
      // Multiple choice - collect all checked values
      const checked = Array.from(inputs)
        .filter((inp) => inp.checked)
        .map((inp) => inp.value);
      return checked.length > 0 ? checked : null;
    } else if (firstInput.type === "radio") {
      // Single choice - find checked radio
      const checked = Array.from(inputs).find((inp) => inp.checked);
      return checked ? checked.value : null;
    } else {
      // Text, number, select, etc.
      return firstInput.value || null;
    }
  }

  /**
   * Update visibility of all questions based on current answers
   */
  function updateVisibility() {
    const answers = {};

    // Collect all answers
    config.questions.forEach((qid) => {
      answers[qid] = getAnswer(qid);
    });

    let surveyEnded = false;
    const skipQuestions = new Set();

    // Process each question's conditions
    config.questions.forEach((questionId) => {
      const questionConditions = config.conditions[questionId] || [];
      const answer = answers[questionId];

      // Evaluate conditions for this question
      for (const condition of questionConditions) {
        if (evaluateCondition(condition, answer)) {
          // Condition is met - apply action
          switch (condition.action) {
            case "end_survey":
              surveyEnded = true;
              break;
            case "skip":
              if (condition.target_question) {
                skipQuestions.add(condition.target_question);
              }
              break;
            case "jump_to":
              // Hide all questions between current and target
              if (condition.target_question) {
                const currentIdx = config.questions.indexOf(questionId);
                const targetIdx = config.questions.indexOf(
                  condition.target_question
                );
                if (currentIdx !== -1 && targetIdx !== -1) {
                  for (let i = currentIdx + 1; i < targetIdx; i++) {
                    skipQuestions.add(config.questions[i]);
                  }
                }
              }
              break;
          }
          // First matching condition wins
          break;
        }
      }
    });

    // Apply visibility changes
    config.questions.forEach((questionId, idx) => {
      const questionElement = form.querySelector(
        `[data-question-id="${questionId}"]`
      );
      if (!questionElement) return;

      // Hide if survey ended and this is after the question that ended it
      const currentQuestionAnswer = answers[questionId];
      const currentConditions = config.conditions[questionId] || [];
      const thisQuestionEnded = currentConditions.some(
        (c) =>
          c.action === "end_survey" &&
          evaluateCondition(c, currentQuestionAnswer)
      );

      if (surveyEnded && !thisQuestionEnded) {
        // Find which question triggered the end
        for (let i = 0; i < idx; i++) {
          const prevQid = config.questions[i];
          const prevAnswer = answers[prevQid];
          const prevConditions = config.conditions[prevQid] || [];
          const prevEnded = prevConditions.some(
            (c) => c.action === "end_survey" && evaluateCondition(c, prevAnswer)
          );
          if (prevEnded) {
            questionElement.style.display = "none";
            return;
          }
        }
      }

      // Hide if this question should be skipped
      if (skipQuestions.has(questionId)) {
        questionElement.style.display = "none";
        return;
      }

      // Handle SHOW conditions
      const showConditions = config.show_conditions[questionId] || [];
      if (showConditions.length > 0) {
        // This question has SHOW conditions - only show if one is met
        let shouldShow = false;
        for (const condition of showConditions) {
          const sourceAnswer = answers[condition.source_question];
          if (evaluateCondition(condition, sourceAnswer)) {
            shouldShow = true;
            break;
          }
        }
        questionElement.style.display = shouldShow ? "" : "none";
        return;
      }

      // Default: show the question
      questionElement.style.display = "";
    });
  }

  // Attach listeners to all form inputs
  form.addEventListener("input", updateVisibility);
  form.addEventListener("change", updateVisibility);

  // Run initial visibility check
  updateVisibility();
})();
