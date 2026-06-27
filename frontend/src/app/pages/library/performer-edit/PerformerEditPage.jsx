import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { usePersonDetailQuery } from '@/queries/metadataQueries';
import { Link2, GitMerge, Sliders, X } from 'lucide-react';
import IconButton from '@/ui/IconButton';
import PerformerLinkingTab from './tabs/PerformerLinkingTab';
import PerformerMixerTab from './tabs/PerformerMixerTab';
import PerformerCustomValuesTab from './tabs/PerformerCustomValuesTab';
import { useTranslation } from '@/providers/LanguageContext';
import './PerformerEditPage.css';

export default function PerformerEditPage() {
  const { t } = useTranslation();
  const { id } = useParams();
  const navigate = useNavigate();
  const { data: person, isLoading, error } = usePersonDetailQuery(id);
  const [activeTab, setActiveTab] = useState('linking');
  const [isCustomDirty, setIsCustomDirty] = useState(false);
  const [isShaking, setIsShaking] = useState(false);

  const handleClose = useCallback(() => {
    if (isCustomDirty) {
      setIsShaking(true);
      setTimeout(() => setIsShaking(false), 500);
    } else {
      navigate(-1);
    }
  }, [navigate, isCustomDirty]);

  const handleTabClick = (tabId) => {
    if (isCustomDirty) {
      setIsShaking(true);
      setTimeout(() => setIsShaking(false), 500);
    } else {
      setActiveTab(tabId);
    }
  };

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        const target = e.target;
        if (target.tagName !== 'INPUT' && target.tagName !== 'TEXTAREA' && target.tagName !== 'SELECT') {
          handleClose();
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleClose]);

  if (isLoading) {
    return (
      <div className="settings-overlay settings-overlay--centered">
        <div className="settings-loading-state">
          <span className="settings-loading-text">{t('library.performerEdit.loadingPerformer') || 'Loading Performer...'}</span>
        </div>
      </div>
    );
  }

  if (error || !person) {
    return (
      <div className="settings-overlay settings-overlay--centered">
        <div className="settings-error-card">
          <div className="settings-error-content">
            <h3>{t('library.performerEdit.failedToLoadPerformer') || 'Failed to load performer'}</h3>
            <button className="btn btn--primary" onClick={handleClose}>{t('library.performerEdit.back') || 'Back'}</button>
          </div>
        </div>
      </div>
    );
  }

  const TABS = [
    { id: 'linking', label: t('library.performerEdit.linkedProfiles') || 'Linked Profiles', icon: Link2 },
    { id: 'mixer', label: t('library.performerEdit.dataMixer') || 'Data Mixer', icon: GitMerge },
    { id: 'custom', label: t('library.performerEdit.customValues') || 'Custom Values', icon: Sliders },
  ];

  return (
    <div className="settings-overlay">
      <aside className="settings-sidebar">
        <h1 className="settings-sidebar-header performer-edit-sidebar-header">
          {t('library.performerEdit.editPerformer') || 'Edit Performer'}
        </h1>
        <div className="performer-edit-sidebar-title-container">
          <h2 className="performer-edit-sidebar-name">{person.name}</h2>
        </div>
        <nav className="settings-sidebar-menu performer-edit-sidebar-menu">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            return (
              <div
                key={tab.id}
                className={`settings-sidebar-item${activeTab === tab.id ? ' active' : ''}`}
                role="button"
                tabIndex={0}
                onClick={() => handleTabClick(tab.id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    handleTabClick(tab.id);
                  }
                }}
              >
                <Icon size={18} />
                <span className="settings-sidebar-label">{tab.label}</span>
              </div>
            );
          })}
        </nav>
      </aside>

      <main className="settings-content-wrapper">
        <div className="settings-close-container">
          <IconButton
            className="settings-close-btn"
            onClick={handleClose}
            size="md"
          >
            <X size={18} />
          </IconButton>
          <span className="settings-close-esc-hint">{t('library.performerEdit.esc') || 'ESC'}</span>
        </div>

        <div className="settings-content performer-edit-content-wrapper--wide">
          {activeTab === 'linking' && (
            <div className="performer-edit-section">
              <h3 className="settings-section-title performer-edit-section-title">{t('library.performerEdit.linkedProfiles') || 'Linked Profiles'}</h3>
              <p className="settings-section-subtitle performer-edit-section-subtitle">{t('library.performerEdit.linkedProfilesSubtitle') || 'Manage connections to external performer registries to import attributes automatically.'}</p>
              <PerformerLinkingTab
                personId={person.id}
                defaultQuery={person.name}
                person={person}
                onClose={handleClose}
              />
            </div>
          )}

          {activeTab === 'mixer' && (
            <div className="performer-edit-section">
              <h3 className="settings-section-title performer-edit-section-title">{t('library.performerEdit.dataMixerGrid') || 'Data Mixer Grid'}</h3>
              <p className="settings-section-subtitle performer-edit-section-subtitle">{t('library.performerEdit.dataMixerGridSubtitle') || 'Select which provider source takes priority on a per-field basis.'}</p>
              <PerformerMixerTab
                person={person}
                onBack={handleClose}
              />
            </div>
          )}

          {activeTab === 'custom' && (
            <div className="performer-edit-section">
              <PerformerCustomValuesTab
                personId={person.id}
                person={person}
                onDirtyChange={setIsCustomDirty}
                isShaking={isShaking}
              />
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
