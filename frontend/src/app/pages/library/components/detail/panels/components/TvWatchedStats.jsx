import { ChevronDown, ChevronRight } from 'lucide-react';
import { formatTime, countEpisodesInNumber, formatEpisodeNumber } from '../../../../utils/detailUtils';
import { useMediaDetailContext } from '../../MediaDetailContext';
import '../PanelsCommon.css';
import './WatchedStats.css';
import Pill from '@/ui/Pill';


export default function TvWatchedStats() {
  const { state, actions, t } = useMediaDetailContext();
  const { item, isWatchLogsExpanded } = state;
  const { setIsWatchLogsExpanded } = actions;

  const formatLogDate = (dateStr) => {
    if (!dateStr) return '';
    try {
      return new Date(dateStr).toLocaleString();
    } catch {
      return dateStr;
    }
  };

  const regularSeasons = (item.seasons || []).filter(s => s.season_number > 0);
  const allEpisodes = regularSeasons.flatMap(s => s.episodes || []);
  const watchStats = item.watch_stats;

  const totalEpisodesCount = watchStats
    ? watchStats.total_episodes_count
    : allEpisodes.reduce((sum, ep) => sum + countEpisodesInNumber(ep.episode_number), 0);

  const watchedEpisodesCount = watchStats
    ? watchStats.watched_episodes_count
    : allEpisodes.reduce((sum, ep) => sum + (ep.is_watched ? countEpisodesInNumber(ep.episode_number) : 0), 0);

  const completionPercentage = totalEpisodesCount > 0
    ? Math.round((watchedEpisodesCount / totalEpisodesCount) * 100)
    : 0;

  const inProgressEpisodes = watchStats
    ? watchStats.in_progress_episodes
    : allEpisodes.filter(e => e.resume_position > 0);

  const isInProgress = inProgressEpisodes.length > 0;

  const allPlaybackLogs = watchStats
    ? watchStats.playback_logs
    : (() => {
        const logs = [];
        regularSeasons.forEach(season => {
          (season.episodes || []).forEach(episode => {
            if (episode.playback_logs && episode.playback_logs.length > 0) {
              episode.playback_logs.forEach(log => {
                logs.push({
                  ...log,
                  seasonNumber: season.season_number,
                  episodeNumber: episode.episode_number,
                  episodeTitle: episode.title,
                  episodeId: episode.id
                });
              });
            }
          });
        });
        logs.sort((a, b) => new Date(b.watched_at) - new Date(a.watched_at));
        return logs;
      })();

  const tvLastWatched = allPlaybackLogs.length > 0 ? allPlaybackLogs[0].watched_at : null;

  const tvStatus = watchedEpisodesCount === totalEpisodesCount && totalEpisodesCount > 0
    ? (t('library.details.statusWatched') || 'Watched')
    : (isInProgress || watchedEpisodesCount > 0
      ? (t('library.details.statusInProgress') || 'In Progress')
      : (t('library.details.statusUnwatched') || 'Unwatched'));

  const episodesCompletedText = `${watchedEpisodesCount} / ${totalEpisodesCount}`;
  const completionRateText = `${completionPercentage}%`;
  const watchActivityTitleText = `${t('library.details.watchActivity') || 'Watch Activity'} (${allPlaybackLogs.length})`;

  return (
    <div className="watched-panel">
      <div>
        <h4 className="details-panel__ratings-title">
          {t('library.details.watchStats') || 'Watch Stats'}
        </h4>
        <div className="specs-grid">
          <div className="specs-card">
            <span className="specs-card__label">{t('library.details.episodesCompleted') || 'Completed'}</span>
            <span className="specs-card__value" title={episodesCompletedText}>
              {episodesCompletedText}
            </span>
          </div>
          <div className="specs-card">
            <span className="specs-card__label">{t('library.details.completionRate') || 'Completion'}</span>
            <span className="specs-card__value" title={completionRateText}>
              {completionRateText}
            </span>
          </div>
          <div className="specs-card specs-card--span-2">
            <span className="specs-card__label">{t('library.details.watchStatus') || 'Status'}</span>
            <span className={`specs-card__value status-${watchedEpisodesCount === totalEpisodesCount && totalEpisodesCount > 0 ? 'watched' : (isInProgress || watchedEpisodesCount > 0 ? 'progress' : 'unwatched')}`} title={tvStatus}>
              {tvStatus}
            </span>
          </div>
          <div className="specs-card specs-card--span-2">
            <span className="specs-card__label">{t('library.details.lastWatched') || 'Last Watched'}</span>
            <span className="specs-card__value" title={tvLastWatched ? formatLogDate(tvLastWatched) : 'Never'}>
              {tvLastWatched ? formatLogDate(tvLastWatched) : (t('library.details.never') || 'Never')}
            </span>
          </div>
          {isInProgress && (
            <div className="specs-card specs-card--span-2">
              <span className="specs-card__label">{t('library.details.inProgressEpisodes') || 'Episodes in Progress'}</span>
              <span className="specs-card__value specs-card__value--in-progress">
                {inProgressEpisodes.map((ep, idx) => {
                  const epNumStr = ep.episode_number
                    ? (ep.episode_number.toString().includes('.') ? ep.episode_number : String(ep.episode_number).padStart(2, '0'))
                    : '';
                  const seasonPrefix = ep.season_number !== undefined
                    ? `S${String(ep.season_number).padStart(2, '0')}E${epNumStr}`
                    : `S${epNumStr}`;
                  const epProgressText = `${seasonPrefix} • ${ep.title} (${formatTime(ep.resume_position)})`;
                  return (
                    <div key={ep.id || idx}>
                      {epProgressText}
                    </div>
                  );
                })}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Season Progress List */}
      <div>
        <h4 className="details-panel__ratings-title">
          {t('library.details.seasonProgress') || 'Season Progress'}
        </h4>
        <div className="watched-panel__seasons-list">
          {regularSeasons.map(season => {
            const sEp = season.episodes || [];
            const totalEp = sEp.length;
            const watchedEp = sEp.filter(e => e.is_watched).length;
            const seasonProgPercent = totalEp > 0 ? Math.round((watchedEp / totalEp) * 100) : 0;
            const seasonTitleText = season.title || `Season ${season.season_number}`;
            const seasonMetaText = `${watchedEp} / ${totalEp} (${seasonProgPercent}%)`;

            return (
              <div
                key={season.season_number}
                className="season-progress-card"
              >
                <div className="season-progress-card__header">
                  <span className="season-progress-card__title">
                    {seasonTitleText}
                  </span>
                  <span className="season-progress-card__meta">
                    {seasonMetaText}
                  </span>
                </div>
                <progress
                  className="season-progress-card__progress"
                  value={seasonProgPercent}
                  max={100}
                />
              </div>
            );
          })}
        </div>
      </div>

      {/* Collapsible Watch Activity */}
      <div>
        {/* eslint-disable-next-line jsx-a11y/no-static-element-interactions */}
        <div
          className="activity-header watched-panel__activity-header"
          onClick={() => setIsWatchLogsExpanded(prev => !prev)}
        >
          <h4 className="watched-panel__activity-title">
            {watchActivityTitleText}
          </h4>
          {isWatchLogsExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        </div>

        {isWatchLogsExpanded && (
          <div className="activity-list">
            {allPlaybackLogs.length > 0 ? (
              allPlaybackLogs.map((log, index) => {
                const logCodeText = `S${log.seasonNumber}E${formatEpisodeNumber(log.episodeNumber)}`;
                return (
                  <div
                    key={log.id || index}
                    className="activity-item activity-item--tv"
                  >
                    <div className="activity-item__tv-top">
                      <Pill variant="meta" className="activity-item__token">
                        {logCodeText}
                      </Pill>
                      <span className="activity-item__title" title={log.episodeTitle}>
                        {log.episodeTitle}
                      </span>
                    </div>
                    <span className="activity-item__date">
                      {formatLogDate(log.watched_at)}
                    </span>
                  </div>
                );
              })
            ) : (
              <div className="activity-list__empty">
                {t('library.details.noActivity') || 'No recorded watch logs.'}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
