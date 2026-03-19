/**
 * Survey Map Visualizer - Git-Graph Style
 * Renders a visual flow diagram of survey branching logic with square connectors
 */

(function () {
  /**
   * Escape a plain-text string for safe insertion into HTML.
   * Use this whenever untrusted data (question text, condition values, etc.)
   * needs to appear inside an innerHTML assignment.
   */
  function escHtml(str) {
    if (str === null || str === undefined) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#x27;");
  }

  const visualizers = document.querySelectorAll(".branching-visualizer");

  visualizers.forEach((visualizer) => {
    const canvas = visualizer.querySelector(".flow-canvas");
    const container = visualizer.querySelector(".flow-canvas-container");
    if (!canvas || !container) return;

    const ctx = canvas.getContext("2d");
    const surveySlug = visualizer.dataset.surveySlug;

    // Get device pixel ratio for sharp rendering on high-DPI displays
    const dpr = window.devicePixelRatio || 1;

    let questions = [];
    let conditions = {};
    let groupRepeats = {};

    // Track node positions for hover detection
    let nodePositionsForHover = {};
    let branchLinesForHover = [];

    // Function to resize canvas to container width with DPI scaling
    function resizeCanvas() {
      const containerWidth = container.clientWidth;
      const displayWidth = containerWidth;
      const displayHeight = canvas.height / dpr; // Get CSS height

      // Only resize if dimensions changed
      if (canvas.width !== displayWidth * dpr) {
        // Set actual size in memory (scaled for DPI)
        canvas.width = displayWidth * dpr;

        // Set display size (CSS)
        canvas.style.width = displayWidth + "px";

        // Scale context to match DPI
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

        if (questions.length > 0) {
          drawGraph();
        }
      }
    }

    // Set canvas height with DPI scaling
    function setCanvasHeight(height) {
      canvas.height = height * dpr;
      canvas.style.height = height + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    // Get logical (CSS) canvas dimensions (not scaled buffer size)
    function getCanvasWidth() {
      return canvas.width / dpr;
    }

    function getCanvasHeight() {
      return canvas.height / dpr;
    }

    // Use solid fallback colors that work reliably
    const colors = {
      primary: "#570df8",
      primaryFocus: "#4506cb",
      primaryContent: "#ffffff",
      secondary: "#f000b8",
      secondaryFocus: "#bd0091",
      accent: "#37cdbe",
      accentFocus: "#2ba69a",
      accentContent: "#ffffff",
      success: "#36d399",
      warning: "#fbbd23",
      error: "#f87272",
      base100: "#ffffff",
      baseContent: "#1f2937",
      border: "#e5e7eb",
    };

    // Get theme colors from DaisyUI semantic elements (most reliable method)
    function resolveColors() {
      try {
        // Create temporary elements with DaisyUI semantic classes to get computed colors
        const colorClasses = {
          primary: "bg-primary",
          secondary: "bg-secondary",
          accent: "bg-accent",
          success: "bg-success",
          warning: "bg-warning",
          error: "bg-error",
        };

        for (const [colorName, className] of Object.entries(colorClasses)) {
          const tempEl = document.createElement("div");
          tempEl.className = className;
          tempEl.style.position = "absolute";
          tempEl.style.visibility = "hidden";
          tempEl.style.width = "1px";
          tempEl.style.height = "1px";
          document.body.appendChild(tempEl);

          const computedColor = getComputedStyle(tempEl).backgroundColor;
          if (
            computedColor &&
            computedColor !== "rgba(0, 0, 0, 0)" &&
            computedColor !== "transparent"
          ) {
            colors[colorName] = computedColor;
          }

          document.body.removeChild(tempEl);
        }

        // Also get focus/content variants from CSS variables
        const styles = getComputedStyle(document.documentElement);
        const pf = styles.getPropertyValue("--pf").trim();
        const pc = styles.getPropertyValue("--pc").trim();
        if (pf) colors.primaryFocus = `hsl(${pf})`;
        if (pc) colors.primaryContent = `hsl(${pc})`;

        const af = styles.getPropertyValue("--af").trim();
        const ac = styles.getPropertyValue("--ac").trim();
        if (af) colors.accentFocus = `hsl(${af})`;
        if (ac) colors.accentContent = `hsl(${ac})`;

        const b1 = styles.getPropertyValue("--b1").trim();
        const bc = styles.getPropertyValue("--bc").trim();
        if (b1) colors.base100 = `hsl(${b1})`;
        if (bc) colors.baseContent = `hsl(${bc})`;

        // Redraw graph with resolved colors
        if (questions.length > 0) {
          drawGraph();
        }
      } catch (e) {
        console.warn("Could not resolve theme colors, using defaults", e);
      }
    }

    // Resolve colors after a short delay to ensure styles are loaded
    setTimeout(resolveColors, 200);

    // Fetch survey structure and conditions
    async function loadData() {
      try {
        const response = await fetch(
          `/surveys/${surveySlug}/builder/api/branching-data/`,
        );
        if (response.ok) {
          const data = await response.json();
          questions = data.questions;
          conditions = data.conditions;
          groupRepeats = data.group_repeats || {};
        } else {
          console.error("Failed to load branching data:", response.status);
          extractFromPage();
        }
      } catch (e) {
        console.error("Failed to load branching data:", e);
        extractFromPage();
      }
      drawGraph();
    }

    function extractFromPage() {
      // Extract question data from the builder page if we're on it
      const questionElements = document.querySelectorAll("[data-qid]");
      questionElements.forEach((el, index) => {
        const qid = el.dataset.qid;
        const textEl = el.querySelector(".q-text, [data-question-text]");
        const text = textEl
          ? textEl.textContent.trim()
          : `Question ${index + 1}`;

        questions.push({
          id: qid,
          text: text.length > 50 ? text.substring(0, 47) + "..." : text,
          order: index,
        });

        // Extract conditions if present
        const conditionElements = el.querySelectorAll("[data-condition-id]");
        if (conditionElements.length > 0) {
          conditions[qid] = [];
          conditionElements.forEach((condEl) => {
            const summaryEl = condEl.querySelector(".text-xs.opacity-70");
            if (summaryEl) {
              const summary = summaryEl.textContent;
              conditions[qid].push({
                summary: summary,
              });
            }
          });
        }
      });
    }

    function drawGraph() {
      if (questions.length === 0) {
        ctx.fillStyle = colors.baseContent;
        ctx.font = "14px sans-serif";
        ctx.textAlign = "left";
        ctx.fillText("No questions to display", 20, 30);
        return;
      }

      // Clear canvas and hover tracking (use logical dimensions - transform handles scaling)
      ctx.clearRect(0, 0, getCanvasWidth(), getCanvasHeight());
      nodePositionsForHover = {};
      branchLinesForHover = [];

      // Git-graph style layout
      // Condition badges on the left, nodes in center, labels/text on the right
      // Branch lines extend left, "else" lines extend right
      const nodeRadius = 8;
      const rowHeight = 50; // Increased for condition labels
      const baseStartX = 120; // Space on left for branch lines and condition badges
      const startY = 30;
      const elseBranchOffset = 40; // How far right the "else" branch goes
      const groupPadding = 10;
      const groupSpacing = 25;

      // Estimate content width for centering
      // Left edge: branch lines can go about 100px left of nodes
      // Right edge: labels + badges take about 350px from node position
      const contentLeftMargin = 100;
      const contentWidth = contentLeftMargin + 350; // ~450px total content width
      const canvasWidth = getCanvasWidth();

      // Calculate horizontal offset to center content
      const horizontalOffset = Math.max(0, (canvasWidth - contentWidth) / 2);
      const startX = baseStartX + horizontalOffset;
      const labelStartX = startX + elseBranchOffset + 30; // Labels to the right of nodes AND else branches

      const nodePositions = {};
      const groupRegions = [];
      let currentY = startY;
      let currentGroup = null;
      let currentGroupId = null;
      let groupStartY = null;

      // Calculate positions for each question and track group regions
      questions.forEach((q, index) => {
        // Add spacing when entering a new group
        if (q.group_name !== currentGroup) {
          // Save previous group region
          if (currentGroup !== null) {
            groupRegions.push({
              name: currentGroup,
              groupId: currentGroupId,
              startY: groupStartY,
              endY: currentY - rowHeight / 2,
            });
            currentY += groupSpacing;
          }
          currentGroup = q.group_name;
          currentGroupId = q.group_id;
          groupStartY = currentY - groupPadding;
        }

        nodePositions[q.id] = {
          x: startX,
          y: currentY,
        };

        // Store for hover detection with full question text
        nodePositionsForHover[q.id] = {
          x: startX,
          y: currentY,
          radius: 8,
          text: q.full_text || q.text,
          labelX: labelStartX,
          labelWidth: 200, // Will be recalculated when drawing
        };

        currentY += rowHeight;

        // Save last group region
        if (index === questions.length - 1) {
          groupRegions.push({
            name: currentGroup,
            groupId: currentGroupId,
            startY: groupStartY,
            endY: currentY - rowHeight / 2 + groupPadding,
          });
        }
      });

      // Add "End Survey" position after all questions
      currentY += groupSpacing; // Add spacing before end node
      const endSurveyPos = {
        x: startX,
        y: currentY,
      };

      // Adjust canvas size to include end survey node (with DPI scaling)
      const requiredHeight = Math.max(currentY + 50, 400);
      setCanvasHeight(requiredHeight);
      canvas.style.display = "block";

      // Ensure canvas fills container width
      resizeCanvas();

      // Helper to create a pale background color
      // Use a simple semi-transparent overlay approach for reliability
      function getPaleBackground(baseColor) {
        // For group backgrounds, use a very light tint
        // Extract RGB values from any color format
        const tempCanvas = document.createElement("canvas");
        tempCanvas.width = 1;
        tempCanvas.height = 1;
        const tempCtx = tempCanvas.getContext("2d");
        tempCtx.fillStyle = baseColor;
        tempCtx.fillRect(0, 0, 1, 1);
        const [r, g, b] = tempCtx.getImageData(0, 0, 1, 1).data;
        return `rgba(${r}, ${g}, ${b}, 0.1)`;
      }

      // Draw group background regions
      groupRegions.forEach((group, index) => {
        // Use pale secondary color for group backgrounds
        ctx.fillStyle = getPaleBackground(colors.secondary);
        ctx.fillRect(
          0,
          group.startY,
          getCanvasWidth(),
          group.endY - group.startY,
        );

        // Draw group label on the left side
        if (group.name) {
          const leftX = 10;
          let labelY = group.startY + 8;

          // Draw group label in secondary color
          ctx.fillStyle = colors.secondary;
          ctx.font = "bold 12px sans-serif";
          ctx.textAlign = "left";
          ctx.textBaseline = "top";
          ctx.fillText(group.name, leftX, labelY);

          // Draw repeat badge below the group name if group has repeats
          if (group.groupId && groupRepeats[group.groupId]) {
            const repeatInfo = groupRepeats[group.groupId];
            const countText =
              repeatInfo.count !== null ? String(repeatInfo.count) : "∞";

            labelY += 18; // Move down below the group name

            // Measure count text
            ctx.font = "bold 10px sans-serif";
            const textWidth = ctx.measureText(countText).width;
            const iconSize = 12;
            const badgeWidth = iconSize + textWidth + 14; // icon + text + padding
            const badgeHeight = 18;
            const badgeX = leftX;
            const badgeY = labelY;

            // Draw badge background
            ctx.fillStyle = "rgba(59, 130, 246, 0.15)";
            ctx.strokeStyle = "rgba(59, 130, 246, 0.4)";
            ctx.lineWidth = 1;
            const radius = 4;
            ctx.beginPath();
            ctx.moveTo(badgeX + radius, badgeY);
            ctx.lineTo(badgeX + badgeWidth - radius, badgeY);
            ctx.quadraticCurveTo(
              badgeX + badgeWidth,
              badgeY,
              badgeX + badgeWidth,
              badgeY + radius,
            );
            ctx.lineTo(badgeX + badgeWidth, badgeY + badgeHeight - radius);
            ctx.quadraticCurveTo(
              badgeX + badgeWidth,
              badgeY + badgeHeight,
              badgeX + badgeWidth - radius,
              badgeY + badgeHeight,
            );
            ctx.lineTo(badgeX + radius, badgeY + badgeHeight);
            ctx.quadraticCurveTo(
              badgeX,
              badgeY + badgeHeight,
              badgeX,
              badgeY + badgeHeight - radius,
            );
            ctx.lineTo(badgeX, badgeY + radius);
            ctx.quadraticCurveTo(badgeX, badgeY, badgeX + radius, badgeY);
            ctx.closePath();
            ctx.fill();
            ctx.stroke();

            // Draw repeat icon
            const iconX = badgeX + 6;
            const iconY = badgeY + badgeHeight / 2;
            drawRepeatIcon(iconX, iconY, iconSize, "rgba(59, 130, 246, 0.9)");

            // Draw count text
            ctx.fillStyle = "rgba(59, 130, 246, 0.9)";
            ctx.font = "bold 10px sans-serif";
            ctx.textAlign = "left";
            ctx.textBaseline = "middle";
            ctx.fillText(
              countText,
              iconX + iconSize + 2,
              badgeY + badgeHeight / 2,
            );
          }
        }
      });

      // Draw connections (vertical lines between nodes)
      // First pass: draw all lines only
      ctx.strokeStyle = colors.accent;
      ctx.lineWidth = 2;

      // Collect all labels to draw after all lines (for proper z-order)
      const labelsToRender = [];

      questions.forEach((q, index) => {
        const qConditions = conditions[q.id] || [];
        const currentPos = nodePositions[q.id];
        const hasJumpConditions = qConditions.some(
          (c) =>
            c.action === "jump_to" ||
            c.action === "skip" ||
            c.action === "end_survey",
        );

        // Draw vertical line to next question (if not last)
        if (index < questions.length - 1) {
          const nextQ = questions[index + 1];
          const nextPos = nodePositions[nextQ.id];

          if (hasJumpConditions) {
            // This question has jump conditions - draw the default "else" path
            // with a label showing the opposite condition
            const elseSummary = buildElseSummary(qConditions);
            const labelInfo = drawDefaultFlowLine(
              currentPos,
              nextPos,
              nodeRadius,
              elseSummary,
              q.full_text || q.text,
              nextQ.full_text || nextQ.text,
            );
            if (labelInfo) {
              labelsToRender.push(labelInfo);
            }
          } else {
            // No conditions - just draw a simple vertical line
            ctx.beginPath();
            ctx.moveTo(currentPos.x, currentPos.y + nodeRadius);
            ctx.lineTo(currentPos.x, nextPos.y - nodeRadius);
            ctx.stroke();
          }
        }

        // Draw branching connections
        qConditions.forEach((cond, condIndex) => {
          if (cond.target_question && nodePositions[cond.target_question]) {
            const toPos = nodePositions[cond.target_question];
            const targetQ = questions.find(
              (tq) => tq.id === cond.target_question,
            );
            // Pass index to stagger multiple branches from same question
            const branchLabelInfo = drawBranchingLine(
              currentPos,
              toPos,
              cond.action,
              condIndex,
              cond.summary || "",
              nodeRadius,
              q.full_text || q.text,
              targetQ ? targetQ.full_text || targetQ.text : "next question",
            );
            if (branchLabelInfo) {
              labelsToRender.push(branchLabelInfo);
            }
          }
        });
      });

      // Second pass: draw all condition labels (on top of lines, but under nodes)
      labelsToRender.forEach((label) => {
        drawConditionLabel(
          label.labelX,
          label.labelY,
          label.labelText,
          label.color,
        );
      });

      // Build a summary for the "else" / default path
      function buildElseSummary(qConditions) {
        // Get the opposite conditions
        const opposites = qConditions
          .filter(
            (c) =>
              c.action === "jump_to" ||
              c.action === "skip" ||
              c.action === "end_survey",
          )
          .map((c) => {
            if (!c.summary) return null;
            // Build opposite condition text
            const oppositeOps = {
              equals: "not",
              "not equal to": "equals",
              "greater than": "at most",
              "at least": "less than",
              "less than": "at least",
              "at most": "greater than",
              contains: "doesn't contain",
              "does not contain": "contains",
              "has a value": "is empty",
              "is empty": "has a value",
            };
            // Try to find and replace the operator
            for (const [op, opposite] of Object.entries(oppositeOps)) {
              if (c.summary.startsWith(op + " ")) {
                return opposite + c.summary.substring(op.length);
              }
            }
            return "otherwise";
          })
          .filter(Boolean);

        if (opposites.length === 0) return "otherwise";
        if (opposites.length === 1) return opposites[0];
        return "otherwise"; // Multiple conditions, just say "otherwise"
      }

      // Draw the default flow line (else path) - returns label info for later rendering
      // This goes to the RIGHT side (opposite of branch lines which go left)
      function drawDefaultFlowLine(
        from,
        to,
        nodeRadius,
        elseSummary,
        sourceQuestionText = "",
        targetQuestionText = "",
      ) {
        const elseColor = "#6b7280"; // Gray for default/else path
        const branchOffset = 40; // Go to the right
        const cornerX = from.x + branchOffset;

        // Stop the line at the edge of the target node, not the center
        const targetX = to.x + nodeRadius;

        ctx.strokeStyle = elseColor;
        ctx.lineWidth = 2;
        ctx.setLineDash([6, 3]); // Different dash pattern from branch lines

        ctx.beginPath();
        ctx.moveTo(from.x, from.y);
        // Horizontal out to the right
        ctx.lineTo(cornerX, from.y);
        // Vertical down to target level
        ctx.lineTo(cornerX, to.y);
        // Horizontal back toward target node (stop before arrowhead)
        ctx.lineTo(targetX + 8, to.y);
        ctx.stroke();
        ctx.setLineDash([]);

        // Draw arrowhead pointing left (toward the target node)
        const arrowSize = 8;
        ctx.fillStyle = elseColor;
        ctx.strokeStyle = elseColor;
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(targetX + arrowSize, to.y - arrowSize / 2);
        ctx.lineTo(targetX, to.y);
        ctx.lineTo(targetX + arrowSize, to.y + arrowSize / 2);
        ctx.closePath();
        ctx.fill();

        // Return label info for later rendering (so labels appear on top of all lines)
        if (elseSummary) {
          const labelY = (from.y + to.y) / 2;

          // Truncate if too long
          let labelText = elseSummary;
          ctx.font = "10px sans-serif";
          const maxWidth = 80;
          if (ctx.measureText(labelText).width > maxWidth) {
            while (
              ctx.measureText(labelText + "...").width > maxWidth &&
              labelText.length > 0
            ) {
              labelText = labelText.slice(0, -1);
            }
            labelText += "...";
          }

          const textWidth = ctx.measureText(labelText).width;
          const padding = 3;
          const labelX = cornerX + 5;

          // Store for hover detection (else lines)
          branchLinesForHover.push({
            x1: from.x,
            y1: from.y,
            x2: to.x,
            y2: to.y,
            cornerX: cornerX,
            summary: elseSummary,
            action: "else",
            labelX: labelX,
            labelY: labelY,
            labelWidth: textWidth + padding * 2,
            sourceQuestion: sourceQuestionText,
            targetQuestion: targetQuestionText,
            isElse: true,
          });

          return { labelX, labelY, labelText, color: elseColor };
        }
        return null;
      }

      // Draw condition label (called in second pass, after all lines are drawn)
      function drawConditionLabel(labelX, labelY, labelText, color) {
        ctx.font = "10px sans-serif";
        const textWidth = ctx.measureText(labelText).width;
        const padding = 3;

        // Draw label background
        ctx.fillStyle = "rgba(255, 255, 255, 0.9)";
        ctx.fillRect(labelX, labelY - 8, textWidth + padding * 2, 16);

        // Draw label text
        ctx.fillStyle = color;
        ctx.font = "10px sans-serif";
        ctx.textAlign = "left";
        ctx.textBaseline = "middle";
        ctx.fillText(labelText, labelX + padding, labelY);
      }

      // Third pass: Draw nodes and labels (on top of everything)
      questions.forEach((q) => {
        const pos = nodePositions[q.id];
        const qConditions = conditions[q.id] || [];
        const hasConditions = qConditions.length > 0;

        drawCircleNode(pos.x, pos.y, nodeRadius, hasConditions);
        drawLabel(
          labelStartX,
          pos.y,
          q.text,
          hasConditions,
          qConditions,
          q.group_name,
          pos.x, // Pass node's x position for badge placement
        );
      });

      // Draw connection from last question to End Survey
      if (questions.length > 0) {
        const lastQ = questions[questions.length - 1];
        const lastPos = nodePositions[lastQ.id];
        const lastConditions = conditions[lastQ.id] || [];
        const hasJumpConditions = lastConditions.some(
          (c) =>
            c.action === "jump_to" ||
            c.action === "skip" ||
            c.action === "end_survey",
        );

        // Draw line from last question to end survey
        ctx.strokeStyle = colors.accent;
        ctx.lineWidth = 2;

        if (hasJumpConditions) {
          // Last question has conditions - draw else path to end
          const elseColor = colors.accent;
          const branchOffset = 40;
          const cornerX = lastPos.x + branchOffset;
          const targetX = endSurveyPos.x + nodeRadius;

          ctx.strokeStyle = elseColor;
          ctx.setLineDash([]);
          ctx.beginPath();
          ctx.moveTo(lastPos.x, lastPos.y);
          ctx.lineTo(cornerX, lastPos.y);
          ctx.lineTo(cornerX, endSurveyPos.y);
          ctx.lineTo(targetX + 8, endSurveyPos.y);
          ctx.stroke();

          // Arrowhead
          const arrowSize = 8;
          ctx.fillStyle = elseColor;
          ctx.beginPath();
          ctx.moveTo(targetX + arrowSize, endSurveyPos.y - arrowSize / 2);
          ctx.lineTo(targetX, endSurveyPos.y);
          ctx.lineTo(targetX + arrowSize, endSurveyPos.y + arrowSize / 2);
          ctx.closePath();
          ctx.fill();
        } else {
          // Simple vertical line
          ctx.beginPath();
          ctx.moveTo(lastPos.x, lastPos.y + nodeRadius);
          ctx.lineTo(endSurveyPos.x, endSurveyPos.y - nodeRadius);
          ctx.stroke();
        }
      }

      // Draw End Survey node (square with error color)
      drawEndSurveyNode(endSurveyPos.x, endSurveyPos.y, nodeRadius);

      // Draw End Survey label
      ctx.fillStyle = colors.error;
      ctx.font = "bold 13px sans-serif";
      ctx.textAlign = "left";
      ctx.textBaseline = "middle";
      ctx.fillText("End Survey", labelStartX, endSurveyPos.y);
    }

    function drawEndSurveyNode(x, y, size) {
      // Draw a square node for end survey (different from question circles)
      const halfSize = size;
      ctx.fillStyle = colors.error;
      ctx.strokeStyle = colors.error;
      ctx.lineWidth = 2;

      ctx.beginPath();
      ctx.rect(x - halfSize, y - halfSize, halfSize * 2, halfSize * 2);
      ctx.fill();
      ctx.stroke();
    }

    function drawCircleNode(x, y, radius, hasConditions) {
      // Draw node circle
      ctx.beginPath();
      ctx.arc(x, y, radius, 0, Math.PI * 2);
      ctx.fillStyle = hasConditions ? colors.primary : colors.accent;
      ctx.fill();
      ctx.strokeStyle = hasConditions
        ? colors.primaryFocus
        : colors.accentFocus;
      ctx.lineWidth = 2;
      ctx.stroke();
    }

    function drawRepeatIcon(x, y, size, color) {
      // Draw a circular arrow repeat icon
      ctx.save();
      ctx.strokeStyle = color;
      ctx.fillStyle = color;
      ctx.lineWidth = 1.2;
      ctx.lineCap = "round";
      ctx.lineJoin = "round";

      const scale = size / 16;
      const cx = x;
      const cy = y;

      // Draw curved arrow path (simplified repeat symbol)
      ctx.beginPath();
      ctx.arc(cx, cy, 4 * scale, -Math.PI * 0.3, Math.PI * 1.3, false);
      ctx.stroke();

      // Arrow head
      ctx.beginPath();
      ctx.moveTo(cx - 3 * scale, cy - 4.5 * scale);
      ctx.lineTo(cx + 1 * scale, cy - 4.5 * scale);
      ctx.lineTo(cx - 1 * scale, cy - 1.5 * scale);
      ctx.closePath();
      ctx.fill();

      ctx.restore();
    }

    function drawLabel(
      x,
      y,
      text,
      hasConditions,
      nodeConditions,
      groupName,
      nodeX,
    ) {
      // Draw text label to the right of the node (and any right-side branches)
      ctx.fillStyle = hasConditions ? colors.primary : colors.accent;
      ctx.font = hasConditions ? "bold 13px sans-serif" : "13px sans-serif";
      ctx.textAlign = "left";
      ctx.textBaseline = "middle";

      // Truncate text if too long (reserve space for group label and badge on right)
      const badgeSpace = nodeConditions.length > 0 ? 80 : 0; // Reserve space for badge
      const maxWidth = getCanvasWidth() - x - 150 - badgeSpace;
      let displayText = text;
      if (ctx.measureText(text).width > maxWidth) {
        while (
          ctx.measureText(displayText + "...").width > maxWidth &&
          displayText.length > 0
        ) {
          displayText = displayText.slice(0, -1);
        }
        displayText += "...";
      }

      ctx.fillText(displayText, x, y);

      // Draw condition count badge to the RIGHT of the question title
      if (nodeConditions.length > 0) {
        const badgeText = `${nodeConditions.length} condition${
          nodeConditions.length > 1 ? "s" : ""
        }`;

        // Measure the displayed text to position badge after it
        ctx.font = hasConditions ? "bold 13px sans-serif" : "13px sans-serif";
        const textWidth = ctx.measureText(displayText).width;

        // Measure badge text
        ctx.font = "10px sans-serif";
        const badgeTextWidth = ctx.measureText(badgeText).width;
        const badgePadding = 4;
        const badgeWidth = badgeTextWidth + badgePadding * 2;
        const badgeHeight = 16;

        // Position badge to the RIGHT of the question title
        const badgeX = x + textWidth + 8; // 8px gap after title

        // Draw badge background
        ctx.fillStyle = "rgba(128, 128, 128, 0.15)";
        ctx.beginPath();
        const radius = 3;
        ctx.roundRect(
          badgeX,
          y - badgeHeight / 2,
          badgeWidth,
          badgeHeight,
          radius,
        );
        ctx.fill();

        // Draw badge text
        ctx.fillStyle = "rgba(128, 128, 128, 0.8)";
        ctx.textAlign = "left";
        ctx.textBaseline = "middle";
        ctx.fillText(badgeText, badgeX + badgePadding, y);
      }
    }

    function drawBranchingLine(
      from,
      to,
      action,
      branchIndex = 0,
      conditionSummary = "",
      nodeRadius = 8,
      sourceQuestionText = "",
      targetQuestionText = "",
    ) {
      // Color-code by action type using theme colors
      const actionColors = {
        show: colors.primary,
        jump_to: colors.success,
        skip: colors.warning,
        end_survey: colors.error,
      };

      const color = actionColors[action] || colors.baseContent;
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.setLineDash([4, 4]);

      // Branch lines go to the LEFT of the main flow
      // Each additional branch from same node goes further left
      const branchOffset = -30 - branchIndex * 25;
      const cornerX = from.x + branchOffset;

      // Stop the line at the edge of the target node, not the center
      const targetX = to.x - nodeRadius;

      ctx.beginPath();
      ctx.moveTo(from.x, from.y);

      // Draw right-angle connector (like git graph)
      // Horizontal out to the left from source
      ctx.lineTo(cornerX, from.y);
      // Vertical down/up to target level
      ctx.lineTo(cornerX, to.y);
      // Horizontal back toward target node (stop before arrowhead)
      ctx.lineTo(targetX - 8, to.y);

      ctx.stroke();
      ctx.setLineDash([]);

      // Draw arrowhead pointing right (toward the target node)
      const arrowSize = 8;
      ctx.fillStyle = color;
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(targetX - arrowSize, to.y - arrowSize / 2);
      ctx.lineTo(targetX, to.y);
      ctx.lineTo(targetX - arrowSize, to.y + arrowSize / 2);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();

      // Return label info for later rendering (so labels appear on top of all lines)
      if (conditionSummary) {
        // Align label vertically with the target node (not midpoint)
        const labelY = to.y;

        // Truncate long condition text
        let labelText = conditionSummary;
        ctx.font = "10px sans-serif";
        const maxLabelWidth = 80;
        if (ctx.measureText(labelText).width > maxLabelWidth) {
          while (
            ctx.measureText(labelText + "...").width > maxLabelWidth &&
            labelText.length > 0
          ) {
            labelText = labelText.slice(0, -1);
          }
          labelText += "...";
        }

        const textWidth = ctx.measureText(labelText).width;
        const padding = 3;
        const labelMargin = 6; // Gap between label right edge and the branch line
        const labelX = cornerX - textWidth - padding * 2 - labelMargin;

        // Store for hover detection
        branchLinesForHover.push({
          x1: from.x,
          y1: from.y,
          x2: to.x,
          y2: to.y,
          cornerX: cornerX,
          summary: conditionSummary,
          action: action,
          labelX: labelX,
          labelY: labelY,
          labelWidth: textWidth + padding * 2,
          sourceQuestion: sourceQuestionText,
          targetQuestion: targetQuestionText,
        });

        return { labelX, labelY, labelText, color };
      }
      return null;
    }

    // Tooltip functionality
    const tooltip = visualizer.querySelector(".survey-map-tooltip");
    const tooltipContent = tooltip
      ? tooltip.querySelector(".tooltip-content")
      : null;

    function showTooltip(x, y, html) {
      if (!tooltip || !tooltipContent) return;
      tooltipContent.innerHTML = html;
      tooltip.classList.remove("hidden");

      // Position tooltip near the cursor but within viewport
      const containerRect = container.getBoundingClientRect();
      const tooltipRect = tooltip.getBoundingClientRect();

      let tooltipX = x + 15;
      let tooltipY = y - 10;

      // Keep within container
      if (tooltipX + tooltipRect.width > container.clientWidth) {
        tooltipX = x - tooltipRect.width - 15;
      }
      if (tooltipY + tooltipRect.height > container.clientHeight) {
        tooltipY = y - tooltipRect.height - 10;
      }

      tooltip.style.left = `${tooltipX + container.scrollLeft}px`;
      tooltip.style.top = `${tooltipY + container.scrollTop}px`;
    }

    function hideTooltip() {
      if (tooltip) {
        tooltip.classList.add("hidden");
      }
    }

    // Handle mouse movement for tooltips
    canvas.addEventListener("mousemove", (e) => {
      if (isPanning) {
        hideTooltip();
        return;
      }

      const rect = canvas.getBoundingClientRect();
      const x = e.clientX - rect.left + container.scrollLeft;
      const y = e.clientY - rect.top + container.scrollTop;

      // Check if hovering over a question node
      for (const [qId, pos] of Object.entries(nodePositionsForHover)) {
        const q = questions.find((q) => q.id === qId);
        if (!q) continue;

        // Check node circle
        const dx = x - pos.x;
        const dy = y - pos.y;
        if (Math.sqrt(dx * dx + dy * dy) < pos.radius + 5) {
          const fullText = q.full_text || q.text;
          const questionNumber = q.order !== undefined ? q.order + 1 : ""; // 1-indexed
          showTooltip(
            e.clientX - rect.left,
            e.clientY - rect.top,
            `<div class="font-semibold mb-1">Q${escHtml(questionNumber)}</div>` +
              `<div class="text-base-content/70">${escHtml(fullText)}</div>`,
          );
          canvas.style.cursor = "pointer";
          return;
        }

        // Check label area (rectangle from labelX)
        if (
          x >= pos.labelX &&
          x <= pos.labelX + pos.labelWidth + 100 &&
          y >= pos.y - 12 &&
          y <= pos.y + 12
        ) {
          const fullText = q.full_text || q.text;
          if (fullText.length > 50) {
            const questionNumber = q.order !== undefined ? q.order + 1 : "";
            showTooltip(
              e.clientX - rect.left,
              e.clientY - rect.top,
              `<div class="font-semibold mb-1">Q${escHtml(questionNumber)}</div>` +
                `<div class="text-base-content/70">${escHtml(fullText)}</div>`,
            );
            canvas.style.cursor = "pointer";
            return;
          }
        }
      }

      // Check if hovering over a branch line label
      for (const branch of branchLinesForHover) {
        if (
          x >= branch.labelX - 5 &&
          x <= branch.labelX + branch.labelWidth + 5 &&
          y >= branch.labelY - 10 &&
          y <= branch.labelY + 10
        ) {
          // Build plain English explanation
          let explanation;
          if (branch.isElse) {
            // Else/default flow line - simple "otherwise" message
            explanation = `Otherwise, continue to <strong>${escHtml(branch.targetQuestion)}</strong>`;
          } else {
            // Regular branch line
            const actionVerbs = {
              show: "show",
              jump_to: "go to",
              skip: "skip to",
              end_survey: "end the survey",
            };
            const actionVerb =
              actionVerbs[branch.action] || escHtml(branch.action);
            const targetText =
              branch.action === "end_survey"
                ? ""
                : `<strong>${escHtml(branch.targetQuestion)}</strong>`;

            explanation =
              branch.action === "end_survey"
                ? `If ${escHtml(branch.summary)}, ${actionVerb}`
                : `If ${escHtml(branch.summary)}, ${actionVerb} ${targetText}`;
          }

          showTooltip(
            e.clientX - rect.left,
            e.clientY - rect.top,
            `<div class="text-base-content">${explanation}</div>`,
          );
          canvas.style.cursor = "pointer";
          return;
        }
      }

      hideTooltip();
      canvas.style.cursor = "default";
    });

    canvas.addEventListener("mouseleave", () => {
      hideTooltip();
      canvas.style.cursor = "default";
    });

    // Pan/zoom functionality
    let isPanning = false;
    let startPanX = 0;
    let startPanY = 0;

    container.addEventListener("mousedown", (e) => {
      isPanning = true;
      startPanX = e.clientX + container.scrollLeft;
      startPanY = e.clientY + container.scrollTop;
    });

    container.addEventListener("mousemove", (e) => {
      if (!isPanning) return;
      container.scrollLeft = startPanX - e.clientX;
      container.scrollTop = startPanY - e.clientY;
    });

    container.addEventListener("mouseup", () => {
      isPanning = false;
    });

    container.addEventListener("mouseleave", () => {
      isPanning = false;
    });

    // Fullscreen functionality
    const fullscreenBtn = visualizer.querySelector(".fullscreen-btn");
    if (fullscreenBtn) {
      fullscreenBtn.addEventListener("click", () => {
        if (container.requestFullscreen) {
          container.requestFullscreen();
        } else if (container.webkitRequestFullscreen) {
          container.webkitRequestFullscreen();
        } else if (container.msRequestFullscreen) {
          container.msRequestFullscreen();
        }
      });
    }

    // Re-render when entering/exiting fullscreen to recalculate centering
    document.addEventListener("fullscreenchange", () => {
      // Small delay to let fullscreen transition complete
      setTimeout(() => {
        resizeCanvas();
        if (questions.length > 0) {
          drawGraph();
        }
      }, 100);
    });

    // Initialize
    resizeCanvas();
    loadData();

    // Listen for window resize to keep canvas responsive
    window.addEventListener("resize", resizeCanvas);

    // Listen for group reordering events to refresh the visualizer
    document.addEventListener("groupsReordered", function () {
      loadData();
    });

    // Also listen for htmx afterSwap events in case groups are added/removed
    document.body.addEventListener("htmx:afterSwap", function (evt) {
      if (evt.detail.target && evt.detail.target.id === "groups-draggable") {
        loadData();
      }
    });
  });
})();
