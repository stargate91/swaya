import { ArrowRight } from 'lucide-react';
import Checkbox from '../../ui/Checkbox';
import Pill from '../../ui/Pill';
import Tooltip from '../../ui/Tooltip';
import { isEpisodeMediaType, isMovieMediaType, isMovieOrEpisodeMediaType, isSceneMediaType } from '@/lib/mediaTypes';
import { mapCollisionStrategyLabel, shouldShowCollisionStrategy } from './organizerMappers';

const renderSelectColumn = (paginatedRows, selectedRowIds, handleToggleAll, handleToggleRow) => ({
  key: 'select',
  label: (
    /* eslint-disable-next-line jsx-a11y/no-static-element-interactions */
    <div onClick={(event) => event.stopPropagation()}>
      <Checkbox
        checked={paginatedRows.length > 0 && paginatedRows.every((row) => selectedRowIds.has(row.id))}
        onChange={handleToggleAll}
      />
    </div>
  ),
  width: '48px',
  align: 'center',
  render: (value, row) => (
    /* eslint-disable-next-line jsx-a11y/no-static-element-interactions */
    <div onClick={(event) => event.stopPropagation()}>
      <Checkbox
        checked={selectedRowIds.has(row.id)}
        onChange={() => handleToggleRow(row.id)}
      />
    </div>
  ),
});

const renderProposedFilename = (value, row, activeMainTab, onOpenMatch, onOpenOverride, t) => {
  const isManualReview = activeMainTab === 'manual';

  const content = (() => {
    if (row.rawType === 'extra') {
      const unmatchedParentStatuses = ['new', 'uncertain', 'no_match', 'multiple', 'error'];
      if (row.parentStatus && unmatchedParentStatuses.includes(row.parentStatus.toLowerCase())) {
        return <span className="organizer-target-note organizer-target-note--warning">{t('organizer.table.targetNotes.fixParentFirst')}</span>;
      }
      if (row.rawAction === 'skip') {
        return <span className="organizer-target-note organizer-target-note--muted">{t('organizer.table.targetNotes.skip')}</span>;
      }
      if (row.rawAction === 'delete') {
        return <span className="organizer-target-note organizer-target-note--danger">{t('organizer.table.targetNotes.delete')}</span>;
      }
    }
    return (
      <span className="organizer-target-proposed">
        {value}
      </span>
    );
  })();

  if (isManualReview && row.rawType !== 'extra') {
    const isEpisode = isEpisodeMediaType(row.rawType);
    const isMissingSeason = isEpisode && (row.season === null || row.season === undefined || row.season === '');
    const isMissingEpisode = isEpisode && (row.episode === null || row.episode === undefined || row.episode === '');

    if (isEpisode && (isMissingSeason || isMissingEpisode)) {
      const label = (() => {
        if (isMissingSeason && isMissingEpisode) {
          return t('organizer.actions.fixSeasonAndEpisode') || 'Fix S & E';
        }
        if (isMissingSeason) {
          return t('organizer.actions.fixSeason') || 'Fix S';
        }
        return t('organizer.actions.fixEpisode') || 'Fix E';
      })();

      return (
        <div className="organizer-target-cell">
          <button
            type="button"
            className="organizer-target-action organizer-target-action--warning"
            onClick={(e) => {
              e.stopPropagation();
              onOpenOverride(row);
            }}
          >
            {label}
          </button>
        </div>
      );
    }

    return (
      <div className="organizer-target-cell">
        <button
          type="button"
          className="organizer-target-action"
          onClick={(e) => {
            e.stopPropagation();
            onOpenMatch(row);
          }}
        >
          {t('organizer.actions.fixMatch')}
        </button>
      </div>
    );
  }

  return content;
};

const renderStatusCell = (value, row, collisionStrategy, normalizeStatusTone, t) => (
  <span className="organizer-status-cell">
    <Pill variant={normalizeStatusTone(value, t)}>{value}</Pill>
    {isMovieOrEpisodeMediaType(row.rawType) && shouldShowCollisionStrategy(row) ? (
      <Pill className="organizer-status-cell__policy" variant="default">
        {mapCollisionStrategyLabel(row.rawAction || collisionStrategy, t)}
      </Pill>
    ) : null}
    {row.rawStatus === 'uncertain' && !isMovieMediaType(row.rawType) && !isSceneMediaType(row.rawType) && (row.season === null || row.season === undefined || row.season === '') ? (
      <Tooltip content={t('organizer.status.missingSeasonTooltip')} side="top">
        <Pill className="organizer-status-cell__policy" variant="default">
          {t('organizer.status.missingSeason')}
        </Pill>
      </Tooltip>
    ) : null}
    {row.rawStatus === 'uncertain' && !isMovieMediaType(row.rawType) && !isSceneMediaType(row.rawType) && (row.episode === null || row.episode === undefined || row.episode === '') ? (
      <Tooltip content={t('organizer.status.missingEpisodeTooltip')} side="top">
        <Pill className="organizer-status-cell__policy" variant="default">
          {t('organizer.status.missingEpisode')}
        </Pill>
      </Tooltip>
    ) : null}
  </span>
);

