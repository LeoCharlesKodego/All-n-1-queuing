import { createContext, useContext, useEffect, useMemo, useState } from "react";
import en from "./i18n/en.js";
import fil from "./i18n/fil.js";

export const catalogs = { en, fil };
export const LANGUAGES = [
  { code: "en", label: "English", short: "EN" },
  { code: "fil", label: "Filipino", short: "FIL" },
];

export function translate(lang, key, vars) {
  const text = catalogs[lang]?.[key] ?? en[key] ?? key;
  if (!vars) return text;
  return text.replace(/\{(\w+)\}/g, (_, name) => (vars[name] == null ? "" : String(vars[name])));
}

const STORAGE_KEY = "queue_lang";
export const LanguageContext = createContext({ lang: "en", setLang: () => {}, t: (k) => k });

export function useLanguageState(defaultLang = "en") {
  const [lang, setLangState] = useState(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved && catalogs[saved] ? saved : defaultLang;
  });
  useEffect(() => {
    if (defaultLang && catalogs[defaultLang] && !localStorage.getItem(STORAGE_KEY)) {
      setLangState(defaultLang);
    }
  }, [defaultLang]);

  const setLang = (next) => {
    localStorage.setItem(STORAGE_KEY, next);
    setLangState(next);
    document.documentElement.lang = next === "fil" ? "fil" : "en";
  };

  const value = useMemo(
    () => ({ lang, setLang, t: (key, vars) => translate(lang, key, vars) }),
    [lang]
  );
  return value;
}

export function LanguageProvider({ value, children }) {
  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useT() {
  return useContext(LanguageContext);
}

export function LanguageSwitch({ compact = false }) {
  const { lang, setLang } = useT();
  return (
    <div className={`lang-switch ${compact ? "compact" : ""}`} role="group" aria-label="Language">
      {LANGUAGES.map((l) => (
        <button
          key={l.code}
          type="button"
          className={lang === l.code ? "active" : ""}
          onClick={() => setLang(l.code)}
        >
          {compact ? l.short : l.label}
        </button>
      ))}
    </div>
  );
}

export function localized(obj, lang, base) {
  if (!obj) return "";
  const suffix = lang === "fil" ? "fil" : "en";
  return obj[`${base}_${suffix}`] ?? obj[`${base}_en`] ?? "";
}
