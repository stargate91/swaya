import { EXTRAS_FOLDER_MODES } from './settingsConstants.js';
import { generatePreview } from './settingsPreview.js';

const FOLDER_ICON = '\uD83D\uDCC1';
const FILE_ICON = '\uD83D\uDCC4';
const RENAME_ARROW = '\u2192';

const formatScenePreviewDate = (format) => String(format || '%Y-%m-%d')
  .replaceAll('%Y', '2024')
  .replaceAll('%m', '06')
  .replaceAll('%d', '14');

function createFolderNode(label, options = {}) {
  return {
    kind: 'folder',
    label,
    tone: options.tone || 'folder',
    topSpacing: Boolean(options.topSpacing),
    children: options.children || [],
  };
}

function getFolderLabel(path) {
  if (!path) return '';
  const cleanPath = path.replace(/\\/g, '/');
  const parts = cleanPath.split('/').filter(Boolean);
  if (parts.length > 0) {
    const lastPart = parts[parts.length - 1];
    if (/\.(mp4|mkv|avi|m4v|mov|wmv|mpg|mpeg|srt|sub|ass|vtt|ac3|dts|mp3|flac|wav|m4a|jpg|jpeg|png|gif|bmp|webp|nfo|xml|txt)$/i.test(lastPart)) {
      parts.pop();
    }
  }
  return parts[0] || '';
}

function createFileNode(label, options = {}) {
  return {
    kind: 'file',
    label,
    tone: options.tone || 'success',
    topSpacing: Boolean(options.topSpacing),
    strike: Boolean(options.strike),
  };
}

function getScenePreviewContext(form) {
  const squeezeStudios = Boolean(form.naming_squeeze_studio_names);
  const parentStudio = squeezeStudios ? 'VelvetMediaGroup' : 'Velvet Media Group';
  const studio = squeezeStudios ? 'VelvetStudios' : 'Velvet Studios';
  const separator = form.naming_performer_splitchar || ' & ';
  const blacklist = new Set(
    String(form.scene_tag_blacklist || '')
      .split(',')
      .map((tag) => tag.trim().toLocaleLowerCase())
      .filter(Boolean)
  );
  const tagLimit = Math.max(0, Number.parseInt(form.scene_tag_limit, 10) || 0);
  let tags = ['Audition', 'Brunette', 'Couples', 'Feature', 'HD', 'Roleplay']
    .filter((tag) => !blacklist.has(tag.toLocaleLowerCase()))
    .sort((left, right) => left.localeCompare(right));
  tags = tagLimit > 0 ? tags.slice(0, tagLimit) : [];
  return {
    date: formatScenePreviewDate(form.naming_scene_date_format),
    studio,
    parent_studio: parentStudio,
    studio_family: parentStudio,
    performers: ['Lana Rose', 'Alex Stone'].join(separator),
    performer: ['Lana Rose', 'Alex Stone'].join(separator),
    tags: tags.join(form.scene_tag_separator || ' '),
  };
}

