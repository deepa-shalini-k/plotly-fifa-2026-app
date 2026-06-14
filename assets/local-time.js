(function () {
  const selector = ".local-time[data-utc-iso]";
  const OFFSET_TIME_ZONE_NAME_RE = /^(?:GMT|UTC)(?:[+-]\d{1,2}(?::\d{2})?)?$/i;
  const IGNORED_ABBREVIATION_WORDS = new Set(["and", "of", "the"]);

  function detectTimeZone() {
    try {
      const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
      return typeof timeZone === "string" && timeZone ? timeZone : "UTC";
    } catch (error) {
      return "UTC";
    }
  }

  function getPart(parts, type) {
    const part = parts.find((item) => item.type === type);
    return part ? part.value : "";
  }

  function getPreferredLocales() {
    if (typeof navigator === "undefined") {
      return undefined;
    }

    if (Array.isArray(navigator.languages) && navigator.languages.length > 0) {
      return navigator.languages;
    }

    if (typeof navigator.language === "string" && navigator.language) {
      return [navigator.language];
    }

    return undefined;
  }

  function getTimeZoneName(date, timeZone, locales, timeZoneName) {
    try {
      const parts = new Intl.DateTimeFormat(locales, {
        timeZone,
        timeZoneName,
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      }).formatToParts(date);
      return getPart(parts, "timeZoneName");
    } catch (error) {
      return "";
    }
  }

  function isOffsetStyleTimeZoneName(value) {
    return OFFSET_TIME_ZONE_NAME_RE.test((value || "").trim());
  }

  function abbreviateLongTimeZoneName(value) {
    const words = (value || "")
      .split(/\s+/)
      .map((word) => word.replace(/[^A-Za-z]/g, ""))
      .filter((word) => word && !IGNORED_ABBREVIATION_WORDS.has(word.toLowerCase()));

    if (words.length === 0) {
      return "";
    }

    const abbreviation = words.map((word) => word[0].toUpperCase()).join("");
    return abbreviation.length >= 2 ? abbreviation : "";
  }

  function resolveTimeZoneLabel(date, timeZone) {
    if (timeZone === "UTC") {
      return "UTC";
    }

    const preferredLocales = getPreferredLocales();
    const preferredShort = getTimeZoneName(date, timeZone, preferredLocales, "short");
    if (preferredShort && !isOffsetStyleTimeZoneName(preferredShort)) {
      return preferredShort;
    }

    const englishLong = getTimeZoneName(date, timeZone, "en", "long");
    const derivedAbbreviation = abbreviateLongTimeZoneName(englishLong);
    if (derivedAbbreviation) {
      return derivedAbbreviation;
    }

    const englishShort = getTimeZoneName(date, timeZone, "en", "short");
    if (englishShort && !isOffsetStyleTimeZoneName(englishShort)) {
      return englishShort;
    }

    return preferredShort || englishShort || "UTC";
  }

  function formatUtcIso(utcIso, formatStyle, showTimezone) {
    const date = new Date(utcIso);
    if (Number.isNaN(date.getTime())) {
      return null;
    }

    const timeZone = detectTimeZone();

    if (formatStyle === "date_iso") {
      const parts = new Intl.DateTimeFormat("en-CA", {
        timeZone,
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
      }).formatToParts(date);

      return {
        value: `${getPart(parts, "year")}-${getPart(parts, "month")}-${getPart(parts, "day")}`,
        zone: "",
      };
    }

    const timeZoneLabel = showTimezone ? resolveTimeZoneLabel(date, timeZone) : "";
    const options = { timeZone };
    if (formatStyle === "time") {
      options.hour = "2-digit";
      options.minute = "2-digit";
      options.hour12 = false;
    } else if (formatStyle === "date") {
      options.day = "2-digit";
      options.month = "short";
      options.year = "numeric";
    } else {
      options.day = "2-digit";
      options.month = "short";
      options.hour = "2-digit";
      options.minute = "2-digit";
      options.hour12 = false;
    }

    const parts = new Intl.DateTimeFormat("en-GB", options).formatToParts(date);
    if (formatStyle === "time") {
      return {
        value: `${getPart(parts, "hour")}:${getPart(parts, "minute")}`,
        zone: timeZoneLabel,
      };
    }

    if (formatStyle === "date") {
      return {
        value: `${getPart(parts, "day")} ${getPart(parts, "month")} ${getPart(parts, "year")}`,
        zone: "",
      };
    }

    return {
      value: `${getPart(parts, "day")} ${getPart(parts, "month")} · ${getPart(parts, "hour")}:${getPart(parts, "minute")}`,
      zone: timeZoneLabel,
    };
  }

  function localizeNode(node) {
    const utcIso = node.dataset.utcIso;
    if (!utcIso) {
      return;
    }

    const formatStyle = node.dataset.localTimeFormat || "datetime";
    const showTimezone = node.dataset.localTimeShowTimezone !== "false";
    const formatted = formatUtcIso(utcIso, formatStyle, showTimezone);
    if (!formatted) {
      return;
    }

    const valueNode = node.querySelector(".local-time-value");
    const zoneNode = node.querySelector(".local-time-zone");

    if (valueNode) {
      valueNode.textContent = formatted.value;
    } else {
      node.textContent = formatted.value;
    }

    if (zoneNode) {
      zoneNode.textContent = showTimezone ? formatted.zone || "UTC" : "";
    }
  }
  function localizeTree(root) {
    if (!root) {
      return;
    }

    if (root.matches && root.matches(selector)) {
      localizeNode(root);
    }

    root.querySelectorAll(selector).forEach(localizeNode);
  }

  function init() {
    localizeTree(document);

    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        mutation.addedNodes.forEach((node) => {
          if (node.nodeType === Node.ELEMENT_NODE) {
            localizeTree(node);
          }
        });
      });
    });

    observer.observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
