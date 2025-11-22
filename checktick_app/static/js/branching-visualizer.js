/**
 * Branching Flow Visualizer - Git-Graph Style
 * Renders a visual flow diagram of survey branching logic
 */

(function () {
  const visualizers = document.querySelectorAll(".branching-visualizer");

  visualizers.forEach((visualizer) => {
    const canvas = visualizer.querySelector(".flow-canvas");
    const container = visualizer.querySelector(".flow-canvas-container");
    if (!canvas || !container) return;

    const ctx = canvas.getContext("2d");
    const surveySlug = visualizer.dataset.surveySlug;

    let questions = [];
    let conditions = {};
    let groupRepeats = {};

    // Function to resize canvas to container width
    function resizeCanvas() {
      const containerWidth = container.clientWidth;
      if (canvas.width !== containerWidth) {
        canvas.width = containerWidth;
        if (questions.length > 0) {
          drawGraph();
        }
      }
    }

    // Use solid fallback colors that work reliably
    const colors = {
      primary: "#570df8",
      primaryFocus: "#4506cb",
      primaryContent: "#ffffff",
      accent: "#37cdbe",
      accentFocus: "#2ba69a",
      accentContent: "#ffffff",
      base100: "#ffffff",
      baseContent: "#1f2937",
      border: "#e5e7eb",
    };

    // Try to get theme colors from computed styles
    function resolveColors() {
      try {
        // Get the actual theme being used
        const currentTheme =
          document.documentElement.getAttribute("data-theme") ||
          document.body.getAttribute("data-theme");

        // Try to get colors from actual themed elements on the page
        // Look for alert-primary or other primary-colored elements
        const primaryElement = document.querySelector(
          '.alert-primary, .btn-primary, .bg-primary, [class*="primary"]'
        );
        const accentElement = document.querySelector(
          '.alert-accent, .btn-accent, .bg-accent, [class*="accent"]'
        );

        if (primaryElement) {
          const primaryStyle = getComputedStyle(primaryElement);
          const bgColor = primaryStyle.backgroundColor;
          if (
            bgColor &&
            bgColor !== "rgba(0, 0, 0, 0)" &&
            bgColor !== "transparent"
          ) {
            colors.primary = bgColor;
          }
        }

        if (accentElement) {
          const accentStyle = getComputedStyle(accentElement);
          const bgColor = accentStyle.backgroundColor;
          if (
            bgColor &&
            bgColor !== "rgba(0, 0, 0, 0)" &&
            bgColor !== "transparent"
          ) {
            colors.accent = bgColor;
          }
        }

        // Also try CSS variables as fallback
        const styles = getComputedStyle(document.documentElement);
        const p = styles.getPropertyValue("--p").trim();
        const a = styles.getPropertyValue("--a").trim();

        if (p) {
          colors.primary = `hsl(${p})`;
          const pf = styles.getPropertyValue("--pf").trim();
          const pc = styles.getPropertyValue("--pc").trim();
          if (pf) colors.primaryFocus = `hsl(${pf})`;
          if (pc) colors.primaryContent = `hsl(${pc})`;
        }

        if (a) {
          colors.accent = `hsl(${a})`;
          const af = styles.getPropertyValue("--af").trim();
          const ac = styles.getPropertyValue("--ac").trim();
          if (af) colors.accentFocus = `hsl(${af})`;
          if (ac) colors.accentContent = `hsl(${ac})`;
        }

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
          `/surveys/${surveySlug}/builder/api/branching-data/`
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

      // Clear canvas
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Git-graph style layout
      const nodeRadius = 8;
      const rowHeight = 40;
      const startX = 30;
      const startY = 30;
      const labelStartX = 50;
      const groupPadding = 10;
      const groupSpacing = 20;

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

      // Adjust canvas size
      const requiredHeight = Math.max(currentY + 30, 400);
      canvas.height = requiredHeight;
      canvas.style.display = "block";

      // Ensure canvas fills container width
      resizeCanvas();

      // Draw group background regions
      groupRegions.forEach((group, index) => {
        // Alternate background shading
        ctx.fillStyle =
          index % 2 === 0
            ? "rgba(128, 128, 128, 0.03)"
            : "rgba(128, 128, 128, 0.06)";
        ctx.fillRect(0, group.startY, canvas.width, group.endY - group.startY);

        // Draw group label and repeat badge if applicable
        if (group.name) {
          let rightX = canvas.width - 10;

          // Draw repeat badge if group has repeats
          if (group.groupId && groupRepeats[group.groupId]) {
            const repeatInfo = groupRepeats[group.groupId];
            const countText = repeatInfo.count !== null ? String(repeatInfo.count) : "∞";

            // Measure count text
            ctx.font = "bold 11px sans-serif";
            const textWidth = ctx.measureText(countText).width;
            const iconSize = 14;
            const badgeWidth = iconSize + textWidth + 18; // icon + text + padding
            const badgeHeight = 20;
            const badgeX = rightX - badgeWidth;
            const badgeY = group.startY + 5;

            // Draw badge background
            ctx.fillStyle = "rgba(59, 130, 246, 0.15)";
            ctx.strokeStyle = "rgba(59, 130, 246, 0.4)";
            ctx.lineWidth = 1;
            const radius = 4;
            ctx.beginPath();
            ctx.moveTo(badgeX + radius, badgeY);
            ctx.lineTo(badgeX + badgeWidth - radius, badgeY);
            ctx.quadraticCurveTo(badgeX + badgeWidth, badgeY, badgeX + badgeWidth, badgeY + radius);
            ctx.lineTo(badgeX + badgeWidth, badgeY + badgeHeight - radius);
            ctx.quadraticCurveTo(badgeX + badgeWidth, badgeY + badgeHeight, badgeX + badgeWidth - radius, badgeY + badgeHeight);
            ctx.lineTo(badgeX + radius, badgeY + badgeHeight);
            ctx.quadraticCurveTo(badgeX, badgeY + badgeHeight, badgeX, badgeY + badgeHeight - radius);
            ctx.lineTo(badgeX, badgeY + radius);
            ctx.quadraticCurveTo(badgeX, badgeY, badgeX + radius, badgeY);
            ctx.closePath();
            ctx.fill();
            ctx.stroke();

            // Draw repeat icon
            const iconX = badgeX + 8;
            const iconY = badgeY + badgeHeight / 2;
            drawRepeatIcon(iconX, iconY, iconSize, "rgba(59, 130, 246, 0.9)");

            // Draw count text
            ctx.fillStyle = "rgba(59, 130, 246, 0.9)";
            ctx.font = "bold 11px sans-serif";
            ctx.textAlign = "left";
            ctx.textBaseline = "middle";
            ctx.fillText(countText, iconX + iconSize + 3, badgeY + badgeHeight / 2);

            // Adjust rightX for group label
            rightX = badgeX - 8;
          }

          // Draw group label
          ctx.fillStyle = "rgba(128, 128, 128, 0.5)";
          ctx.font = "bold 11px sans-serif";
          ctx.textAlign = "right";
          ctx.textBaseline = "top";
          ctx.fillText(group.name, rightX, group.startY + 5);
        }
      });

      // Draw connections (vertical lines between nodes)
      ctx.strokeStyle = colors.border;
      ctx.lineWidth = 2;

      questions.forEach((q, index) => {
        const qConditions = conditions[q.id] || [];
        const currentPos = nodePositions[q.id];

        // Draw vertical line to next question (if not last)
        if (index < questions.length - 1) {
          const nextPos = nodePositions[questions[index + 1].id];
          ctx.beginPath();
          ctx.moveTo(currentPos.x, currentPos.y + nodeRadius);
          ctx.lineTo(currentPos.x, nextPos.y - nodeRadius);
          ctx.stroke();
        }

        // Draw branching connections
        qConditions.forEach((cond, condIndex) => {
          if (cond.target_question && nodePositions[cond.target_question]) {
            const toPos = nodePositions[cond.target_question];
            // Alternate sides for multiple conditions from the same question
            const useRightSide = condIndex % 2 === 0;
            drawBranchingLine(currentPos, toPos, cond.action, useRightSide);
          }
        });
      });

      // Draw nodes and labels
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
          q.group_name
        );
      });
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

    function drawLabel(x, y, text, hasConditions, nodeConditions, groupName) {
      // Draw text label to the right of the node
      ctx.fillStyle = hasConditions ? colors.primary : colors.accent;
      ctx.font = hasConditions ? "bold 13px sans-serif" : "13px sans-serif";
      ctx.textAlign = "left";
      ctx.textBaseline = "middle";

      // Truncate text if too long (reserve space for group label on right)
      const maxWidth = canvas.width - x - 150;
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

      // Draw condition count badge below the label if present
      if (nodeConditions.length > 0) {
        const badgeY = y + 14;
        const badgeText = `${nodeConditions.length} condition${
          nodeConditions.length > 1 ? "s" : ""
        }`;

        // Measure badge text
        ctx.font = "10px sans-serif";
        const badgeTextWidth = ctx.measureText(badgeText).width;
        const badgePadding = 4;
        const badgeWidth = badgeTextWidth + badgePadding * 2;
        const badgeHeight = 16;

        // Draw badge background
        ctx.fillStyle = "rgba(128, 128, 128, 0.15)";
        ctx.beginPath();
        const radius = 3;
        ctx.roundRect(
          x,
          badgeY - badgeHeight / 2,
          badgeWidth,
          badgeHeight,
          radius
        );
        ctx.fill();

        // Draw badge text
        ctx.fillStyle = "rgba(128, 128, 128, 0.8)";
        ctx.textAlign = "left";
        ctx.textBaseline = "middle";
        ctx.fillText(badgeText, x + badgePadding, badgeY);
      }
    }

    function drawBranchingLine(from, to, action, useRightSide = true) {
      // Color-code by action type
      const actionColors = {
        SHOW: "#3b82f6",
        JUMP_TO: "#10b981",
        SKIP: "#f59e0b",
        END_SURVEY: "#ef4444",
      };

      ctx.strokeStyle = actionColors[action] || "#6b7280";
      ctx.lineWidth = 2;
      ctx.setLineDash([5, 3]);

      ctx.beginPath();
      ctx.moveTo(from.x, from.y);

      // Draw curved line for branching connections, alternating sides
      const curveOffset = useRightSide ? 20 : -20;
      const midX = from.x + curveOffset;
      ctx.bezierCurveTo(midX, from.y, midX, to.y, to.x, to.y);

      ctx.stroke();
      ctx.setLineDash([]);
    }

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
