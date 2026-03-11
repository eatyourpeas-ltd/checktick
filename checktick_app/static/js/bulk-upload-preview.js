(() => {
  const textarea = document.querySelector('textarea[name="markdown"]');
  const previewContainer = document.getElementById("bulk-structure-preview");
  const countBadge = document.getElementById("bulk-structure-count");
  const openModalButton = document.getElementById("bulk-import-open-modal");
  const openModalButtonTop = document.getElementById(
    "bulk-import-open-modal-top",
  );
  const confirmDialog = document.getElementById("bulk-import-confirm");
  const cancelModalButton = document.getElementById("bulk-import-cancel");

  // Function to open modal
  const openModal = () => {
    if (typeof confirmDialog.showModal === "function") {
      confirmDialog.showModal();
    }
  };

  if (confirmDialog && cancelModalButton) {
    // Add event listeners to both buttons
    if (openModalButton) {
      openModalButton.addEventListener("click", openModal);
    }
    if (openModalButtonTop) {
      openModalButtonTop.addEventListener("click", openModal);
    }

    cancelModalButton.addEventListener("click", () => {
      if (typeof confirmDialog.close === "function") {
        confirmDialog.close();
      }
    });

    confirmDialog.addEventListener("cancel", (event) => {
      event.preventDefault();
      if (typeof confirmDialog.close === "function") {
        confirmDialog.close();
      }
    });
  }

  if (!textarea || !previewContainer) {
    return;
  }

  const slugify = (text) =>
    (text || "")
      .toString()
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9\s-]/g, " ")
      .trim()
      .replace(/[\s_-]+/g, "-")
      .replace(/^-+|-+$/g, "");

  const allocateId = (preferred, fallback, registry) => {
    let base = preferred ? slugify(preferred) : "";
    if (!base) {
      base = slugify(fallback);
    }
    let candidate = base || fallback || "item";
    const original = candidate;
    let counter = 2;
    while (registry.has(candidate)) {
      candidate = `${original}-${counter++}`;
    }
    registry.add(candidate);
    return candidate;
  };

  const extractTitleAndId = (rawTitle, fallbackId, registry) => {
    let title = rawTitle || "";
    let explicitId;
    let isRequired = false;

    // Check for required indicator (trailing asterisk)
    // Handle both "Title*" and "Title* {id}" formats
    if (
      title.endsWith("*") ||
      (title.includes("{") && title.split("{")[0].trim().endsWith("*"))
    ) {
      isRequired = true;
      // Strip asterisk from before the ID if present
      if (title.includes("{") && title.split("{")[0].trim().endsWith("*")) {
        const parts = title.split("{");
        parts[0] = parts[0].trim().slice(0, -1).trim();
        title = parts.join("{");
      } else {
        title = title.slice(0, -1).trim();
      }
    }

    const match = title.match(/\{([^{}]+)\}\s*$/);
    if (match) {
      explicitId = match[1].trim();
      title = title.slice(0, match.index).trim();
    }
    const id = allocateId(explicitId, fallbackId, registry);
    return { title: title.trim(), id, explicitId, isRequired };
  };

  const createIdToken = (text, variant) => {
    const el = document.createElement("code");
    el.textContent = text;
    el.className =
      "inline-flex items-center rounded border px-2 py-0.5 font-mono text-xs tracking-tight";

    if (variant === "group") {
      el.style.backgroundColor = "hsl(var(--p) / 0.18)";
      el.style.borderColor = "hsl(var(--p) / 0.35)";
      el.style.color = "hsl(var(--p))";
    } else if (variant === "question") {
      el.style.backgroundColor = "hsl(var(--s) / 0.16)";
      el.style.borderColor = "hsl(var(--s) / 0.32)";
      el.style.color = "hsl(var(--s))";
    } else {
      el.style.backgroundColor = "hsl(var(--in) / 0.15)";
      el.style.borderColor = "hsl(var(--in) / 0.3)";
      el.style.color = "hsl(var(--in))";
    }

    return el;
  };

  const createMetaBadge = (variant, label) => {
    const badge = document.createElement("span");
    badge.className =
      "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium";
    badge.style.backgroundColor = "hsl(var(--p) / 0.18)";
    badge.style.borderColor = "hsl(var(--p) / 0.35)";
    badge.style.color = "hsl(var(--p))";

    const icon = document.createElement("span");
    icon.setAttribute("aria-hidden", "true");
    icon.className = "leading-none";
    icon.textContent = variant === "repeat" ? "++" : "➜";

    const text = document.createElement("span");
    text.textContent = label;

    badge.appendChild(icon);
    badge.appendChild(text);

    return badge;
  };

  const parseStructure = (md) => {
    const rawLines = (md || "").split(/\r?\n/);
    const normalized = rawLines.map((raw) => {
      let depth = 0;
      let i = 0;
      while (i < raw.length) {
        const char = raw[i];
        if (char === ">") {
          depth += 1;
          i += 1;
          if (raw[i] === " ") {
            i += 1;
          }
          continue;
        }
        if (char === " ") {
          i += 1;
          continue;
        }
        break;
      }
      const content = raw.slice(i);
      return {
        depth,
        content,
        trimmed: content.trim(),
      };
    });

    const groups = [];
    const warnings = [];
    const groupIds = new Set();
    const questionIds = new Set();
    const pendingRepeat = new Map();
    let currentGroup = null;

    const isGroupHeading = (line) => /^#(?!#)\s+/.test(line);
    const isQuestionHeading = (line) => /^##\s+/.test(line);

    for (let i = 0; i < normalized.length; i += 1) {
      const { trimmed, depth } = normalized[i];
      if (!trimmed) {
        continue;
      }

      const repeatMatch = trimmed.match(/^REPEAT(?:-(\d+))?$/i);
      if (repeatMatch) {
        pendingRepeat.set(
          depth,
          repeatMatch[1] ? parseInt(repeatMatch[1], 10) : null,
        );
        continue;
      }

      if (isGroupHeading(trimmed)) {
        const rawTitle = trimmed.replace(/^#\s+/, "").trim();
        const { title, id: groupId } = extractTitleAndId(
          rawTitle,
          `group-${groups.length + 1}`,
          groupIds,
        );
        let description = "";
        for (let j = i + 1; j < normalized.length; j += 1) {
          const lookahead = normalized[j].trimmed;
          if (!lookahead) {
            continue;
          }
          if (isGroupHeading(lookahead) || isQuestionHeading(lookahead)) {
            break;
          }
          if (!/^\(.*\)$/.test(lookahead) && !lookahead.startsWith("?")) {
            description = lookahead;
          }
          break;
        }
        currentGroup = {
          title: title || "Untitled group",
          id: groupId,
          description,
          questions: [],
          repeat: pendingRepeat.has(depth)
            ? { maxCount: pendingRepeat.get(depth) }
            : null,
        };
        if (pendingRepeat.has(depth)) {
          pendingRepeat.delete(depth);
        }
        groups.push(currentGroup);
        continue;
      }

      if (isQuestionHeading(trimmed)) {
        const rawTitle = trimmed.replace(/^##\s+/, "").trim();
        if (!currentGroup) {
          warnings.push(
            `Question “${
              rawTitle || "Untitled"
            }” appears before any group heading. It will be imported into an auto-created group.`,
          );
          const { id: fallbackGroupId } = extractTitleAndId(
            "Ungrouped",
            `group-${groups.length + 1}`,
            groupIds,
          );
          currentGroup = {
            title: "Ungrouped",
            id: fallbackGroupId,
            description: "",
            questions: [],
            repeat: null,
          };
          groups.push(currentGroup);
        }

        const {
          title,
          id: questionId,
          isRequired,
        } = extractTitleAndId(
          rawTitle,
          `${currentGroup.id}-${currentGroup.questions.length + 1}`,
          questionIds,
        );
        const question = {
          title: title || "Untitled question",
          id: questionId,
          description: "",
          type: "",
          branches: [],
          isRequired: isRequired || false,
        };

        for (let j = i + 1; j < normalized.length; j += 1) {
          const lookahead = normalized[j].trimmed;
          if (!lookahead) {
            continue;
          }
          if (isGroupHeading(lookahead) || isQuestionHeading(lookahead)) {
            break;
          }
          if (
            !question.description &&
            !/^\(.*\)$/.test(lookahead) &&
            !lookahead.startsWith("?")
          ) {
            question.description = lookahead;
          } else if (!question.type && /^\(.*\)$/.test(lookahead)) {
            question.type = lookahead.slice(1, -1).trim();
          } else if (/^\?\s*/.test(lookahead)) {
            const branchMatch = lookahead.match(
              /^\?\s*when\s+(.+?)\s*->\s*\{([^{}]+)\}\s*$/i,
            );
            if (branchMatch) {
              const condition = branchMatch[1].trim();
              const targetRaw = branchMatch[2].trim();
              question.branches.push({
                condition,
                target: slugify(targetRaw),
                targetRaw,
              });
            }
          }
        }

        currentGroup.questions.push(question);
      }
    }

    return { groups, warnings };
  };

  const renderStructure = ({ groups, warnings }) => {
    previewContainer.innerHTML = "";
    previewContainer.setAttribute("aria-busy", "true");

    if (warnings.length) {
      const warningBox = document.createElement("div");
      warningBox.className = "alert alert-warning text-sm";
      const heading = document.createElement("div");
      heading.className = "font-semibold";
      heading.textContent = "Notes";
      warningBox.appendChild(heading);
      const list = document.createElement("ul");
      list.className = "list-disc pl-5 mt-1 space-y-1";
      warnings.forEach((message) => {
        const li = document.createElement("li");
        li.textContent = message;
        list.appendChild(li);
      });
      warningBox.appendChild(list);
      previewContainer.appendChild(warningBox);
    }

    let totalQuestions = 0;

    if (!groups.length) {
      const empty = document.createElement("div");
      empty.className = "text-sm text-base-content/70";
      empty.textContent =
        "Add a # heading for a group and ## headings for questions to see the structure preview.";
      previewContainer.appendChild(empty);
      previewContainer.setAttribute("aria-busy", "false");
      if (countBadge) {
        countBadge.classList.add("hidden");
      }
      return;
    }

    groups.forEach((group) => {
      totalQuestions += group.questions.length;
      const groupCard = document.createElement("div");
      groupCard.className =
        "rounded-lg border border-base-300 bg-base-100 p-4 shadow-sm space-y-3";

      const header = document.createElement("div");
      header.className =
        "flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between";

      const titleWrap = document.createElement("div");
      titleWrap.className = "flex flex-wrap items-center gap-2";
      const groupBadge = createIdToken(group.id, "group");

      const title = document.createElement("span");
      title.className = "font-medium text-base-content";
      title.textContent = group.title;

      titleWrap.appendChild(groupBadge);
      titleWrap.appendChild(title);

      header.appendChild(titleWrap);

      const headerMeta = document.createElement("div");
      headerMeta.className = "flex flex-wrap items-center gap-2";
      headerMeta.style.marginLeft = "auto";

      if (group.repeat) {
        const repeatLabel = group.repeat.maxCount
          ? `Repeat ×${group.repeat.maxCount}`
          : "Repeat";
        headerMeta.appendChild(createMetaBadge("repeat", repeatLabel));
      }

      const questionCount = document.createElement("span");
      questionCount.className = "text-xs text-base-content/60";
      questionCount.textContent = `${group.questions.length} question${
        group.questions.length === 1 ? "" : "s"
      }`;
      headerMeta.appendChild(questionCount);

      header.appendChild(headerMeta);
      groupCard.appendChild(header);

      if (group.description) {
        const description = document.createElement("p");
        description.className = "text-sm text-base-content/70";
        description.textContent = group.description;
        groupCard.appendChild(description);
      }

      if (group.questions.length) {
        const questionList = document.createElement("div");
        questionList.className = "space-y-2";

        group.questions.forEach((question, index) => {
          const questionRow = document.createElement("div");
          questionRow.className =
            "rounded-md border border-base-300 bg-base-200/60 p-3";

          const rowHeader = document.createElement("div");
          rowHeader.className =
            "flex flex-wrap items-center gap-2 justify-between";

          const questionWrap = document.createElement("div");
          questionWrap.className = "flex flex-wrap items-center gap-2";

          const questionBadge = createIdToken(question.id, "question");

          const questionTitle = document.createElement("span");
          questionTitle.className = "font-medium text-sm text-base-content";
          questionTitle.textContent = `${index + 1}. ${question.title}`;

          // Add red asterisk if question is required
          if (question.isRequired) {
            const asterisk = document.createElement("span");
            asterisk.className = "text-error";
            asterisk.textContent = "*";
            questionTitle.appendChild(asterisk);
          }

          questionWrap.appendChild(questionBadge);
          questionWrap.appendChild(questionTitle);
          rowHeader.appendChild(questionWrap);

          const rowMeta = document.createElement("div");
          rowMeta.className = "flex flex-wrap items-center gap-2";
          rowMeta.style.marginLeft = "auto";

          if (question.type) {
            const typePill = createIdToken(question.type, "info");
            typePill.classList.add("uppercase", "tracking-wide");
            rowMeta.appendChild(typePill);
          }

          if (rowMeta.childNodes.length) {
            rowHeader.appendChild(rowMeta);
          }

          questionRow.appendChild(rowHeader);

          if (question.description) {
            const questionDescription = document.createElement("p");
            questionDescription.className = "text-xs text-base-content/70 mt-2";
            questionDescription.textContent = question.description;
            questionRow.appendChild(questionDescription);
          }

          if (question.branches.length) {
            const branchList = document.createElement("div");
            branchList.className = "mt-2 space-y-1";

            question.branches.forEach((branch) => {
              const row = document.createElement("div");
              row.className =
                "flex items-center justify-between gap-2 rounded px-2 py-1 text-xs";
              row.style.backgroundColor = "hsl(var(--p) / 0.12)";
              row.style.border = "1px solid hsl(var(--p) / 0.3)";

              const when = document.createElement("span");
              when.className = "font-medium";
              when.textContent = `when ${branch.condition}`;

              const targetBadge = createMetaBadge(
                "branch",
                `{${branch.targetRaw}}`,
              );

              row.appendChild(when);
              row.appendChild(targetBadge);
              branchList.appendChild(row);
            });

            questionRow.appendChild(branchList);
          }

          questionList.appendChild(questionRow);
        });

        groupCard.appendChild(questionList);
      }

      previewContainer.appendChild(groupCard);
    });

    if (countBadge) {
      countBadge.classList.remove("hidden");
      countBadge.textContent = `${groups.length} group${
        groups.length === 1 ? "" : "s"
      }, ${totalQuestions} question${totalQuestions === 1 ? "" : "s"}`;
    }

    previewContainer.setAttribute("aria-busy", "false");
  };

  const updatePreview = () => {
    const parsed = parseStructure(textarea.value);
    renderStructure(parsed);
  };

  let scheduled = false;
  const scheduleUpdate = () => {
    if (scheduled) {
      return;
    }
    scheduled = true;
    requestAnimationFrame(() => {
      scheduled = false;
      updatePreview();
    });
  };

  textarea.addEventListener("input", scheduleUpdate);
  textarea.addEventListener("change", scheduleUpdate);

  updatePreview();
})();

