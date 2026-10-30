import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { Lang, MessageKey, messages } from './messages';

interface I18nValue {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: (key: MessageKey, vars?: Record<string, string | number>) => string;
}

const KEY = 'lang';

const initialLang = (): Lang => {
  try {
    const stored = localStorage.getItem(KEY);
    if (stored === 'vi' || stored === 'en') return stored;
  } catch {
    return 'vi';
  }
  return 'vi';
};

const I18nContext = createContext<I18nValue | null>(null);

export const I18nProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [lang, setLang] = useState<Lang>(initialLang);

  useEffect(() => {
    document.documentElement.lang = lang;
    try {
      localStorage.setItem(KEY, lang);
    } catch {
      return;
    }
  }, [lang]);

  const t = useCallback<I18nValue['t']>(
    (key, vars) => {
      const template: string = messages[lang][key];
      if (!vars) return template;
      return template.replace(/\{(\w+)\}/g, (_, name: string) => String(vars[name] ?? ''));
    },
    [lang]
  );

  const value = useMemo(() => ({ lang, setLang, t }), [lang, t]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
};

export const useI18n = (): I18nValue => {
  const value = useContext(I18nContext);
  if (!value) throw new Error('useI18n must be used inside I18nProvider');
  return value;
};
