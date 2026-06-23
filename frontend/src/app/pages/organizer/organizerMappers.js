export const PAGE_SIZE_OPTIONS = [20, 40, 60, 120];
export const MANUAL_REVIEW_STATUSES = new Set(['error', 'new', 'no_match', 'uncertain', 'multiple']);
export const MATCHED_STATUSES = new Set(['matched']);

export const EXTRA_CATEGORY_BY_TAB = {
  bonus: 'video',
  subtitles: 'subtitle',
  audio: 'audio',
  images: 'image',
  metadata: 'metadata',
};

const prettifyToken = (value) => String(value || '')
  .replace(/[_-]+/g, ' ')
  .replace(/\b\w/g, (char) => char.toUpperCase());

export const mapOrganizerTypeLabel = (type, t) => {
  const value = String(type || '').toLowerCase();
  if (value === 'episode') return t('organizer.typeLabels.episode');
  if (value === 'movie') return t('organizer.typeLabels.movie');
  if (value === 'tv') return t('organizer.typeLabels.tv');
  if (value === 'scene') return t('organizer.typeLabels.scene');
  if (value === 'extra') return t('organizer.typeLabels.extra');
  return prettifyToken(value) || t('organizer.typeLabels.media');
};

export const normalizeStatusTone = (value, t) => {
  if (value === t('organizer.status.ready')) return 'success';
  if (value === t('organizer.status.collision') || value === t('organizer.status.error')) return 'danger';
  if (value === t('organizer.status.pending') || value === t('organizer.status.uncertain') || value === t('organizer.status.multiple') || value === t('organizer.status.noMatch')) return 'warning';
  return 'default';
};

export const mapCollisionStrategyLabel = (value, t) => {
  const strategy = String(value || '').toLowerCase();
  if (strategy === 'skip') return t('organizer.collisionStrategy.skip');
  if (strategy === 'replace_if_better') return t('organizer.collisionStrategy.replaceIfBetter');
  if (strategy === 'replace') return t('organizer.collisionStrategy.replace');
  return t('organizer.collisionStrategy.keepBoth');
};

export const shouldShowCollisionStrategy = (row) => {
  const action = String(row?.rawAction || '').toLowerCase();
  return Boolean(row?.hasCollision) || action === 'skip' || action === 'replace' || action === 'replace_if_better';
};

const mapItemStatus = (status, hasCollision, t) => {
  if (hasCollision) {
    return t('organizer.status.collision');
  }

  const value = String(status || '').toLowerCase();
  if (value === 'matched' || value === 'renamed' || value === 'organized') return t('organizer.status.ready');
  if (value === 'no_match') return t('organizer.status.noMatch');
  if (value === 'uncertain') return t('organizer.status.uncertain');
  if (value === 'multiple') return t('organizer.status.multiple');
  if (value === 'error') return t('organizer.status.error');
  if (value === 'new') return t('organizer.status.pending');
  return prettifyToken(value) || t('organizer.status.pending');
};

const mapItemType = (type, t) => mapOrganizerTypeLabel(type, t);

export const normalizeItemStatus = (status) => String(status || '').toLowerCase();
export const getFilenameFromPath = (value) => String(value || '').split(/[/\\]/).pop() || '-';

export const compareOrganizerValues = (left, right) => {
  const a = String(left ?? '').trim().toLowerCase();
  const b = String(right ?? '').trim().toLowerCase();
  return a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' });
};

export const mapOrganizerItemRow = (item, t) => ({
  id: `item-${item.id}`,
  itemId: item.id,
  source: getFilenameFromPath(item.filename),
  target: getFilenameFromPath(item.planned_path),
  sourcePath: item.current_path || item.filename,
  targetPath: item.planned_path || '-',
  type: mapItemType(item.type, t),
  status: mapItemStatus(item.status, item.has_collision, t),
  hasCollision: Boolean(item.has_collision),
  rawAction: String(item.action || '').toLowerCase(),
  rawType: String(item.type || '').toLowerCase(),
  rawStatus: String(item.status || '').toLowerCase(),
  category: '-',
  language: item.target_language ? prettifyToken(item.target_language) : '-',
  extension: String(item.extension || '').replace(/^\./, ''),
  season: item.season !== undefined ? item.season : null,
  episode: item.episode !== undefined ? item.episode : null,
  customEdition: item.custom_edition !== undefined ? item.custom_edition : 'none',
  customAudioType: item.custom_audio_type !== undefined ? item.custom_audio_type : 'none',
  customSource: item.custom_source !== undefined ? item.custom_source : 'none',
  images: item.images || [],
  rawPayload: item,
});

export const mapExtraRow = (item, t) => ({
  id: `extra-${item.id}`,
  itemId: item.id,
  source: getFilenameFromPath(item.filename),
  target: getFilenameFromPath(item.planned_path),
  sourcePath: item.path || item.filename,
  targetPath: item.planned_path || '-',
  type: t('organizer.typeLabels.extra'),
  status: item.action === 'delete' ? t('organizer.status.delete') : t('organizer.status.ready'),
  rawAction: String(item.action || '').toLowerCase(),
  rawType: 'extra',
  rawStatus: String(item.action === 'delete' ? 'delete' : 'matched'),
  category: item.subtype && item.subtype !== 'other' ? prettifyToken(item.subtype) : '-',
  language: item.language ? String(item.language).toUpperCase() : '-',
  extension: String(item.extension || '').replace(/^\./, ''),
  parentStatus: item.parent_status || null,
  parentType: String(item.parent_type || '').toLowerCase(),
  parent_id: item.parent_id || item.parent_item_id,
  parent_is_adult: item.parent_is_adult,
  images: [],
  rawPayload: item,
});