function buildPreviewAssets(form) {
  const sceneContext = getScenePreviewContext(form);
  const movieFile = generatePreview(form.naming_movie_template, 'movie', form.naming_filename_casing, form.naming_word_separator, form.naming_custom_tag, true);
  const movieNameNoExt = movieFile.replace(/\.mp4$/, '');

  const helper = (template, type, defaultTmpl, defaultExt) => {
    let result = generatePreview(
      template || defaultTmpl,
      type,
      form.naming_filename_casing,
      form.naming_word_separator,
      form.naming_custom_tag,
      true
    );
    if (result) {
      return result.replace('The Matrix (1999)', movieNameNoExt);
    }
    return `${movieNameNoExt}${defaultExt}`;
  };

  return {
    movieFile,
    movieSubtitle: helper(form.extras_sub_template, 'extraSub', '{parent_name} {sub_category}', '.en.srt'),
    movieExtraVideo: helper(form.extras_video_template, 'extraVideo', '{parent_name} {sub_category}', '-trailer.mp4'),
    movieExtraAudio: helper(form.extras_audio_template, 'extraAudio', '{parent_name} {sub_category}', '.commentary.ac3'),
    movieExtraImg: helper(form.extras_img_template, 'extraImg', '{parent_name} {sub_category}', '-poster.jpg'),
    movieExtraMeta: helper(form.extras_meta_template, 'extraMeta', '{parent_name} {sub_category}', '.nfo'),
    adultMovieFile: generatePreview(form.naming_movie_template, 'adultMovie', form.naming_filename_casing, form.naming_word_separator, form.naming_custom_tag, true),
    adultFolderMovie: generatePreview(form.folder_movie_template, 'adultMovie', form.naming_filename_casing, form.naming_word_separator, form.naming_custom_tag, false),
    adultSceneFile: generatePreview(
      form.naming_scene_template || '{studio} - {performers} - {date} - {title} [{resolution}]',
      'scene',
      form.naming_filename_casing,
      form.naming_word_separator,
      form.naming_custom_tag,
      true,
      null,
      sceneContext
    ),
    adultSceneFolder: form.folder_scene_template
      ? generatePreview(
          form.folder_scene_template,
          'scene',
          form.naming_filename_casing,
          form.naming_word_separator,
          form.naming_custom_tag,
          false,
          null,
          sceneContext
        )
      : '',
    episodeFile: generatePreview(form.naming_episode_template, 'episode', form.naming_filename_casing, form.naming_word_separator, form.naming_custom_tag, true),
    folderMovie: generatePreview(form.folder_movie_template, 'movie', form.naming_filename_casing, form.naming_word_separator, form.naming_custom_tag, false),
    folderTv: generatePreview(form.folder_tv_template, 'tv', form.naming_filename_casing, form.naming_word_separator, form.naming_custom_tag, false),
    folderSeason: generatePreview(form.folder_season_template, 'season', form.naming_filename_casing, form.naming_word_separator, form.naming_custom_tag, false),
    folderEpisode: generatePreview(form.folder_episode_template, 'episode', form.naming_filename_casing, form.naming_word_separator, form.naming_custom_tag, false),
    folderCollection: generatePreview(form.folder_collection_template || '{Collection}', 'collection', form.naming_filename_casing, form.naming_word_separator, form.naming_custom_tag, true),
  };
}

function buildMovieExtraNodes(form, assets) {
  if (!form.extras_enabled) {
    return [];
  }

  const types = [
    { key: 'video', action: form.extras_video_action, assetKey: 'movieExtraVideo', origName: 'original_trailer.mp4' },
    { key: 'sub', action: form.extras_sub_action, assetKey: 'movieSubtitle', origName: 'original_subtitle.srt' },
    { key: 'audio', action: form.extras_audio_action, assetKey: 'movieExtraAudio', origName: 'original_audio.ac3' },
    { key: 'img', action: form.extras_img_action, assetKey: 'movieExtraImg', origName: 'original_poster.jpg' },
    { key: 'meta', action: form.extras_meta_action, assetKey: 'movieExtraMeta', origName: 'original_metadata.nfo' },
  ];

  const fileNodes = [];
  for (const t of types) {
    const action = t.action || 'rename';
    if (action === 'ignore') {
      fileNodes.push(createFileNode(t.origName, { tone: 'muted' }));
    } else if (action === 'delete') {
      fileNodes.push(createFileNode(assets[t.assetKey] || t.origName, { tone: 'danger', strike: true }));
    } else {
      fileNodes.push(createFileNode(assets[t.assetKey], { tone: 'muted' }));
    }
  }

  if (form.extras_folder_mode === EXTRAS_FOLDER_MODES.SUBFOLDER) {
    return [createFolderNode(form.extras_subfolder_name, { topSpacing: true, children: fileNodes })];
  }

  if (fileNodes.length > 0) {
    fileNodes[0].topSpacing = true;
  }
  return fileNodes;
}

