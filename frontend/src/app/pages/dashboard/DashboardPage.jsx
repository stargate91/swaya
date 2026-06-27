import { useSettingsQuery } from '@/queries/settingsQueries';
import Page from '@/ui/Page';
import DashboardView from './DashboardView';
import './DashboardPage.css';

export default function DashboardPage() {
  const { isLoading: isSettingsLoading } = useSettingsQuery();

  if (isSettingsLoading) {
    return (
      <Page className="dashboard-page" contentBottom>
        <div className="dashboard-loading">
          <div className="dashboard-spinner" />
        </div>
      </Page>
    );
  }

  return (
    <Page className="dashboard-page" contentBottom>
      <div className="dashboard-container">
        <DashboardView />
      </div>
    </Page>
  );
}
