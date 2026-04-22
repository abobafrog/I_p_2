import { useEffect, type RefObject } from "react";

import { translateTexts } from "./api";
import type { AppLocale } from "./i18n";

const TRANSLATABLE_ATTRIBUTES = ["placeholder", "aria-label", "title", "alt"] as const;
const SKIP_TAGS = new Set([
  "CODE",
  "KBD",
  "NOSCRIPT",
  "PRE",
  "SAMP",
  "SCRIPT",
  "STYLE",
  "TEXTAREA",
]);
const TRANSIENT_DELAY_MS = 40;
const SOURCE_CHARSET: Record<AppLocale, RegExp> = {
  ru: /[А-Яа-яЁё]/u,
  en: /[A-Za-z]/u,
  zh: /[\u4e00-\u9fff]/u,
};

type TranslationState = {
  locale: AppLocale;
  source: string;
  translated: string;
};

type TranslationTarget = {
  sourceText: string;
  apply: (translatedText: string) => void;
};

const TEXT_STATE = new WeakMap<Text, TranslationState>();
const ATTRIBUTE_STATE = new WeakMap<Element, Map<string, TranslationState>>();
export const SOURCE_LOCALE: AppLocale = "ru";

function shouldSkipElement(element: Element | null) {
  if (!element) {
    return true;
  }

  if (element.closest('[translate="no"], [data-no-translate="true"]')) {
    return true;
  }

  return SKIP_TAGS.has(element.tagName);
}

