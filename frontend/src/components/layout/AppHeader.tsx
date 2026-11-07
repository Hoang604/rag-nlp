import React from 'react';
import { BookOpen, Monitor, Moon, Sun } from 'lucide-react';
import { useI18n } from '../../i18n/I18nContext';
import { Lang, MessageKey } from '../../i18n/messages';
import { ThemeChoice, useTheme } from '../../hooks/useTheme';

export type TabId = 'answer' | 'eval' | 'explorer';

const TABS: { id: TabId; label: MessageKey }[] = [
  { id: 'answer', label: 'nav.answer' },
  { id: 'eval', label: 'nav.eval' },
  { id: 'explorer', label: 'nav.explorer' },
];

const THEMES: { id: ThemeChoice; label: MessageKey; icon: typeof Sun }[] = [
  { id: 'light', label: 'theme.light', icon: Sun },
  { id: 'system', label: 'theme.system', icon: Monitor },
  { id: 'dark', label: 'theme.dark', icon: Moon },
];

const LANGS: { id: Lang; label: string }[] = [
  { id: 'vi', label: 'VI' },
  { id: 'en', label: 'EN' },
];

const segment = (active: boolean) =>
  `flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors duration-200 ${
    active ? 'bg-slate-100 text-slate-950' : 'text-slate-400 hover:text-slate-100'
  }`;

interface AppHeaderProps {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
}

export const AppHeader: React.FC<AppHeaderProps> = ({ activeTab, onTabChange }) => {
  const { t, lang, setLang } = useI18n();
  const { choice, set } = useTheme();

  return (
    <header className="flex flex-wrap items-center gap-x-8 gap-y-3 border-b border-slate-800 bg-slate-950 px-5 py-3 sm:px-8">
      <div className="flex items-center gap-2.5">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-white">
          <BookOpen className="h-4 w-4" />
        </span>
        <span className="text-sm font-semibold tracking-tight text-slate-100">
          {t('app.title')}
        </span>
      </div>

      <nav className="flex gap-1" aria-label="Menu">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            data-testid={`tab-${tab.id}`}
            onClick={() => onTabChange(tab.id)}
            aria-current={activeTab === tab.id ? 'page' : undefined}
            className={`border-b-2 px-3 py-1.5 text-sm font-medium transition-colors duration-200 ${
              activeTab === tab.id
                ? 'border-brand-500 text-slate-100'
                : 'border-transparent text-slate-400 hover:text-slate-100'
            }`}
          >
            {t(tab.label)}
          </button>
        ))}
      </nav>

      <div className="ml-auto flex items-center gap-3">
        <div
          role="group"
          aria-label={t('lang.label')}
          className="flex gap-0.5 rounded-lg border border-slate-700 bg-slate-900 p-0.5"
        >
          {LANGS.map((item) => (
            <button
              key={item.id}
              type="button"
              data-testid={`lang-${item.id}`}
              onClick={() => setLang(item.id)}
              aria-pressed={lang === item.id}
              className={segment(lang === item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
        <div
          role="group"
          aria-label={t('theme.label')}
          className="flex gap-0.5 rounded-lg border border-slate-700 bg-slate-900 p-0.5"
        >
          {THEMES.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                type="button"
                data-testid={`theme-${item.id}`}
                onClick={() => set(item.id)}
                aria-pressed={choice === item.id}
                title={t(item.label)}
                className={segment(choice === item.id)}
              >
                <Icon className="h-3.5 w-3.5" />
                <span className="hidden md:inline">{t(item.label)}</span>
              </button>
            );
          })}
        </div>
      </div>
    </header>
  );
};