// AI Assistant Tab Functionality
(() => {
  const tabManual = document.getElementById("tab-manual");
  const tabAI = document.getElementById("tab-ai");
  const manualContent = document.getElementById("manual-tab-content");
  const aiContent = document.getElementById("ai-tab-content");
  const phaseBadge = document.getElementById("llm-phase-badge");
  const chatMessages = document.getElementById("chat-messages");
  const userMessageInput = document.getElementById("user-message-input");
  const sendMessageBtn = document.getElementById("send-message-btn");
  const newSessionBtn = document.getElementById("new-session-btn");
  const aiLoading = document.getElementById("ai-loading");
  const manualMarkdownInput = document.getElementById("markdown-input");

  if (!tabManual || !tabAI || !manualContent || !aiContent) {
    return;
  }

  let conversationHistory = [];
  let sessionId = null;

  const setPhaseBadge = (phase) => {
    if (!phaseBadge) return;
    const p = (phase || "").toString().toLowerCase();
    phaseBadge.classList.remove("badge-info", "badge-success", "badge-outline");
    if (p === "planning") {
      phaseBadge.classList.add("badge-info");
      phaseBadge.textContent = "Planning";
    } else if (p === "implementation") {
      phaseBadge.classList.add("badge-success");
      phaseBadge.textContent = "Implementation";
    } else {
      phaseBadge.classList.add("badge-outline");
      phaseBadge.textContent = p ? p : "Idle";
    }
  };

  // initialize badge
  setPhaseBadge("planning");

  // Get session history elements
  const tabHistory = document.getElementById("tab-history");
  const historyContent = document.getElementById("history-tab-content");
  const sessionHistoryList = document.getElementById("session-history-list");

  // Manual Input sub-tabs
  const tabMarkdownInput = document.getElementById("tab-markdown-input");
  const tabFormatReference = document.getElementById("tab-format-reference");
  const markdownInputContent = document.getElementById(
    "markdown-input-content",
  );
  const formatReferenceContent = document.getElementById(
    "format-reference-content",
  );

  // Store current survey markdown
  let currentSurveyMarkdown = "";

  // Tab switching
  const switchTab = () => {
    if (tabManual.checked) {
      manualContent.classList.remove("hidden");
      aiContent.classList.add("hidden");
      if (historyContent) historyContent.classList.add("hidden");
    } else if (tabAI.checked) {
      manualContent.classList.add("hidden");
      aiContent.classList.remove("hidden");
      if (historyContent) historyContent.classList.add("hidden");
    } else if (tabHistory && tabHistory.checked) {
      manualContent.classList.add("hidden");
      aiContent.classList.add("hidden");
      if (historyContent) historyContent.classList.remove("hidden");
    }
  };

  tabManual.addEventListener("change", switchTab);
  tabAI.addEventListener("change", switchTab);

  if (tabHistory) {
    tabHistory.addEventListener("change", () => {
      switchTab();
      if (tabHistory.checked) {
        loadSessionHistory();
      }
    });
  }

  // Sub-tab switching for Manual Input
  const switchManualSubTab = () => {
    if (!tabMarkdownInput || !tabFormatReference) return;

    if (tabMarkdownInput.checked) {
      markdownInputContent.classList.remove("hidden");
      formatReferenceContent.classList.add("hidden");
    } else if (tabFormatReference.checked) {
      markdownInputContent.classList.add("hidden");
      formatReferenceContent.classList.remove("hidden");
    }
  };

  if (tabMarkdownInput) {
    tabMarkdownInput.addEventListener("change", switchManualSubTab);
  }
  if (tabFormatReference) {
    tabFormatReference.addEventListener("change", switchManualSubTab);
  }

  // Load session history
  const loadSessionHistory = async () => {
    if (!sessionHistoryList) return;

    // Show loading state
    sessionHistoryList.innerHTML = `
      <div class="text-sm text-base-content/70 text-center py-8">
        <span class="loading loading-spinner loading-md"></span>
        <p class="mt-2">Loading previous sessions...</p>
      </div>
    `;

    try {
      const response = await fetch(window.location.href, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]")
            .value,
        },
        body: JSON.stringify({
          action: "get_sessions",
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();

      if (data.error) {
        throw new Error(data.error);
      }

      displaySessionList(data.sessions);
    } catch (error) {
      console.error("Error loading sessions:", error);
      sessionHistoryList.innerHTML = `
        <div class="alert alert-error text-sm">
          <span>Error loading sessions: ${error.message}</span>
        </div>
      `;
    }
  };

  // Display session list
  const displaySessionList = (sessions) => {
    if (!sessions || sessions.length === 0) {
      sessionHistoryList.innerHTML = `
        <div class="text-sm text-base-content/70 text-center py-8">
          <p>No previous sessions found.</p>
          <p class="mt-2">Start a new conversation in the AI Assistant tab.</p>
        </div>
      `;
      return;
    }

    sessionHistoryList.innerHTML = "";

    sessions.forEach((session) => {
      const sessionCard = document.createElement("div");
      sessionCard.className = `card bg-base-200 border border-base-300 ${
        session.is_active ? "ring-2 ring-primary" : ""
      }`;

      const updatedDate = new Date(session.updated_at);
      const formattedDate = updatedDate.toLocaleDateString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });

      sessionCard.innerHTML = `
        <div class="card-body p-4">
          <div class="flex items-start justify-between gap-4">
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 mb-2">
                <span class="text-sm font-medium">${formattedDate}</span>
                ${
                  session.is_active
                    ? '<span class="badge badge-primary badge-sm">Active</span>'
                    : ""
                }
              </div>
              <p class="text-sm text-base-content/70 truncate">${
                session.last_message_preview || "No messages yet"
              }</p>
              <div class="flex gap-2 mt-2 text-xs text-base-content/60">
                <span>${session.message_count} message${
                  session.message_count !== 1 ? "s" : ""
                }</span>
                ${
                  session.has_markdown
                    ? '<span class="text-success">• Has markdown</span>'
                    : ""
                }
              </div>
            </div>
            <div class="flex flex-col gap-2">
              <button class="btn btn-sm btn-primary resume-session-btn" data-session-id="${
                session.id
              }">
                Resume
              </button>
              <button class="btn btn-sm btn-ghost view-session-btn" data-session-id="${
                session.id
              }">
                View
              </button>
            </div>
          </div>
        </div>
      `;

      sessionHistoryList.appendChild(sessionCard);
    });

    // Add event listeners to buttons using event delegation
    sessionHistoryList
      .querySelectorAll(".resume-session-btn")
      .forEach((btn) => {
        btn.addEventListener("click", () => {
          const sessionIdToResume = btn.dataset.sessionId;
          resumeSession(sessionIdToResume);
        });
      });

    sessionHistoryList.querySelectorAll(".view-session-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const sessionIdToView = btn.dataset.sessionId;
        viewSession(sessionIdToView);
      });
    });
  };

  // Resume session
  const resumeSession = async (sessionIdToResume) => {
    try {
      // Fetch session details
      const response = await fetch(window.location.href, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]")
            .value,
        },
        body: JSON.stringify({
          action: "get_session_details",
          session_id: sessionIdToResume,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();

      if (data.error) {
        throw new Error(data.error);
      }

      // Set session ID
      sessionId = sessionIdToResume;

      // Clear chat messages
      chatMessages.innerHTML = "";

      // Load conversation history
      conversationHistory = data.conversation_history || [];

      // Display all messages
      conversationHistory.forEach((msg) => {
        if (msg.role === "user" || msg.role === "assistant") {
          addMessageToChat(msg.content, msg.role === "user");
        }
      });

      // Load markdown if available
      if (data.current_markdown) {
        updateMarkdownOutput(data.current_markdown);
      }

      // Switch to AI tab
      tabAI.checked = true;
      switchTab();
    } catch (error) {
      console.error("Error resuming session:", error);
      alert(`Error resuming session: ${error.message}`);
    }
  };

  // View session
  const viewSession = (sessionIdToView) => {
    // TODO: Show modal with full conversation history
    console.log("Viewing session:", sessionIdToView);
  };

  // Auto-scroll chat to bottom
  const scrollChatToBottom = () => {
    if (chatMessages) {
      chatMessages.scrollTop = chatMessages.scrollHeight;
    }
  };

  // Add message to chat UI
  const addMessageToChat = (content, isUser = false) => {
    if (!chatMessages) return;

    const messageDiv = document.createElement("div");
    messageDiv.className = `chat ${isUser ? "chat-end" : "chat-start"}`;

    const bubble = document.createElement("div");
    bubble.className = `chat-bubble ${isUser ? "chat-bubble-primary" : ""}`;
    if (isUser) {
      bubble.textContent = content;
    } else {
      bubble.innerHTML = renderMarkdown(content);
    }

    messageDiv.appendChild(bubble);

    // Remove placeholder if exists
    const placeholder = chatMessages.querySelector(".text-center");
    if (placeholder) {
      placeholder.remove();
    }

    chatMessages.appendChild(messageDiv);
    scrollChatToBottom();
  };

  // Escape HTML entities
  const escapeHtml = (text) => {
    if (!text) return "";
    return text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  };

  // Simple markdown to HTML converter for chat messages
  const renderMarkdownCore = (text) => {
    if (!text) return "";

    // Escape HTML first
    let html = text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

    // Convert markdown syntax
    html = html
      // Bold
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      // Italic
      .replace(/\*(.+?)\*/g, "<em>$1</em>")
      // Code
      .replace(/`(.+?)`/g, '<code class="bg-base-300 px-1 rounded">$1</code>')
      // Lists (simple approach)
      .replace(/^\* (.+)$/gm, "<li>$1</li>")
      .replace(/^- (.+)$/gm, "<li>$1</li>")
      // Wrap lists
      .replace(/(<li>.*<\/li>)/gs, '<ul class="list-disc list-inside">$1</ul>')
      // Headings
      .replace(/^### (.+)$/gm, '<h3 class="font-bold text-base mt-2">$1</h3>')
      .replace(/^## (.+)$/gm, '<h2 class="font-bold text-lg mt-2">$1</h2>')
      .replace(/^# (.+)$/gm, '<h1 class="font-bold text-xl mt-2">$1</h1>')
      // Line breaks
      .replace(/\n/g, "<br>");

    return html;
  };

  const renderMarkdown = (text) => {
    if (!text) return "";

    // If the assistant included a 'Thinking Process' section, show it
    // as a pale inline alert inside the speech bubble to distinguish it
    // from the final conversational text.
    const thinkingIndex = text.search(/Thinking Process:?/i);
    let reasoningHtml = "";
    if (thinkingIndex !== -1) {
      const mainText = text.slice(0, thinkingIndex).trim();
      const reasoningText = text.slice(thinkingIndex).replace(/^[\s\S]*?:\s*/i, "");
      const mainHtml = renderMarkdownCore(mainText);
      const reasoningCore = renderMarkdownCore(reasoningText);
      if (reasoningCore) {
        reasoningHtml = `<div class=\"alert alert-info text-sm mt-2\">${reasoningCore}</div>`;
      }
      return mainHtml + reasoningHtml;
    }

    return renderMarkdownCore(text);
  };

  // Update markdown output in Manual Input tab
  const updateMarkdownOutput = (markdown) => {
    if (manualMarkdownInput && markdown) {
      // Update the manual input textarea
      manualMarkdownInput.value = markdown;
      // Trigger input event to update the preview
      manualMarkdownInput.dispatchEvent(new Event("input", { bubbles: true }));
    }
  };

  // Extract markdown from code blocks
  const extractMarkdownFromText = (text) => {
    // First try: Look for ```markdown ... ``` or ``` ... ``` code blocks
    const markdownMatch = text.match(/```(?:markdown)?\s*\n([\s\S]*?)```/);
    if (markdownMatch) {
      return markdownMatch[1].trim();
    }

    // Fallback: Look for markdown-like content (starts with # or ##)
    // This handles cases where LLM doesn't use code fences
    const lines = text.split("\n");
    let markdownLines = [];
    let foundMarkdownStart = false;

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();

      // Look for markdown heading that starts with # followed by space and text ending with {id}
      if (!foundMarkdownStart && /^#+\s+.+\s+\{[^}]+\}/.test(line)) {
        foundMarkdownStart = true;
      }

      if (foundMarkdownStart) {
        markdownLines.push(lines[i]);
      }
    }

    return markdownLines.length > 0 ? markdownLines.join("\n").trim() : null;
  };

  // Separate conversational text from markdown
  const separateConversationAndMarkdown = (text) => {
    const markdown = extractMarkdownFromText(text);

    if (!markdown) {
      return { conversation: text, markdown: null };
    }

    // Remove the markdown from conversation
    let conversation = text;

    // If it was in code fences, remove the whole block
    conversation = conversation.replace(/```(?:markdown)?\s*\n[\s\S]*?```/, "");

    // Otherwise remove the extracted markdown
    if (conversation === text) {
      conversation = conversation.replace(markdown, "");
    }

    conversation = conversation.trim();

    return { conversation, markdown };
  };

  // Send message to AI
  const sendMessage = async () => {
    const message = userMessageInput.value.trim();
    if (!message) {
      return;
    }

    // Add user message to UI
    addMessageToChat(message, true);
    conversationHistory.push({ role: "user", content: message });

    // Clear input
    userMessageInput.value = "";

    // Show loading
    aiLoading.classList.remove("hidden");
    sendMessageBtn.disabled = true;

    try {
      // Create a placeholder message element for streaming response
      const assistantMsgDiv = document.createElement("div");
      assistantMsgDiv.className = "chat chat-start";
      const bubble = document.createElement("div");
      bubble.className = "chat-bubble chat-bubble-secondary";
      bubble.textContent = "";
      assistantMsgDiv.appendChild(bubble);
      chatMessages.appendChild(assistantMsgDiv);
      scrollChatToBottom();

      let fullResponse = "";
      let currentMarkdown = "";

      // Use fetch and handle both SSE (streaming) and non-streaming JSON responses.
      const response = await fetch(window.location.href, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]")
            .value,
        },
        body: JSON.stringify({
          action: "ai_chat",
          message: message,
          session_id: sessionId,
          conversation_history: conversationHistory,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const contentType = (
        response.headers.get("content-type") || ""
      ).toLowerCase();

      // If the server returned a JSON payload (non-streaming), handle it simply.
      if (contentType.includes("application/json")) {
        const json = await response.json();
        if (json.error) {
          throw new Error(json.error || "AI returned an error");
        }

        // Prefer explicit markdown field when provided by server
        const payloadText = json.markdown || json.content || json.message || "";
        const { conversation, markdown } = separateConversationAndMarkdown(
          payloadText || "",
        );

        // Update chat bubble with conversational text (if any)
        if (conversation) {
          bubble.innerHTML = renderMarkdown(conversation);
        }

        // Only update manual input if we have markdown
        const markdownToUse = json.markdown || markdown;
        if (markdownToUse) {
          updateMarkdownOutput(markdownToUse);
          conversationHistory.push({ role: "assistant", content: payloadText });
        } else {
          // Assistant is asking clarifying questions — don't try to parse.
          conversationHistory.push({ role: "assistant", content: payloadText });
        }

        // Update phase badge if server included it
        setPhaseBadge(
          json.phase ||
            json.llm_phase ||
            (markdownToUse ? "implementation" : "planning"),
        );
        // Done with non-streaming flow
      } else {
        // Streaming SSE path
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let streamErrorOccurred = false;

        while (true) {
          const { done, value } = await reader.read();

          if (done) break;

          // Decode the chunk
          const chunk = decoder.decode(value, { stream: true });
          buffer += chunk;

          // Process complete SSE messages (each ends with \n\n)
          let boundary;
          while ((boundary = buffer.indexOf("\n\n")) !== -1) {
            const message = buffer.substring(0, boundary);
            buffer = buffer.substring(boundary + 2);

            // Each SSE message should start with "data: "
            if (message.startsWith("data: ")) {
              const jsonStr = message.substring(6).trim();
              if (!jsonStr) continue;

              try {
                const data = JSON.parse(jsonStr);

                if (data.error) {
                  // Display server-side error message in the chat UI without
                  // throwing to avoid noisy console parse errors.
                  const srvErr = document.createElement("div");
                  srvErr.className = "alert alert-error text-sm mt-2";
                  srvErr.textContent = `AI error: ${data.error}`;
                  chatMessages.appendChild(srvErr);
                  scrollChatToBottom();
                  streamErrorOccurred = true;
                  break;
                }

                if (data.session_id) {
                  sessionId = data.session_id;
                }

                if (data.chunk) {
                  fullResponse += data.chunk;
                  bubble.textContent = fullResponse;
                  scrollChatToBottom();
                }

                if (data.markdown) {
                  currentMarkdown = data.markdown;
                }
                // Update phase badge when provided in SSE messages
                if (data.phase || data.llm_phase) {
                  setPhaseBadge(data.phase || data.llm_phase);
                }

                if (data.done) {
                  // Use assistant_message if provided by the server, otherwise
                  // fall back to the accumulated streamed chunks.
                  const finalText = data.assistant_message || fullResponse;

                  // Separate conversation from markdown
                  const { conversation, markdown } =
                    separateConversationAndMarkdown(finalText);

                  // Update chat bubble with rendered conversational text
                  if (conversation) {
                    bubble.innerHTML = renderMarkdown(conversation);
                  } else {
                    bubble.innerHTML = renderMarkdown(
                      "I've updated the survey markdown.",
                    );
                  }

                  // Update conversation history with final assistant text
                  conversationHistory.push({
                    role: "assistant",
                    content: finalText,
                  });

                  // Only update manual input if we have markdown (from SSE or extracted)
                  const markdownToUse =
                    data.markdown || currentMarkdown || markdown;
                  if (markdownToUse) {
                    updateMarkdownOutput(markdownToUse);
                  }

                  // Update phase badge if provided
                  if (data.phase || data.llm_phase) {
                    setPhaseBadge(data.phase || data.llm_phase);
                  }
                }
              } catch (e) {
                // Avoid logging large LLM payloads; log concise error for debugging
                console.error("Error parsing SSE data:", e.message || e);
                // Show a friendly error to the user in the chat UI
                const errEl = document.createElement("div");
                errEl.className = "alert alert-error text-sm mt-2";
                errEl.textContent = `AI response error: ${e.message || "unexpected response"}`;
                chatMessages.appendChild(errEl);
                scrollChatToBottom();
                streamErrorOccurred = true;
                break;
              }
            }
          }
          if (streamErrorOccurred) break;
        }
        if (streamErrorOccurred) {
          // Abort streaming handling early
        }
      }
    } catch (error) {
      console.error("Error sending message:", error);
      const errorMsg = document.createElement("div");
      errorMsg.className = "alert alert-error text-sm";
      errorMsg.textContent = `Error: ${error.message}`;
      chatMessages.appendChild(errorMsg);
      scrollChatToBottom();
    } finally {
      aiLoading.classList.add("hidden");
      sendMessageBtn.disabled = false;
      userMessageInput.focus();
    }
  };

  // New session handler
  const startNewSession = () => {
    conversationHistory = [];
    sessionId = null;
    chatMessages.innerHTML = `
      <div class="text-sm text-base-content/70 text-center py-8">
        Start a conversation to generate your survey using AI. Describe what you want to measure, and the assistant will help you create the markdown.
      </div>
    `;
    // Clear manual input
    if (manualMarkdownInput) {
      manualMarkdownInput.value = "";
      manualMarkdownInput.dispatchEvent(new Event("input", { bubbles: true }));
    }
  };

  // Event listeners
  if (sendMessageBtn) {
    sendMessageBtn.addEventListener("click", sendMessage);
  }

  if (userMessageInput) {
    userMessageInput.addEventListener("keypress", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });
  }

  if (newSessionBtn) {
    newSessionBtn.addEventListener("click", startNewSession);
  }

  // Handle initial tab selection from data attribute
  const scriptTag = document.querySelector("script[data-initial-tab]");
  if (scriptTag) {
    const initialTab = scriptTag.dataset.initialTab;
    if (initialTab === "ai") {
      const tabAi = document.getElementById("tab-ai");
      const manualContent = document.getElementById("manual-tab-content");
      const aiContent = document.getElementById("ai-tab-content");
      const historyContent = document.getElementById("history-tab-content");

      if (tabAi) tabAi.checked = true;
      if (manualContent) manualContent.classList.add("hidden");
      if (aiContent) aiContent.classList.remove("hidden");
      if (historyContent) historyContent.classList.add("hidden");
    } else if (initialTab === "history") {
      const tabHistory = document.getElementById("tab-history");
      const manualContent = document.getElementById("manual-tab-content");
      const aiContent = document.getElementById("ai-tab-content");
      const historyContent = document.getElementById("history-tab-content");

      if (tabHistory) tabHistory.checked = true;
      if (manualContent) manualContent.classList.add("hidden");
      if (aiContent) aiContent.classList.add("hidden");
      if (historyContent) historyContent.classList.remove("hidden");
    }
    // manual is default, already checked in HTML
  }
})();
