import { resolveMediaImageUrl } from '@/lib/imageUrls';

export const SOURCE_LABELS = {
  bluray: 'Blu-Ray',
  web: 'WEB-DL',
  dvd: 'DVD',
  tv: 'TV HDTV',
  cam: 'CAM'
};

export const EDITION_LABELS = {
  theatrical: 'Theatrical Edition',
  directors_cut: "Director's Cut",
  extended: 'Extended Edition',
  unrated: 'Unrated',
  remastered: 'Remastered',
  special: 'Special Edition',
  ultimate: 'Ultimate',
  collectors_edition: "Collector's Edition",
  fan_edit: 'Fan Edit'
};

export const AUDIO_TYPE_LABELS = {
  mono: 'Mono',
  stereo: 'Stereo',
  surround: 'Surround Sound',
  dual_audio: 'Dual Audio',
  multi_audio: 'Multi Audio'
};

export const getDurationText = (seconds, t) => {
  if (!seconds) return '';
  const totalMinutes = Math.round(seconds / 60);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;

  if (hours > 0) {
    if (minutes > 0) {
      return t('library.details.durationHoursMinutes', { hours, minutes, defaultValue: '{{hours}}h {{minutes}}m' });
    }
    return t('library.details.durationHours', { hours, count: hours, defaultValue: '{{hours}}h' });
  }
  return t('library.details.durationMinutes', { minutes, count: minutes, defaultValue: '{{minutes}}m' });
};

export const formatEpisodeNumber = (epNum) => {
  if (epNum === undefined || epNum === null) return '';
  const str = String(epNum).trim();

  if (str.includes(',')) {
    const parts = str.split(',').map(s => s.trim()).filter(Boolean);
    if (parts.length > 1) {
      return `${parts[0]}-${parts[parts.length - 1]}`;
    }
  }

  if (str.includes('-')) {
    const parts = str.split('-').map(s => s.trim()).filter(Boolean);
    return parts.length > 0 ? parts.join('-') : '';
  }

  return str;
};

export const formatTime = (secs) => {
  if (secs === undefined || secs === null) return '';
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = Math.round(secs % 60);
  return [h > 0 ? h : null, m, s]
    .filter(x => x !== null)
    .map(x => String(x).padStart(2, '0'))
    .join(':');
};

export const countEpisodesInNumber = (epNum) => {
  if (epNum === undefined || epNum === null) return 1;
  const str = String(epNum).trim();
  if (!str) return 1;

  if (str.includes(',')) {
    const parts = str.split(',').map(s => s.trim()).filter(Boolean);
    return parts.length > 0 ? parts.length : 1;
  }

  if (str.includes('-')) {
    const parts = str.split('-').map(s => s.trim()).filter(Boolean);
    if (parts.length === 2) {
      const start = parseInt(parts[0], 10);
      const end = parseInt(parts[1], 10);
      if (!isNaN(start) && !isNaN(end) && end >= start) {
        return end - start + 1;
      }
    }
  }

  return 1;
};

export const resolveDetailsImageUrl = (path, API_BASE, imageType = 'backdrop') => {
  return resolveMediaImageUrl(path, imageType, API_BASE);
};