export function buildOrganizerColumns({
  activeExtrasTab,
  activeMainTab,
  collisionStrategy,
  handleToggleAll,
  handleToggleRow,
  normalizeStatusTone,
  paginatedRows,
  renderSortableLabel,
  selectedRowIds,
  t,
  onOpenMatch,
  onOpenOverride,
}) {
  const columns = [
    renderSelectColumn(paginatedRows, selectedRowIds, handleToggleAll, handleToggleRow),
    { key: 'source', label: renderSortableLabel(t('organizer.table.originalFilename'), 'source') },
    {
      key: 'arrow',
      label: '',
      width: '32px',
      align: 'center',
      render: (value, row) => {
        const isManualReview = activeMainTab === 'manual';
        if (isManualReview && row.rawType !== 'extra') {
          return <></>;
        }
        if (row.rawType === 'extra') {
          const unmatchedParentStatuses = ['new', 'uncertain', 'no_match', 'multiple', 'error'];
          if (row.parentStatus && unmatchedParentStatuses.includes(row.parentStatus.toLowerCase())) {
            return <></>;
          }
          if (row.rawAction === 'skip' || row.rawAction === 'delete') {
            return <></>;
          }
        }
        return <ArrowRight size={14} className="organizer-target-arrow" />;
      },
    },
    {
      key: 'target',
      label: activeMainTab === 'manual'
        ? t('organizer.table.proposedFilename')
        : renderSortableLabel(t('organizer.table.proposedFilename'), 'target'),
      render: (value, row) => renderProposedFilename(value, row, activeMainTab, onOpenMatch, onOpenOverride, t),
    },
  ];

  if (activeMainTab === 'extras') {
    if (activeExtrasTab === 'bonus' || activeExtrasTab === 'images') {
      columns.push({ key: 'category', label: renderSortableLabel(t('organizer.table.subcategory'), 'category'), align: 'center', width: '15%' });
    } else if (activeExtrasTab === 'subtitles' || activeExtrasTab === 'audio') {
      columns.push({ key: 'category', label: renderSortableLabel(t('organizer.table.subcategory'), 'category'), align: 'center', width: '15%' });
      columns.push({
        key: 'language',
        label: renderSortableLabel(t('organizer.table.language'), 'language'),
        align: 'center',
        width: '10%',
        render: (value) => (value ? String(value).substring(0, 2).toUpperCase() : ''),
      });
    } else if (activeExtrasTab === 'metadata') {
      columns.push({ key: 'extension', label: renderSortableLabel(t('organizer.table.extension'), 'extension'), align: 'center', width: '12%' });
    }
  } else {
    columns.push({
      key: 'status',
      label: activeMainTab === 'manual' ? renderSortableLabel(t('organizer.table.status'), 'status') : t('organizer.table.status'),
      align: 'center',
      width: '20%',
      render: (value, row) => renderStatusCell(value, row, collisionStrategy, normalizeStatusTone, t),
    });
  }

  const targetCol = columns.find(c => c.key === 'target');
  if (activeMainTab === 'manual' && targetCol) {
    targetCol.width = '15%';
  }

  // Calculate sum of specific widths (excluding select, source)
  let specificPercent = 0;
  columns.forEach((col) => {
    if (col.key !== 'source' && col.width && col.width.endsWith('%')) {
      specificPercent += parseFloat(col.width);
    }
  });

  const remainingPercent = 100 - specificPercent;
  const sourceCol = columns.find(c => c.key === 'source');
  if (sourceCol) {
    if (activeMainTab === 'manual') {
      sourceCol.width = `${remainingPercent.toFixed(2)}%`;
    } else {
      const halfWidth = `${(remainingPercent / 2).toFixed(2)}%`;
      sourceCol.width = halfWidth;
      if (targetCol) targetCol.width = halfWidth;
    }
  }

  return columns;
}
