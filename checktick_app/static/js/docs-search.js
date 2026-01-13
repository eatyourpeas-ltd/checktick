/**
 * Documentation Search Component
 * Pure vanilla JavaScript - no dependencies
 */

class DocSearch {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.searchIndex = null;
    this.isLoading = false;
    this.init();
  }

  async init() {
    await this.loadIndex();
    this.render();
    this.attachEventListeners();
  }

  async loadIndex() {
    this.isLoading = true;
    try {
      const response = await fetch("/docs/search/index.json");
      const data = await response.json();
      this.searchIndex = data.index;
    } catch (error) {
      console.error("Failed to load search index:", error);
      this.searchIndex = [];
    } finally {
      this.isLoading = false;
    }
  }

  render() {
    this.container.innerHTML = `
      <div>
        <div class="input input-sm">
          <span>🔍</span>
          <input
            type="search"
            id="doc-search-input"
            placeholder="Search docs..."
            class="grow"
            autocomplete="off"
          />
        </div>
        <div id="doc-search-results" class="search-results hidden"></div>
      </div>
    `;
  }

  attachEventListeners() {
    const input = document.getElementById("doc-search-input");
    const resultsContainer = document.getElementById("doc-search-results");

    let debounceTimer;
    input.addEventListener("input", (e) => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        const query = e.target.value.trim();
        if (query.length >= 2) {
          const results = this.search(query);
          this.displayResults(results, query);
        } else {
          resultsContainer.classList.add("hidden");
        }
      }, 200);
    });

    // Close results when clicking outside
    document.addEventListener("click", (e) => {
      if (!this.container.contains(e.target)) {
        resultsContainer.classList.add("hidden");
      }
    });

    // Show results when input is focused with existing query
    input.addEventListener("focus", () => {
      if (input.value.trim().length >= 2) {
        resultsContainer.classList.remove("hidden");
      }
    });
  }

  search(query) {
    if (!this.searchIndex || this.searchIndex.length === 0) {
      return [];
    }

    const queryLower = query.toLowerCase();
    const terms = queryLower.split(/\s+/).filter((t) => t.length > 0);

    // Check if it's a phrase search (contains quotes)
    const isPhraseSearch = query.includes('"');
    const phrase = isPhraseSearch
      ? query.match(/"([^"]+)"/)?.[1]?.toLowerCase()
      : null;

    const results = this.searchIndex.map((doc) => {
      let score = 0;
      const titleLower = doc.title.toLowerCase();
      const contentLower = doc.content.toLowerCase();
      const headingsLower = doc.headings.map((h) => h.toLowerCase()).join(" ");

      // Phrase search
      if (phrase) {
        if (titleLower.includes(phrase)) score += 100;
        if (headingsLower.includes(phrase)) score += 50;
        if (contentLower.includes(phrase)) score += 20;
      } else {
        // Term-based search
        terms.forEach((term) => {
          // Title matches (highest weight)
          if (titleLower.includes(term)) {
            score += titleLower === term ? 100 : 50;
          }

          // Heading matches (medium weight)
          if (headingsLower.includes(term)) {
            score += 30;
          }

          // Content matches (lower weight)
          const contentMatches = (
            contentLower.match(new RegExp(term, "g")) || []
          ).length;
          score += Math.min(contentMatches * 5, 25);
        });
      }

      // Find best snippet with highlighted terms
      const snippet = this.extractSnippet(doc.content, terms, phrase);

      return { ...doc, score, snippet };
    });

    // Filter and sort by score
    return results
      .filter((r) => r.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, 10);
  }

  extractSnippet(content, terms, phrase) {
    const searchTerm = phrase || terms[0];
    if (!searchTerm) return content.substring(0, 150) + "...";

    const contentLower = content.toLowerCase();
    const index = contentLower.indexOf(searchTerm);

    if (index === -1) {
      return content.substring(0, 150) + "...";
    }

    // Extract context around the match
    const start = Math.max(0, index - 60);
    const end = Math.min(content.length, index + searchTerm.length + 90);
    let snippet = content.substring(start, end);

    // Add ellipsis
    if (start > 0) snippet = "..." + snippet;
    if (end < content.length) snippet = snippet + "...";

    return snippet;
  }

  displayResults(results, query) {
    const resultsContainer = document.getElementById("doc-search-results");

    if (results.length === 0) {
      resultsContainer.innerHTML = `
        <div class="search-no-results">
          No results found for "${this.escapeHtml(query)}"
        </div>
      `;
      resultsContainer.classList.remove("hidden");
      return;
    }

    const terms = query
      .toLowerCase()
      .split(/\s+/)
      .filter((t) => t.length > 0);
    const phrase = query.match(/"([^"]+)"/)?.[1];

    resultsContainer.innerHTML = `
      <div class="search-results-header">
        Found ${results.length} result${results.length !== 1 ? "s" : ""}
      </div>
      ${results
        .map(
          (result) => `
        <a href="${result.url}" class="search-result-item">
          <div class="search-result-title">
            ${this.highlightText(result.title, terms, phrase)}
          </div>
          <div class="search-result-category">
            ${this.formatCategory(result.category)}
          </div>
          <div class="search-result-snippet">
            ${this.highlightText(result.snippet, terms, phrase)}
          </div>
        </a>
      `
        )
        .join("")}
    `;

    resultsContainer.classList.remove("hidden");
  }

  highlightText(text, terms, phrase) {
    const escaped = this.escapeHtml(text);

    if (phrase) {
      const regex = new RegExp(`(${this.escapeRegex(phrase)})`, "gi");
      return escaped.replace(regex, "<mark>$1</mark>");
    }

    let highlighted = escaped;
    terms.forEach((term) => {
      const regex = new RegExp(`(${this.escapeRegex(term)})`, "gi");
      highlighted = highlighted.replace(regex, "<mark>$1</mark>");
    });

    return highlighted;
  }

  formatCategory(category) {
    const categoryNames = {
      "getting-started": "📚 Getting Started",
      features: "✨ Features",
      "self-hosting": "🖥️ Self-Hosting",
      configuration: "⚙️ Configuration",
      security: "🔒 Security",
      "data-governance": "📊 Data Governance",
      api: "🔧 API & Development",
      testing: "🧪 Testing",
      internationalisation: "🌍 Internationalisation",
      "accessibility-and-inclusion": "♿ Accessibility",
      "getting-involved": "🤝 Contributing",
      "dspt-overview": "🏥 DSPT Overview",
      other: "📄 Other",
    };

    return categoryNames[category] || category;
  }

  escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  escapeRegex(str) {
    return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }
}

// Initialize on page load
document.addEventListener("DOMContentLoaded", () => {
  const searchContainer = document.getElementById("doc-search-container");
  if (searchContainer) {
    new DocSearch("doc-search-container");
  }
});
