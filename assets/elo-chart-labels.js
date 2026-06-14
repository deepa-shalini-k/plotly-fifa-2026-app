(function () {
  const containerSelector = ".elo-nivo-chart[data-team-code-map]";
  const textSelector = "svg text";
  let queued = false;

  function parseCodeMap(container) {
    try {
      return JSON.parse(container.dataset.teamCodeMap || "{}");
    } catch (error) {
      return {};
    }
  }

  function getTeamName(label) {
    const testId = label.getAttribute("data-testid") || "";
    const prefix = testId.match(/^label\.(?:start|end)\.(.+)$/);
    if (prefix && prefix[1]) {
      return prefix[1];
    }

    return label.dataset.originalLabel || label.textContent.trim();
  }

  function applyLabels(root) {
    const scope = root && root.querySelectorAll ? root : document;
    const containers = [];

    if (scope.matches && scope.matches(containerSelector)) {
      containers.push(scope);
    }

    scope.querySelectorAll(containerSelector).forEach((container) => {
      containers.push(container);
    });

    containers.forEach((container) => {
      const codeMap = parseCodeMap(container);

      container.querySelectorAll(textSelector).forEach((label) => {
        const currentText = label.textContent.trim();
        const originalLabel = getTeamName(label);
        const teamName = codeMap[originalLabel] ? originalLabel : currentText;
        const code = codeMap[teamName];
        if (code && label.textContent !== code) {
          if (!label.dataset.originalLabel) {
            label.dataset.originalLabel = teamName;
          }
          label.textContent = code;
        }
      });
    });
  }

  function queueApply(root) {
    if (queued) {
      return;
    }

    queued = true;
    window.requestAnimationFrame(() => {
      queued = false;
      applyLabels(root || document);
    });
  }

  function init() {
    applyLabels(document);

    const observer = new MutationObserver((mutations) => {
      if (mutations.length > 0) {
        queueApply(document);
      }
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true,
      characterData: true,
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
