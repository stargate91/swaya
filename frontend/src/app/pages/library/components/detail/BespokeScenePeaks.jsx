import { Flame, X } from 'lucide-react';
import { useMediaDetailContext } from './MediaDetailContext';
import { formatTime } from '../../utils/detailUtils';
import './BespokeScenePeaks.css';

const LPAR = '(';
const RPAR = ')';

export default function BespokeScenePeaks() {
  const { state, mutations, t } = useMediaDetailContext();
  const { item, cleanId, effectiveId } = state;
  const { deletePeakMutation, playMutation } = mutations;

  const peaks = item?.peaks_history || [];

  const handleDeletePeak = (e, logId) => {
    e.stopPropagation();
    if (deletePeakMutation.isPending) return;
    deletePeakMutation.mutate({ itemId: effectiveId, logId, tvId: cleanId });
  };

  const handlePlayMedia = () => {
    if (playMutation.isPending) return;
    playMutation.mutate(item.id);
  };

  return (
    <div className="bespoke-scene-peaks-card">
      <div className="bespoke-scene-peaks-header">
        <div className="bespoke-scene-peaks-header-left">
          <Flame size={12} className="bespoke-scene-peaks-title-icon" />
          <span className="bespoke-scene-peaks-title">
            {t('library.details.peaksTitle') || 'Peak Moments'} {LPAR}{peaks.length}{RPAR}
          </span>
        </div>
      </div>

      <div className="bespoke-scene-peaks-body">
        {peaks.length > 0 ? (
          <div className="bespoke-scene-peaks-list">
            {peaks.map((log, index) => {
              const hasPosition = log.video_position != null && log.video_position > 0;
              return (
                <div
                  key={log.id || index}
                  className={`bespoke-scene-peaks-item ${hasPosition ? 'bespoke-scene-peaks-item--playable' : ''}`}
                  onClick={hasPosition ? handlePlayMedia : undefined}
                  title={hasPosition ? "Play Video" : undefined}
                >
                  <div className="bespoke-scene-peaks-item-left">
                    <Flame size={11} className="bespoke-scene-peaks-item-icon" />
                    <span className="bespoke-scene-peaks-item-time">
                      {hasPosition ? formatTime(log.video_position) : (t('library.details.playSession') || 'Play Session')}
                    </span>
                  </div>

                  <div className="bespoke-scene-peaks-item-right">
                    <span className="bespoke-scene-peaks-item-date">
                      {new Date(log.watched_at).toLocaleDateString()}
                    </span>
                    <button
                      type="button"
                      className="bespoke-scene-peaks-item-delete"
                      onClick={(e) => handleDeletePeak(e, log.id)}
                      disabled={deletePeakMutation.isPending}
                      title={t('library.details.deletePeakBtn') || 'Delete Peak'}
                    >
                      <X size={12} />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <span className="bespoke-scene-peaks-empty-text">
            {t('library.details.noPeaks') || 'No peak moments recorded yet.'}
          </span>
        )}
      </div>
    </div>
  );
}
