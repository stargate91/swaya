import PropTypes from 'prop-types';
import { useSettingsQuery } from '../../queries';
import { useTranslation } from '../../providers/LanguageContext';
import ContinueWatchingWidget from './widgets/ContinueWatchingWidget';
import LibraryInsightsWidget from './widgets/LibraryInsightsWidget';
import StatisticsWidget from './widgets/StatisticsWidget';
import RecommendationsWidget from './widgets/RecommendationsWidget';
import './DashboardPage.css';

const DashboardView = () => {
  const { data: settings = {} } = useSettingsQuery();
  const { t } = useTranslation();

  const displayName = settings.user_name?.trim();
  const welcomeTitle = displayName
    ? t('dashboard.welcome', { name: displayName })
    : t('dashboard.welcome_no_name') || 'Welcome back';

  return (
    <>
      <div className="dashboard-header">
        <h1 className="dashboard-header__title">{welcomeTitle}</h1>
        <p className="dashboard-header__subtitle">{t('dashboard.subtitle') || 'Here is an overview of your media library.'}</p>
      </div>

      <ContinueWatchingWidget T={t} />

      <RecommendationsWidget
        language={settings?.ui_language || settings?.primary_metadata_language}
        T={t}
      />

      <LibraryInsightsWidget T={t} />

      <StatisticsWidget T={t} />
    </>
  );
};

export default DashboardView;
