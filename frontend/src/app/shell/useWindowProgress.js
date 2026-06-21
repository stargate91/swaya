import { useEffect, useState } from 'react';
import { useTranslation } from '../providers/LanguageContext';
import { useImageStatusQuery, useScanStatusQuery, useHydrateStatusQuery } from '../queries';
import {
  getScanProgress,
  formatScanRemaining,
  getScanTaskName,
  getImageProgress,
  formatImageRemaining,
} from './windowProgressUtils';

export default function useWindowProgress() {
  const { t } = useTranslation();
  const [now, setNow] = useState(() => Date.now());
  const scanStatusQuery = useScanStatusQuery();
  const imageStatusQuery = useImageStatusQuery();
  const hydrateStatusQuery = useHydrateStatusQuery();
  
  const scanStatus = scanStatusQuery.data || null;
  const imageStatus = imageStatusQuery.data || null;
  const hydrateStatus = hydrateStatusQuery.data || null;
  
  const isPrimaryActive = Boolean(scanStatus?.active);
  const isImageActive = Boolean(imageStatus?.active) && !isPrimaryActive;
  const isHydrateActive = Boolean(hydrateStatus?.active);

  useEffect(() => {
    if (!isPrimaryActive) return undefined;

    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [isPrimaryActive]);

  const isMainActive = isPrimaryActive && (
    scanStatus?.phase === 'collecting' ||
    scanStatus?.phase === 'resolving' ||
    scanStatus?.phase === 'enriching' ||
    scanStatus?.phase === 'organizing' ||
    scanStatus?.phase === 'undoing' ||
    scanStatus?.phase === 'sync_language'
  );
  
  const isPeopleImportActive = isPrimaryActive && scanStatus?.phase === 'people_importing';
  const isPeopleEnricherActive = isPeopleImportActive || isHydrateActive;

  const rawProgress = isPrimaryActive ? getScanProgress(scanStatus) : 0;

  const scanProgressData = isPrimaryActive && isMainActive
    ? scanStatus.phase === 'sync_language'
      ? {
          taskName: t('progress.sync.running') || 'Syncing metadata languages...',
          progress: Math.round(scanStatus.progress || 0),
          timeRemaining: `${scanStatus.processed_files || 0}/${scanStatus.total_files || 0}`,
          active: true,
          variant: 'primary',
        }
      : {
          taskName: getScanTaskName(scanStatus, t),
          progress: rawProgress,
          timeRemaining: formatScanRemaining(scanStatus, rawProgress, now),
          active: true,
          variant: 'primary',
        }
    : null;

  return {
    hasProgress: isMainActive || isPeopleEnricherActive || isImageActive,
    scanProgress: scanProgressData,
    imageProgress: isImageActive
      ? {
          taskName: t('progress.images.downloading'),
          progress: getImageProgress(imageStatus),
          timeRemaining: formatImageRemaining(imageStatus),
          active: true,
          variant: 'sub',
        }
      : null,
    hydrateProgress: isPeopleImportActive
      ? {
          taskName: t('progress.people.importing') || 'Importing bulk people...',
          progress: scanStatus.total > 0 ? Math.round((scanStatus.current / scanStatus.total) * 100) : 0,
          timeRemaining: `${scanStatus.current || 0}/${scanStatus.total || 0}`,
          active: true,
          variant: 'sub',
        }
      : isHydrateActive
      ? {
          taskName: t('progress.people.hydrating') || 'Enriching extra people...',
          progress: hydrateStatus.total > 0 ? Math.round((hydrateStatus.current / hydrateStatus.total) * 100) : 0,
          timeRemaining: `${hydrateStatus.current || 0}/${hydrateStatus.total || 0}`,
          active: true,
          variant: 'sub',
        }
      : null,
    syncProgress: null,
  };
}
