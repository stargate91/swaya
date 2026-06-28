import { useMemo } from 'react';
import PropTypes from 'prop-types';
import DashboardWidgetShell from './DashboardWidgetShell';
import { useStatsQuery } from '../../../queries';

const translateGenreLabel = (label, T) => {
  if (!label) return '';
  const genreKey = `library.genres.${label}`;
  const translated = T(genreKey);
  return (translated && translated !== genreKey) ? translated : label;
};

const isSingleGenreLabel = (label) => {
  const normalized = String(label || '').trim().toLowerCase();
  if (!normalized) return false;
  if (normalized.includes('&')) return false;
  if (normalized.includes('/')) return false;
  if (normalized.includes(',')) return false;
  if (/\b(and|és)\b/.test(normalized)) return false;
  return true;
};

const RADAR_GENRE_LIMIT = 6;
const MIN_DNA_TITLES = 4;
const MIN_TIMELINE_TITLES = 5;

const LibraryDNA = ({ constellation, genres, insightTitleCount, T }) => {
  const insightData = useMemo(() => {
    const sanitizeNodes = (nodes = []) => (
      nodes.filter((node) => isSingleGenreLabel(node?.label))
    );

    const fallbackNodes = !genres || Object.keys(genres).length === 0
      ? []
      : Object.entries(genres)
        .sort((a, b) => b[1] - a[1])
        .slice(0, RADAR_GENRE_LIMIT + 6)
        .map(([label, count], index) => ({ id: `fallback-${index}`, label, count }));

    const sourceNodes = sanitizeNodes(constellation?.nodes?.length ? constellation.nodes : fallbackNodes);
    if (!sourceNodes.length) return null;

    const sortedNodes = [...sourceNodes].sort((a, b) => (b.count || 0) - (a.count || 0));
    const nodes = sortedNodes.slice(0, RADAR_GENRE_LIMIT);
    const otherGenres = sortedNodes.slice(RADAR_GENRE_LIMIT).map((node) => ({
      ...node,
      translatedLabel: translateGenreLabel(node.label, T),
    }));
    const center = 150;
    const radius = 92;
    const levels = 4;
    const maxNodeCount = Math.max(...nodes.map((node) => Number(node.count || 0)), 1);
    const plottedNodes = nodes.map((node, index) => {
      const angle = (-Math.PI / 2) + ((Math.PI * 2) / nodes.length) * index;
      const valueRatio = Number(node.count || 0) / maxNodeCount;
      const pointRadius = radius * valueRatio;
      const axisX = center + Math.cos(angle) * radius;
      const axisY = center + Math.sin(angle) * radius;
      const pointX = center + Math.cos(angle) * pointRadius;
      const pointY = center + Math.sin(angle) * pointRadius;
      const labelRadius = radius + 34;
      const labelX = center + Math.cos(angle) * labelRadius;
      const labelY = center + Math.sin(angle) * labelRadius;

      return {
        ...node,
        translatedLabel: translateGenreLabel(node.label, T),
        angle,
        axisX,
        axisY,
        pointX,
        pointY,
        labelX,
        labelY,
        valueRatio,
      };
    });

    const polygonPoints = plottedNodes.map((node) => `${node.pointX},${node.pointY}`).join(' ');
    const rings = Array.from({ length: levels }, (_, index) => {
      const ringRadius = radius * ((index + 1) / levels);
      const points = plottedNodes.map((node) => {
        const x = center + Math.cos(node.angle) * ringRadius;
        const y = center + Math.sin(node.angle) * ringRadius;
        return `${x},${y}`;
      }).join(' ');
      return {
        key: `ring-${index + 1}`,
        points,
      };
    });

    return {
      nodes: plottedNodes,
      otherGenres,
      maxNodeCount,
      polygonPoints,
      rings,
    };
  }, [constellation, genres, T]);

  if (!insightData?.nodes?.length) return null;
  const hasEnoughData = insightTitleCount >= MIN_DNA_TITLES && insightData.nodes.length >= 3;
  const topGenres = insightData.nodes.slice(0, 3);

  return (
    <div className="insights-panel">
      <h3 className="insights-panel-title">
        <span className="insights-panel-dot is-pink" />
        {T('dashboard.stats.library_dna') || 'Library DNA'}
      </h3>
      {hasEnoughData ? (
        <div className="insights-dna-stage insights-dna-stage--radar">
          <div className="insights-radar-stage">
            <svg viewBox="0 0 300 300" className="insights-radar-svg" aria-hidden="true">
              {insightData.rings.map((ring) => (
                <polygon key={ring.key} points={ring.points} className="insights-radar-ring" />
              ))}
              {insightData.nodes.map((node) => (
                <line
                  key={`axis-${node.id}`}
                  x1="150"
                  y1="150"
                  x2={node.axisX}
                  y2={node.axisY}
                  className="insights-radar-axis"
                />
              ))}
              <polygon points={insightData.polygonPoints} className="insights-radar-shape" />
              {insightData.nodes.map((node) => (
                <circle
                  key={`point-${node.id}`}
                  cx={node.pointX}
                  cy={node.pointY}
                  r="4"
                  className="insights-radar-point"
                />
              ))}
              {insightData.nodes.map((node) => (
                <text
                  key={`label-${node.id}`}
                  x={node.labelX}
                  y={node.labelY}
                  textAnchor={node.labelX < 126 ? 'end' : (node.labelX > 174 ? 'start' : 'middle')}
                  className="insights-radar-label"
                >
                  {node.translatedLabel}
                </text>
              ))}
            </svg>
          </div>

          <div className="insights-radar-legend">
            {insightData.nodes.map((node) => (
              <div
                key={node.id}
                className="insights-radar-legend-row"
                title={T('dashboard.stats.items_count_tooltip', { label: node.translatedLabel, count: node.count }) || `${node.translatedLabel}: ${node.count}`}
              >
                <span className="insights-radar-legend-label">{node.translatedLabel}</span>
                <strong className="insights-radar-legend-count">{node.count}</strong>
              </div>
            ))}

            {insightData.otherGenres.length > 0 && (
              <div className="insights-radar-other">
                <span className="insights-radar-other__title">{T('dashboard.stats.other_genres') || 'Other Genres'}</span>
                <div className="insights-radar-other__list">
                  {insightData.otherGenres.map((node) => (
                    <span
                      key={`other-${node.id}`}
                      className="insights-radar-other__chip"
                      title={T('dashboard.stats.items_count_tooltip', { label: node.translatedLabel, count: node.count }) || `${node.translatedLabel}: ${node.count}`}
                    >
                      {node.translatedLabel} {node.count}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="insights-low-data">
          <p className="insights-low-data__copy">
            {T('dashboard.stats.library_dna_low_data', { count: insightTitleCount }) || `Need more matched files for library insights. Current count: ${insightTitleCount}`}
          </p>
          <div className="insights-low-data__chips">
            {topGenres.map((node) => (
              <div
                key={node.id}
                className="insights-low-data__chip"
                title={T('dashboard.stats.items_count_tooltip', { label: node.translatedLabel, count: node.count }) || `${node.translatedLabel}: ${node.count}`}
              >
                <span>{node.translatedLabel}</span>
                <strong>{node.count}</strong>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

LibraryDNA.propTypes = {
  constellation: PropTypes.object,
  genres: PropTypes.object,
  insightTitleCount: PropTypes.number.isRequired,
  T: PropTypes.func.isRequired,
};

const TimeTravelTimeline = ({ decades, insightTitleCount, T }) => {
  if (!decades || Object.keys(decades).length === 0) return null;
  const sorted = Object.entries(decades).sort((a, b) => a[0].localeCompare(b[0]));
  const maxCount = Math.max(...sorted.map(([, count]) => count));
  const topDecade = [...sorted].sort((a, b) => b[1] - a[1])[0][0];
  const formatDecade = (decade) => {
    const match = String(decade || '').match(/^(\d{4})s$/);
    return match ? T('dashboard.stats.decade_label', { decade: match[1] }) || `${match[1]}s` : decade;
  };
  const topDecadeLabel = formatDecade(topDecade);
  const hasEnoughData = insightTitleCount >= MIN_TIMELINE_TITLES && sorted.length >= 2;

  return (
    <div className="insights-panel">
      <h3 className="insights-panel-title">
        <span className="insights-panel-dot is-blue" />
        {T('dashboard.stats.timeline') || 'Time Travel'}
      </h3>
      <p className="insights-panel-subtitle">
        {T('dashboard.stats.top_decade', { decade: topDecadeLabel }) || `Most files are from the ${topDecadeLabel}`}
      </p>

      {hasEnoughData ? (
        <div className="insights-timeline">
          {sorted.map(([decade, count]) => {
            const heightPct = Math.max(5, (count / maxCount) * 100);
            const decadeLabel = formatDecade(decade);
            return (
              <div key={decade} className="insights-timeline-column">
                <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="insights-timeline-bar-shell">
                  <rect
                    x="0"
                    y={100 - heightPct}
                    width="100"
                    height={heightPct}
                    rx="6"
                    ry="6"
                    className="insights-timeline-bar"
                  >
                    <title>{T('dashboard.stats.items_count_tooltip', { label: decadeLabel, count }) || `${decadeLabel}: ${count} files`}</title>
                  </rect>
                </svg>
                <div className="insights-timeline-label">
                  {decadeLabel}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="insights-low-data insights-low-data--timeline">
          <p className="insights-low-data__copy">
            {T('dashboard.stats.timeline_low_data', { count: insightTitleCount }) || `Timeline will build automatically once more movies are scanned.`}
          </p>
          <div className="insights-low-data__highlight">
            <strong>{topDecadeLabel}</strong>
            <span>{T('dashboard.stats.items_count_tooltip', { label: topDecadeLabel, count: decades[topDecade] }) || `${topDecadeLabel}: ${decades[topDecade]} files`}</span>
          </div>
        </div>
      )}
    </div>
  );
};

TimeTravelTimeline.propTypes = {
  decades: PropTypes.object,
  insightTitleCount: PropTypes.number.isRequired,
  T: PropTypes.func.isRequired,
};

const LibraryInsightsWidget = ({ T }) => {
  const { data: stats = {}, isLoading } = useStatsQuery();
  const insightTitleCount = useMemo(
    () => Object.values(stats?.decade_distribution || {}).reduce((sum, value) => sum + Number(value || 0), 0),
    [stats?.decade_distribution]
  );
  const hasInsights = Boolean(
    (stats?.genre_constellation?.nodes?.length) ||
    (stats?.genre_distribution && Object.keys(stats.genre_distribution).length) ||
    (stats?.decade_distribution && Object.keys(stats.decade_distribution).length)
  );

  if (!isLoading && !hasInsights) {
    return null;
  }

  return (
    <DashboardWidgetShell loading={isLoading} size="lg">
      <div className="insights-layout">
        <LibraryDNA
          constellation={stats?.genre_constellation}
          genres={stats?.genre_distribution}
          insightTitleCount={insightTitleCount}
          T={T}
        />
        <TimeTravelTimeline
          decades={stats?.decade_distribution}
          insightTitleCount={insightTitleCount}
          T={T}
        />
      </div>
    </DashboardWidgetShell>
  );
};

LibraryInsightsWidget.propTypes = {
  T: PropTypes.func.isRequired,
};

export default LibraryInsightsWidget;
