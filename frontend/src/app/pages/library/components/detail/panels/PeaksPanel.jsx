import { Trash2, Flame } from 'lucide-react';
import { formatTime } from '../../../utils/detailUtils';
import { useMediaDetailContext } from '../MediaDetailContext';
import Pill from '@/ui/Pill';
import './PeaksPanel.css';

const LPAR = '(';
const RPAR = ')';
const DASH_CHAR = '—';

export default function PeaksPanel() {
  const { state, mutations, t } = useMediaDetailContext();
  const { item } = state;
  const { deletePeakMutation } = mutations;

  const formatLogDate = (dateStr) => {
    if (!dateStr) return '';
    try {
      return new Date(dateStr).toLocaleString();
    } catch {
      return dateStr;
    }
  };

  const handleDeletelog = (logId) => {
    if (deletePeakMutation.isPending) return;
    deletePeakMutation.mutate({ itemId: item.id, logId });
  };

  const peaks = item?.peaks_history || [];

  return (
    <div className="peaks-panel">
      <div className="peaks-panel__header-row">
        <h4 className="peaks-panel__title">
          {t('library.details.peaksTitle') || 'Peak Moments'} {LPAR}{peaks.length}{RPAR}
        </h4>
      </div>

      <div className="peaks-panel__list-container">
        {peaks.length > 0 ? (
          <div className="peaks-table">
            <div className="peaks-table__header">
              <div className="peaks-table__col-header">{t('library.details.peakDate') || 'Date'}</div>
              <div className="peaks-table__col-header">{t('library.details.peakPosition') || 'Position'}</div>
              <div className="peaks-table__col-header peaks-table__col-header--actions"></div>
            </div>
            <div className="peaks-table__body">
              {peaks.map((log, index) => (
                <div key={log.id || index} className="peaks-table__row">
                  <div className="peaks-table__cell peaks-table__cell--date">
                    {formatLogDate(log.watched_at)}
                  </div>
                  <div className="peaks-table__cell peaks-table__cell--position">
                    {log.video_position != null ? (
                      <Pill variant="neutral" className="peak-position-pill">
                        <Flame size={12} className="peak-position-pill__icon" />
                        {formatTime(log.video_position)}
                      </Pill>
                    ) : (
                      <span className="peaks-table__empty-cell">{DASH_CHAR}</span>
                    )}
                  </div>
                  <div className="peaks-table__cell peaks-table__cell--actions">
                    <button
                      type="button"
                      className="peak-delete-btn"
                      onClick={() => handleDeletelog(log.id)}
                      disabled={deletePeakMutation.isPending}
                      title={t('library.details.deletePeakBtn') || 'Delete Peak'}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="peaks-panel__empty">
            {t('library.details.noPeaks') || 'No peak moments recorded yet.'}
          </div>
        )}
      </div>
    </div>
  );
}
