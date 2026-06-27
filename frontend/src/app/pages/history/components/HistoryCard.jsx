import { useState } from 'react';
import { RotateCcw, Calendar, CheckCircle2, Clock, AlertTriangle, ChevronDown, ChevronUp, ArrowRight } from 'lucide-react';
import Button from '@/ui/Button';
import Tooltip from '@/ui/Tooltip';
import Spinner from '@/ui/Spinner';
import { useTranslation } from '@/providers/LanguageContext';

const getCardIconAndClass = (status) => {
  switch (status) {
    case 'completed':
      return {
        icon: <CheckCircle2 size={18} />,
        accentColor: 'var(--color-state-success, #10b981)',
      };
    case 'partial':
      return {
        icon: <AlertTriangle size={18} />,
        accentColor: 'var(--color-state-warning, #f59e0b)',
      };
    case 'undone':
      return {
        icon: <RotateCcw size={18} />,
        accentColor: 'var(--color-text-muted, #94a3b8)',
      };
    default:
      return {
        icon: <Clock size={18} />,
        accentColor: 'var(--color-accent, #1493ff)',
      };
  }
};

export default function HistoryCard({
  batch,
  index,
  isAnyTaskActive,
  isUndoing,
  isReverting,
  onConfirmUndo,
}) {
  const { t } = useTranslation();
  const [isExpanded, setIsExpanded] = useState(false);
  const isUndone = batch.status === 'undone';
  const isRevertDisabled = isUndone || isAnyTaskActive || isReverting;
  const { icon, accentColor } = getCardIconAndClass(batch.status);
  const hasLogs = batch.logs && batch.logs.length > 0;

  return (
    <div
      className={`history-card history-card--${batch.status} ${isExpanded ? 'is-expanded' : ''}`}
      ref={(el) => {
        if (el) {
          el.style.setProperty('--item-index', index);
          el.style.setProperty('--accent-color', accentColor);
        }
      }}
    >
      <div className="history-card__main-row">
        <div className="history-card__icon-wrapper">
          {icon}
        </div>
        <div className="history-card__left">
          <div className="history-card__header">
            {batch.success_count > 0 && (
              <div className="history-card__detailed-stats">
                {batch.movie_count > 0 && (
                  <div className="history-card__stat-badge">
                    <span className="history-card__badge-val">{batch.movie_count}</span>
                    <span className="history-card__badge-lbl">{t('historyPage.badgeMovies') || 'Movies'}</span>
                  </div>
                )}
                {batch.episode_count > 0 && (
                  <div className="history-card__stat-badge">
                    <span className="history-card__badge-val">{batch.episode_count}</span>
                    <span className="history-card__badge-lbl">{t('historyPage.badgeEpisodes') || 'Episodes'}</span>
                  </div>
                )}
                {batch.extra_count > 0 && (
                  <div className="history-card__stat-badge">
                    <span className="history-card__badge-val">{batch.extra_count}</span>
                    <span className="history-card__badge-lbl">{t('historyPage.badgeExtras') || 'Extras'}</span>
                  </div>
                )}
                <div className="history-card__stat-badge history-card__stat-badge--total">
                  <span className="history-card__badge-val">{batch.success_count}</span>
                  <span className="history-card__badge-lbl">{t('historyPage.statTotal') || 'Total'}</span>
                </div>
                {batch.undone_count > 0 && batch.remaining_count > 0 && (
                  <>
                    <div className="history-card__stat-badge history-card__stat-badge--undone">
                      <span className="history-card__badge-val">{batch.undone_count}</span>
                      <span className="history-card__badge-lbl">{t('historyPage.statReverted') || 'Reverted'}</span>
                    </div>
                    <div className="history-card__stat-badge history-card__stat-badge--remaining">
                      <span className="history-card__badge-val">{batch.remaining_count}</span>
                      <span className="history-card__badge-lbl">{t('historyPage.statRemaining') || 'Remaining'}</span>
                    </div>
                  </>
                )}
              </div>
            )}
            {batch.failed_count > 0 && (
              <div className="history-card__stat-badge history-card__stat-badge--failed">
                <span className="history-card__badge-val">{batch.failed_count}</span>
                <span className="history-card__badge-lbl">{t('historyPage.statFailed') || 'Failed'}</span>
              </div>
            )}
          </div>
          <div className="history-card__meta">
            <div className="history-card__meta-item">
              <Calendar size={14} />
              <span>{new Date(batch.created_at).toLocaleString()}</span>
            </div>
            <div className="history-card__meta-item">
              <Clock size={14} />
              <span>{t('historyPage.batchIdLabel', { defaultValue: 'ID: #{{id}}', id: batch.id })}</span>
            </div>
          </div>
        </div>
        <div className="history-card__right">
          <div className="history-card__actions">
            {hasLogs && (
              <Button
                variant="ghost"
                size="sm"
                className="history-card__toggle-btn"
                onClick={() => setIsExpanded(!isExpanded)}
              >
                {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                <span>
                  {isExpanded ? t('common.hideDetails') || 'Hide Details' : t('common.showDetails') || 'Show Details'}
                </span>
              </Button>
            )}
            <Tooltip
              content={
                isUndone
                  ? (t('historyPage.alreadyRevertedTooltip') || 'This batch has already been reverted.')
                  : null
              }
              side="left"
            >
              <Button
                variant="secondary"
                size="sm"
                disabled={isRevertDisabled}
                onClick={() => onConfirmUndo(batch)}
                icon={(isUndoing && isAnyTaskActive && !isUndone) || isReverting ? <Spinner size={14} /> : <RotateCcw size={14} />}
              >
                {t('historyPage.revertButton') || 'Revert'}
              </Button>
            </Tooltip>
          </div>
        </div>
      </div>

      {isExpanded && hasLogs && (
        <div className="history-card__details">
          <div className="history-card__files-title">
            {t('historyPage.renamedFilesTitle') || 'Renamed Files:'}
          </div>
          <div className="history-card__files-list">
            {batch.logs.map((log) => {
              const oldFile = log.old_value ? log.old_value.split(/[\\/]/).pop() : '';
              const newFile = log.new_value ? log.new_value.split(/[\\/]/).pop() : '';
              const oldDir = log.old_value ? log.old_value.substring(0, log.old_value.length - oldFile.length) : '';
              const newDir = log.new_value ? log.new_value.substring(0, log.new_value.length - newFile.length) : '';
              return (
                <div key={log.id} className={`history-card__file-item history-card__file-item--${log.status}`}>
                  <div className="history-card__file-paths">
                    <div className="history-card__file-path-group">
                      <span className="history-card__file-dir">{oldDir}</span>
                      <span className="history-card__file-name">{oldFile}</span>
                    </div>
                    <ArrowRight size={14} className="history-card__file-arrow" />
                    <div className="history-card__file-path-group">
                      <span className="history-card__file-dir">{newDir}</span>
                      <span className="history-card__file-name history-card__file-name--new">{newFile}</span>
                    </div>
                  </div>
                  {log.error_message && (
                    <div className="history-card__file-error">{log.error_message}</div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
