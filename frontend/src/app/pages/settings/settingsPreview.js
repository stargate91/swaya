const PREVIEW_CONTEXTS = {
  movie: {
    title: 'The Matrix',
    original_title: 'The Matrix',
    year: '1999',
    release_date: '1999-03-31',
    resolution: '1080p',
    edition: 'Ultimate Edition',
    collection: 'The Matrix Collection',
    source: 'BluRay',
    video_codec: 'h264',
    audio_codec: 'DTS-HD',
    audio_channels: '5.1',
    imdb_id: 'tt0133093',
    tmdb_id: '603',
    rating_imdb: '8.7',
  },
  adultMovie: {
    title: 'Velvet Nights XXX',
    original_title: 'Velvet Nights XXX',
    year: '2018',
    release_date: '2018-06-14',
    resolution: '1080p',
    edition: 'Extended Cut',
    collection: '',
    source: 'WEB-DL',
    video_codec: 'h264',
    audio_codec: 'AAC',
    audio_channels: '2.0',
    imdb_id: 'tt0000000',
    tmdb_id: '0',
    rating_imdb: '6.4',
  },
  scene: {
    studio: 'Velvet Studios',
    performers: 'Lana Rose & Alex Stone',
    performer: 'Lana Rose & Alex Stone',
    rating_porndb: '8.4',
    date: '2024-06-14',
    title: 'Late Night Audition',
    resolution: '1080p',
    source: 'WEB-DL',
    video_codec: 'h264',
  },
  tv: {
    tv_title: 'Stranger Things',
    tv_original_title: 'Stranger Things',
    year: '2016',
    first_air_year: '2016',
    first_air_date: '2016-07-15',
    last_air_year: '2022',
    last_air_date: '2022-07-01',
    year_range: '2016-2022',
    tv_tmdb_id: '66732',
  },
  season: {
    season: '01',
    season_name: 'Season 1',
    tv_title: 'Stranger Things',
  },
  collection: {
    collection: 'The Matrix Collection',
  },
  extraVideo: {
    parent_name: 'The Matrix (1999)',
    sub_category: 'trailer',
  },
  extraSub: {
    parent_name: 'The Matrix (1999)',
    language: 'en',
    sub_category: 'forced',
  },
  extraAudio: {
    parent_name: 'The Matrix (1999)',
    language: 'en',
    sub_category: 'commentary',
  },
  extraImg: {
    parent_name: 'The Matrix (1999)',
    sub_category: 'poster',
  },
  extraMeta: {
    parent_name: 'The Matrix (1999)',
  },
  episode: {
    tv_title: 'Stranger Things',
    tv_original_title: 'Stranger Things',
    season: '01',
    episode: '03',
    episode_title: 'Holly, Jolly',
    resolution: '1080p',
    video_codec: 'h264',
    audio_codec: 'EAC3',
    audio_channels: '5.1',
    tv_tmdb_id: '66732',
    first_air_year: '2016',
  },
};

const PREVIEW_EXTENSIONS = {
  extraAudio: '.ac3',
  extraImg: '.jpg',
  extraMeta: '.nfo',
  extraSub: '.srt',
  extraVideo: '.mp4',
};

const isMoviePreviewType = (type) => type === 'movie' || type === 'adultMovie';
const isTvPreviewType = (type) => type === 'tv';
const isCollectionPreviewType = (type) => type === 'collection';
const isSeasonLikePreviewType = (type) => type === 'season' || type === 'episode';

export function generatePreview(template, type, casing, separator, customTag, isFile = true, sortOptions = null, contextOverrides = null) {
  if (!template) return '';

  const previewType = PREVIEW_CONTEXTS[type] ? type : 'episode';
  const context = {
    ...PREVIEW_CONTEXTS[previewType],
    ...(contextOverrides || {}),
    custom: customTag || 'custom',
  };
  const ext = isFile ? (PREVIEW_EXTENSIONS[previewType] || '.mp4') : '';

  let result = template.replace(/\{(\w+)\}/g, (match, p1) => {
    const key = p1.toLowerCase().replace(/_/g, '');
    const foundKey = Object.keys(context).find((k) => k.toLowerCase().replace(/_/g, '') === key);
    return foundKey ? context[foundKey] : '';
  });

  result = result.replace(/\(\s*\)/g, '');
  result = result.replace(/\[\s*\]/g, '');
  result = result.replace(/\s*-\s*-\s*/g, ' - ');
  result = result.replace(/\s{2,}/g, ' ');
  result = result.replace(/\s*-\s*$/g, '');
  result = result.replace(/^\s*-\s*/g, '');
  result = result.replace(/[\\/:*?"<>|]/g, '').trim();

  if (casing === 'lower') {
    result = result.toLowerCase();
  } else if (casing === 'upper') {
    result = result.toUpperCase();
  } else if (casing === 'title') {
    result = result.replace(/\b[a-z]/gi, (char) => char.toUpperCase());
  }

  const sepMap = {
    space: ' ',
    dot: '.',
    dash: '-',
    underscore: '_'
  };
  const sep = sepMap[separator] || ' ';
  if (sep !== ' ') {
    result = result.replace(/\(/g, '').replace(/\)/g, '').replace(/\[/g, '').replace(/\]/g, '');
    result = result.replace(/\s-\s/g, ' ');
    result = result.replace(/\s+/g, ' ');
    result = result.replace(/\s/g, sep);
  }

  let finalResult = result;
  if (!isFile && result) {
    if (type === 'movie') {
      finalResult = `${result}/The Matrix (1999) 1080p.mp4`;
    } else if (type === 'adultMovie') {
      finalResult = `${result}/Velvet Nights XXX (2018) 1080p.mp4`;
    } else if (isTvPreviewType(type)) {
      finalResult = `${result}/Season 01/Stranger Things - S01E03 - Holly, Jolly.mp4`;
    } else if (isSeasonLikePreviewType(type)) {
      finalResult = `${result}/Stranger Things - S01E03 - Holly, Jolly.mp4`;
    }
  } else if (isCollectionPreviewType(type)) {
    finalResult = result ? `${result}/The Matrix (1999).mp4` : '';
  } else {
    finalResult = result ? `${result}${ext}` : '';
  }

  if (sortOptions && sortOptions.enabled && (!isFile || isCollectionPreviewType(type)) && finalResult) {
    const rootName = (isMoviePreviewType(type) || isCollectionPreviewType(type))
      ? (sortOptions.moviesName || 'Movies')
      : (sortOptions.tvName || 'TV Shows');
    finalResult = `${rootName}/${finalResult}`;
  }

  return finalResult;
}