function buildMovieNodes(form, assets) {
  let nodes;
  if (form.folder_create_movie_subdir) {
    nodes = [
      createFolderNode(getFolderLabel(assets.folderMovie), {
        children: [createFileNode(assets.movieFile), ...buildMovieExtraNodes(form, assets)],
      }),
    ];
  } else {
    nodes = [createFileNode(assets.movieFile), ...buildMovieExtraNodes(form, assets)];
  }

  if (form.folder_create_collection_dir) {
    return [createFolderNode(getFolderLabel(assets.folderCollection), { children: nodes })];
  }

  return nodes;
}

function buildAdultNodes(form, assets) {
  const movieNodes = form.folder_create_movie_subdir
    ? [createFolderNode(getFolderLabel(assets.adultFolderMovie), { tone: 'adult', children: [createFileNode(assets.adultMovieFile, { tone: 'adult' })] })]
    : [createFileNode(assets.adultMovieFile, { tone: 'adult' })];
  const tvNodes = [
    createFolderNode(getFolderLabel(assets.folderTv), {
      tone: 'adult',
      children: [createFileNode(assets.episodeFile, { tone: 'adult' })],
    }),
  ];
  let sceneNodes = [createFileNode(assets.adultSceneFile, { tone: 'adult' })];
  if (assets.adultSceneFolder) {
    sceneNodes = [createFolderNode(getFolderLabel(assets.adultSceneFolder), { tone: 'adult', children: sceneNodes })];
  }
  if (form.scene_grouping_mode === 'studio') {
    sceneNodes = [createFolderNode(getScenePreviewContext(form).studio, { tone: 'adult', children: sceneNodes })];
  } else if (form.scene_grouping_mode === 'parent_studio') {
    sceneNodes = [createFolderNode(getScenePreviewContext(form).parent_studio, { tone: 'adult', children: sceneNodes })];
  } else if (form.scene_grouping_mode === 'parent_studio_studio') {
    sceneNodes = [
      createFolderNode(getScenePreviewContext(form).parent_studio, {
        tone: 'adult',
        children: [createFolderNode(getScenePreviewContext(form).studio, { tone: 'adult', children: sceneNodes })],
      }),
    ];
  }

  if (!form.naming_adult_subfolders_enabled) {
    return [...movieNodes, ...tvNodes, ...sceneNodes];
  }

  return [
    createFolderNode(form.folder_adult_movies_name, { tone: 'adult', children: movieNodes }),
    createFolderNode(form.folder_adult_tv_name, { tone: 'adult', children: tvNodes }),
    createFolderNode(form.folder_adult_scenes_name, { tone: 'adult', children: sceneNodes }),
  ];
}

function buildEpisodeFileNode(assets) {
  return createFileNode(assets.episodeFile);
}

function buildShowNodes(form, assets, options = {}) {
  if (!form.folder_create_show_dir) {
    return [createFileNode(assets.episodeFile, { topSpacing: Boolean(options.topSpacing) })];
  }

  if (!form.folder_create_season_dir) {
    return [createFolderNode(getFolderLabel(assets.folderTv), { topSpacing: Boolean(options.topSpacing), children: [buildEpisodeFileNode(assets)] })];
  }

  const seasonChildren = form.folder_create_episode_dir
    ? [createFolderNode(getFolderLabel(assets.folderEpisode), { children: [buildEpisodeFileNode(assets)] })]
    : [buildEpisodeFileNode(assets)];

  return [
    createFolderNode(getFolderLabel(assets.folderTv), {
      topSpacing: Boolean(options.topSpacing),
      children: [createFolderNode(getFolderLabel(assets.folderSeason), { children: seasonChildren })],
    }),
  ];
}

function buildOrganizedNodes(form, assets) {
  if (form.folder_sort_by_type) {
    return [
      createFolderNode(form.folder_movies_name, { children: buildMovieNodes(form, assets) }),
      createFolderNode(form.folder_tv_name, { topSpacing: true, children: buildShowNodes(form, assets) }),
      ...(form.include_adult ? [createFolderNode(form.folder_adult_name, { tone: 'adult', topSpacing: true, children: buildAdultNodes(form, assets) })] : []),
    ];
  }

  return [
    ...buildMovieNodes(form, assets),
    ...buildShowNodes(form, assets, { topSpacing: true }),
    ...(form.include_adult ? buildAdultNodes(form, assets).map((node, index) => ({ ...node, topSpacing: index === 0 })) : []),
  ];
}

