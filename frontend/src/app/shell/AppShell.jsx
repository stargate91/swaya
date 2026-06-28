import { Suspense, useState, useEffect, useRef } from 'react';
import { Outlet, useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import AppClosePrompt from './AppClosePrompt';
import WindowTitlebar from './WindowTitlebar';
import Sidebar from './Sidebar';
import Spinner from '../ui/Spinner';
import { useSettingsQuery, useScanStatusQuery } from '../queries';
import { useUi } from '../providers/UiProvider';
import { useTranslation } from '../providers/LanguageContext';
import api from '../lib/api';

const getBulkImportBannerStorageKey = (adultOnly) => adultOnly ? 'showBulkImportBanner:nsfw' : 'showBulkImportBanner:sfw';

function PeopleImportCompletionWatcher() {
  const queryClient = useQueryClient();
  const { toast } = useUi();
  const { t } = useTranslation();
  const scanStatusQuery = useScanStatusQuery();
  const prevScanStatusActive = useRef(false);
  const prevScanStatusPhase = useRef('');
  const prevPeopleAdultOnly = useRef(false);
  const prevLastCompleted = useRef(scanStatusQuery.data?.last_completed || 0);
  const completedImportHandledRef = useRef(false);

  useEffect(() => {
    const data = scanStatusQuery.data;
    if (!data) return;

    const didPeopleImportFinish =
      prevScanStatusActive.current &&
      prevScanStatusPhase.current === 'people_importing' &&
      !data.active;
    const didBackgroundPeopleImportFinish =
      prevLastCompleted.current !== 0 &&
      (data.last_completed || 0) > prevLastCompleted.current &&
      prevScanStatusPhase.current === 'people_importing';

    if (data.active && data.phase === 'people_importing') {
      completedImportHandledRef.current = false;
      prevPeopleAdultOnly.current = Boolean(data.people_adult_only);
    }

    if ((didPeopleImportFinish || didBackgroundPeopleImportFinish) && !completedImportHandledRef.current) {
      completedImportHandledRef.current = true;
      const adultOnly = prevPeopleAdultOnly.current;
      api.people.bulkImportReport('all', { adultOnly }).then((rep) => {
        if (rep && rep.status === 'completed' && rep.report) {
          const hasUnresolved = (rep.report.multiple_match_count > 0) || (rep.report.no_match_count > 0);
          if (hasUnresolved) {
            localStorage.setItem(getBulkImportBannerStorageKey(adultOnly), 'true');
          }
          window.dispatchEvent(new CustomEvent('people-bulk-import-complete', {
            detail: { hasUnresolved, adultOnly }
          }));
          queryClient.invalidateQueries({ queryKey: ['library'] });
          queryClient.invalidateQueries({ queryKey: ['stats'] });
          toast(t(adultOnly ? 'library.addPeople.adultBulkFinishedToast' : 'library.addPeople.bulkFinishedToast'), 'success');
        }
      }).catch(() => {
        // Ignore completion-report failures here.
      });
    }

    if (data.last_completed) {
      prevLastCompleted.current = data.last_completed;
    }
    prevScanStatusActive.current = data.active;
    prevScanStatusPhase.current = data.phase;
  }, [queryClient, scanStatusQuery.data, t, toast]);

  return null;
}

export default function AppShell() {
  const { data: settings } = useSettingsQuery();
  const theme = settings?.ui_theme || 'dark';
  const navigate = useNavigate();

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  useEffect(() => {
    if (settings && !settings.onboarding_completed) {
      navigate('/onboarding');
    }
  }, [settings, navigate]);

  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(() => {
    try {
      const saved = localStorage.getItem('sidebar_collapsed');
      return saved !== null ? JSON.parse(saved) : false;
    } catch {
      return false;
    }
  });

  const handleToggleSidebar = () => {
    setIsSidebarCollapsed((current) => {
      const next = !current;
      try {
        localStorage.setItem('sidebar_collapsed', JSON.stringify(next));
      } catch {
        // Ignore storage access errors.
      }
      return next;
    });
  };

  return (
    <div className={`shell ${isSidebarCollapsed ? 'is-sidebar-collapsed' : ''}`}>
      <PeopleImportCompletionWatcher />
      <button
        type="button"
        tabIndex={0}
        autoFocus
        className="shell__focus-sentinel"
        aria-hidden="true"
      />
      <WindowTitlebar />
      <Sidebar isCollapsed={isSidebarCollapsed} onToggle={handleToggleSidebar} />

      <div className="shell__main">
        <main className="shell__content">
          <header className="shell__utility-bar">
            <div className="shell__utility-bar-left" aria-label="Context actions placeholder" />
            <div className="shell__utility-bar-center" id="shell-utility-bar-center" />
          </header>
          <Suspense fallback={
            <div className="shell__suspense-fallback">
              <Spinner label="Loading page..." />
            </div>
          }>
            <Outlet />
          </Suspense>
          <footer className="shell__utility-bar-bottom">
            <div className="shell__utility-bar-bottom-left" aria-label="Context bottom-left actions placeholder" />
            <div className="shell__utility-bar-bottom-center" id="shell-utility-bar-bottom-center" />
            <div className="shell__utility-bar-bottom-right" aria-label="Context bottom-right actions placeholder" />
          </footer>
        </main>
      </div>
      <AppClosePrompt />
    </div>
  );
}