function shouldTranslateText(text: string, sourceLocale: AppLocale) {
  const stripped = text.trim();
  if (!stripped) {
    return false;
  }

  if (!SOURCE_CHARSET[sourceLocale].test(stripped)) {
    return false;
  }

  if (stripped.includes("=>") || stripped.includes(":=") || stripped.includes("++") || stripped.includes("--")) {
    return false;
  }

  if (/[{}[\];`]/.test(stripped)) {
    return false;
  }

  if ((stripped.includes("(") || stripped.includes(")")) && !/\s/.test(stripped)) {
    return false;
  }

  if (stripped.includes("=") && stripped.split(/\s+/).length <= 4 && !/[.!?]/.test(stripped)) {
    return false;
  }

  return true;
}

function preserveWhitespace(sourceText: string, translatedText: string) {
  const prefixMatch = sourceText.match(/^\s*/);
  const suffixMatch = sourceText.match(/\s*$/);
  const prefix = prefixMatch?.[0] ?? "";
  const suffix = suffixMatch?.[0] ?? "";
  return `${prefix}${translatedText}${suffix}`;
}

function restoreRootToSource(root: HTMLElement, sourceLocale: AppLocale) {
  let restoredCount = 0;

  const textWalker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let currentNode = textWalker.nextNode();

  while (currentNode) {
    const textNode = currentNode as Text;
    const state = TEXT_STATE.get(textNode);
    if (state && state.locale !== sourceLocale && state.source !== state.translated) {
      textNode.nodeValue = state.source;
      TEXT_STATE.set(textNode, {
        locale: sourceLocale,
        source: state.source,
        translated: state.source,
      });
      restoredCount += 1;
    }

    currentNode = textWalker.nextNode();
  }

  const elements = root.querySelectorAll<HTMLElement>("*");
  elements.forEach((element) => {
    const stateMap = ATTRIBUTE_STATE.get(element);
    if (!stateMap) {
      return;
    }

    TRANSLATABLE_ATTRIBUTES.forEach((attribute) => {
      const state = stateMap.get(attribute);
      if (!state || state.locale === sourceLocale || state.source === state.translated) {
        return;
      }

      element.setAttribute(attribute, state.source);
      stateMap.set(attribute, {
        locale: sourceLocale,
        source: state.source,
        translated: state.source,
      });
      restoredCount += 1;
    });
  });

  return restoredCount;
}

function getSourceText(
  currentValue: string,
  state: TranslationState | undefined,
  sourceLocale: AppLocale,
) {
  if (shouldTranslateText(currentValue, sourceLocale)) {
    return currentValue;
  }

  if (state && shouldTranslateText(state.source, sourceLocale)) {
    return state.source;
  }

  return null;
}

function collectTextNodeTargets(
  root: HTMLElement,
  sourceLocale: AppLocale,
  locale: AppLocale,
): TranslationTarget[] {
  const targets: TranslationTarget[] = [];
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let currentNode = walker.nextNode();

  while (currentNode) {
    const textNode = currentNode as Text;
    const currentValue = textNode.nodeValue ?? "";
    const state = TEXT_STATE.get(textNode);
    const sourceText = getSourceText(currentValue, state, sourceLocale);

    if (sourceText && !(state && state.locale === locale && state.translated === currentValue)) {
      targets.push({
        sourceText,
        apply: (translatedText: string) => {
          const nextValue = preserveWhitespace(sourceText, translatedText);
          textNode.nodeValue = nextValue;
          TEXT_STATE.set(textNode, {
            locale,
            source: sourceText,
            translated: nextValue,
          });
        },
      });
    }

    currentNode = walker.nextNode();
  }

  return targets;
}

function collectAttributeTargets(
  root: HTMLElement,
  sourceLocale: AppLocale,
  locale: AppLocale,
): TranslationTarget[] {
  const targets: TranslationTarget[] = [];
  const elements = root.querySelectorAll<HTMLElement>("*");

  elements.forEach((element) => {
    if (shouldSkipElement(element)) {
      return;
    }

    let stateMap = ATTRIBUTE_STATE.get(element);
    if (!stateMap) {
      stateMap = new Map<string, TranslationState>();
      ATTRIBUTE_STATE.set(element, stateMap);
    }

    TRANSLATABLE_ATTRIBUTES.forEach((attribute) => {
      const value = element.getAttribute(attribute);
      if (!value) {
        return;
      }

      const state = stateMap.get(attribute);
      const sourceText = getSourceText(value, state, sourceLocale);
      if (!sourceText || (state && state.locale === locale && state.translated === value)) {
        return;
      }

      targets.push({
        sourceText,
        apply: (translatedText: string) => {
          const nextValue = preserveWhitespace(sourceText, translatedText);
          element.setAttribute(attribute, nextValue);
          stateMap?.set(attribute, {
            locale,
            source: sourceText,
            translated: nextValue,
          });
        },
      });
    });
  });

  return targets;
}

function collectTranslationTargets(
  root: HTMLElement,
  sourceLocale: AppLocale,
  locale: AppLocale,
): TranslationTarget[] {
  return [
    ...collectTextNodeTargets(root, sourceLocale, locale),
    ...collectAttributeTargets(root, sourceLocale, locale),
  ];
}

async function translateSourceTexts(
  texts: string[],
  sourceLocale: AppLocale,
  targetLocale: AppLocale,
) {
  if (texts.length === 0 || sourceLocale === targetLocale) {
    return texts.slice();
  }

  try {
    const response = await translateTexts(texts, targetLocale);
    return response.texts;
  } catch {
    return texts.slice();
  }
}

async function translateTargets(
  root: HTMLElement,
  sourceLocale: AppLocale,
  locale: AppLocale,
  isCancelled: () => boolean = () => false,
) {
  if (sourceLocale === locale) {
    return restoreRootToSource(root, sourceLocale);
  }

  const targets = collectTranslationTargets(root, sourceLocale, locale);
  if (targets.length === 0) {
    return 0;
  }

  const sources = Array.from(new Set(targets.map((target) => target.sourceText)));
  const translatedBySource = new Map<string, string>();
  const translatedTexts = await translateSourceTexts(sources, sourceLocale, locale);
  if (isCancelled()) {
    return 0;
  }

  sources.forEach((sourceText, index) => {
    translatedBySource.set(sourceText, translatedTexts[index] ?? sourceText);
  });

  let translatedCount = 0;
  targets.forEach((target) => {
    const translatedText = translatedBySource.get(target.sourceText) ?? target.sourceText;
    if (translatedText !== target.sourceText) {
      translatedCount += 1;
    }
    target.apply(translatedText);
  });

  return translatedCount;
}

export function useAutoPageTranslation(
  rootRef: RefObject<HTMLElement | null>,
  sourceLocale: AppLocale,
  locale: AppLocale,
  refreshToken = 0,
) {
  useEffect(() => {
    const root = rootRef.current;
    if (!root) {
      return;
    }

    let cancelled = false;
    let timerId = window.setTimeout(() => {
      if (!cancelled) {
        void translateTargets(root, sourceLocale, locale, () => cancelled).catch(() => {
          // Keep the original text if translation fails.
        });
      }
    }, 0);

    const observer = new MutationObserver(() => {
      window.clearTimeout(timerId);
      timerId = window.setTimeout(() => {
        if (!cancelled) {
          void translateTargets(root, sourceLocale, locale, () => cancelled).catch(() => {
            // Keep the original text if translation fails.
          });
        }
      }, TRANSIENT_DELAY_MS);
    });

    observer.observe(root, {
      attributes: true,
      attributeFilter: [...TRANSLATABLE_ATTRIBUTES],
      childList: true,
      characterData: true,
      subtree: true,
    });

    return () => {
      cancelled = true;
      window.clearTimeout(timerId);
      observer.disconnect();
    };
  }, [locale, refreshToken, rootRef, sourceLocale]);
}

export function useAutoDocumentTitleTranslation(
  sourceTitle: string,
  sourceLocale: AppLocale,
  locale: AppLocale,
  refreshToken = 0,
) {
  useEffect(() => {
    let cancelled = false;

    void translateSourceTexts([sourceTitle], sourceLocale, locale)
      .then((response) => {
        if (!cancelled) {
          document.title = response[0] ?? sourceTitle;
        }
      })
      .catch(() => {
        if (!cancelled) {
          document.title = sourceTitle;
        }
      });

    return () => {
      cancelled = true;
    };
  }, [locale, refreshToken, sourceLocale, sourceTitle]);
}