function buildUnorganizedNodes(form, assets) {
  const extraNodes = [];
  if (form.extras_enabled) {
    const types = [
      { action: form.extras_video_action, assetKey: 'movieExtraVideo', origName: 'original_trailer.mp4' },
      { action: form.extras_sub_action, assetKey: 'movieSubtitle', origName: 'original_subtitle.srt' },
      { action: form.extras_audio_action, assetKey: 'movieExtraAudio', origName: 'original_audio.ac3' },
      { action: form.extras_img_action, assetKey: 'movieExtraImg', origName: 'original_poster.jpg' },
      { action: form.extras_meta_action, assetKey: 'movieExtraMeta', origName: 'original_metadata.nfo' },
    ];
    for (const t of types) {
      const action = t.action || 'rename';
      const node = action === 'ignore'
        ? createFileNode(t.origName, { tone: 'muted' })
        : action === 'delete'
          ? createFileNode(assets[t.assetKey] || t.origName, { tone: 'danger', strike: true })
          : createFileNode(assets[t.assetKey], { tone: 'muted' });
      extraNodes.push(node);
    }
    if (extraNodes.length > 0) {
      extraNodes[0].topSpacing = true;
    }
  }

  return [
    createFileNode(assets.movieFile),
    ...extraNodes,
    createFileNode(assets.episodeFile),
    ...(form.include_adult ? [createFileNode(assets.adultMovieFile, { topSpacing: true })] : []),
  ];
}

function buildRenameItems(form, assets) {
  const items = [
    { before: 'original_movie_file.mp4', after: assets.movieFile, afterTone: 'success' },
    { before: 'original_episode_file.mp4', after: assets.episodeFile, afterTone: 'success' },
  ];

  if (form.extras_enabled) {
    const types = [
      { action: form.extras_video_action, assetKey: 'movieExtraVideo', origName: 'original_trailer.mp4' },
      { action: form.extras_sub_action, assetKey: 'movieSubtitle', origName: 'original_subtitle.srt' },
      { action: form.extras_audio_action, assetKey: 'movieExtraAudio', origName: 'original_audio.ac3' },
      { action: form.extras_img_action, assetKey: 'movieExtraImg', origName: 'original_poster.jpg' },
      { action: form.extras_meta_action, assetKey: 'movieExtraMeta', origName: 'original_metadata.nfo' },
    ];

    for (const t of types) {
      const action = t.action || 'rename';
      if (action === 'delete') {
        items.push({ before: t.origName, after: 'Deleted', afterTone: 'danger', strike: true });
      } else if (action === 'ignore') {
        items.push({ before: t.origName, after: t.origName, afterTone: 'muted' });
      } else {
        items.push({ before: t.origName, after: assets[t.assetKey] || t.origName, afterTone: 'muted' });
      }
    }
  }

  if (form.include_adult) {
    items.push({ before: 'original_adult_movie_file.mp4', after: assets.adultMovieFile, afterTone: 'adult' });
  }

  return items;
}

export function buildStructurePreviewModel(form, t) {
  const assets = buildPreviewAssets(form);

  if (!form.folder_move_to_library) {
    return {
      mode: 'rename',
      rootIcon: FOLDER_ICON,
      fileIcon: FILE_ICON,
      arrow: RENAME_ARROW,
      rootLabel: t('settingsPage.sections.organization.previewScanFolderPlaceholder'),
      items: buildRenameItems(form, assets),
    };
  }

  return {
    mode: 'tree',
    rootIcon: FOLDER_ICON,
    fileIcon: FILE_ICON,
    folderIcon: FOLDER_ICON,
    rootLabel: (form.folder_library_path || '').trim() || t('settingsPage.sections.organization.previewTargetFolderPlaceholder'),
    nodes: form.folder_organization_enabled
      ? buildOrganizedNodes(form, assets)
      : buildUnorganizedNodes(form, assets),
  };
}
