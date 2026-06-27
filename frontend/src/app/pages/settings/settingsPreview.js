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
    title: "Riley Reid Experience",
    original_title: "Riley Reid Experience",
    year: '2016',
    release_date: '2016-04-10',
    resolution: '1080p',
    edition: 'Extended Cut',
    collection: '',
    source: 'WEB-DL',
    video_codec: 'h264',
    audio_codec: 'AAC',
    audio_channels: '2.0',
    imdb_id: 'tt0000000',
    tmdb_id: '0',
    rating_imdb: '7.8',
  },
  scene: {
    studio: 'Brazzers Network',
    performers: 'Abella Danger & Jordi El Nino Polla',
    performer: 'Abella Danger & Jordi El Nino Polla',
    rating_porndb: '9.2',
    date: '2018-09-15',
    title: 'Private Tutoring',
    resolution: '1080p',
    source: 'WEB-DL',
    video_codec: 'h264',
  },
  tv: {
    tv_title: 'Game of Thrones',
    tv_original_title: 'Game of Thrones',
    year: '2011',
    first_air_year: '2011',
    first_air_date: '2011-04-17',
    last_air_year: '2019',
    last_air_date: '2019-05-19',
    year_range: '2011-2019',
    tv_tmdb_id: '1399',
  },
  adultTv: {
    tv_title: "Adriana's World",
    tv_original_title: "Adriana's World",
    year: '2017',
    first_air_year: '2017',
    first_air_date: '2017-06-15',
    last_air_year: '2020',
    last_air_date: '2020-08-20',
    year_range: '2017-2020',
    tv_tmdb_id: '99999',
  },
  season: {
    season: '01',
    season_name: 'Season 1',
    tv_title: 'Game of Thrones',
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
    tv_title: 'Game of Thrones',
    tv_original_title: 'Game of Thrones',
    season: '01',
    episode: '03',
    episode_title: 'Lord Snow',
    resolution: '1080p',
    video_codec: 'h264',
    audio_codec: 'EAC3',
    audio_channels: '5.1',
    tv_tmdb_id: '1399',
    first_air_year: '2011',
  },
  adultEpisode: {
    tv_title: "Adriana's World",
    tv_original_title: "Adriana's World",
    season: '01',
    episode: '03',
    episode_title: "Sweet Temptations",
    resolution: '1080p',
    video_codec: 'h264',
    audio_codec: 'EAC3',
    audio_channels: '5.1',
    tv_tmdb_id: '99999',
    first_air_year: '2017',
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
const isCollectionPreviewType = (type) => type === 'collection';

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
      finalResult = `${result}/Riley Reid Experience (2016) 1080p.mp4`;
    } else if (type === 'tv') {
      finalResult = `${result}/Season 01/Game of Thrones - S01E03 - Lord Snow.mp4`;
    } else if (type === 'adultTv') {
      finalResult = `${result}/Season 01/Adriana's World - S01E03 - Sweet Temptations.mp4`;
    } else if (type === 'season' || type === 'episode') {
      finalResult = `${result}/Game of Thrones - S01E03 - Lord Snow.mp4`;
    } else if (type === 'adultEpisode') {
      finalResult = `${result}/Adriana's World - S01E03 - Sweet Temptations.mp4`;
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

