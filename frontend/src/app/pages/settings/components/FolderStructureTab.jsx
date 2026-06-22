import Card from '@/ui/Card';
import Stack from '@/ui/Stack';
import Switch from '@/ui/Switch';
import Input from '@/ui/Input';
import { FOLDER_MOVIE_TAGS, FOLDER_SHOW_TAGS, FOLDER_SEASON_TAGS, FOLDER_EPISODE_TAGS } from '../settingsTemplateTags.js';
import { useTemplatePreview } from '../hooks';
import SettingsLiveImpact from './SettingsLiveImpact.jsx';
import TemplateFieldSection from './TemplateFieldSection.jsx';
import { useSettingsFormContext } from '../SettingsFormContext.jsx';

export default function FolderStructureTab({
  form,
  t,
  handleChange,
  handleCheckboxChange,
  insertTag,
  formInputs
}) {
  const getPreview = useTemplatePreview(form);
  const { renderContext } = useSettingsFormContext();
  const isScanActive = Boolean(renderContext?.isBackgroundActive);
  const sortOptions = {
    enabled: form.folder_sort_by_type,
    moviesName: form.folder_movies_name,
    tvName: form.folder_tv_name
  };

  return (
    <Stack gap="xl">
      <Card
        title={t('settingsPage.sections.folderStructure.behaviorTitle')}
        eyebrow={t('settingsPage.sections.folderStructure.behaviorEyebrow')}
      >
        <Stack gap="lg">
          <Switch
            id="folder_organization_enabled"
            checked={form.folder_organization_enabled}
            disabled={isScanActive}
            onChange={handleCheckboxChange('folder_organization_enabled')}
          >
            {t('settingsPage.sections.folderStructure.orgEnabled')}
          </Switch>
          <span className="ui-field__hint settings-hint--tight-top">
            {t('settingsPage.sections.folderStructure.orgEnabledHint')}
          </span>

          {form.folder_organization_enabled && (
            <>
              <div className="settings-section-stack">
                <h3 className="settings-section-heading">
                  {t('settingsPage.sections.folderStructure.destinationTitle')}
                </h3>
              </div>
              <Switch
                id="folder_move_to_library"
                checked={form.folder_move_to_library}
                disabled={isScanActive}
                onChange={handleCheckboxChange('folder_move_to_library')}
              >
                {t('settingsPage.sections.folderStructure.moveToLibrary')}
              </Switch>
              <span className="ui-field__hint settings-hint--tight-top">
                {t('settingsPage.sections.folderStructure.moveToLibraryHint')}
              </span>

              <div className="settings-section-stack">
                <h3 className="settings-section-heading">
                  {t('settingsPage.sections.folderStructure.rootFoldersTitle')}
                </h3>
              </div>
              <Switch
                id="folder_sort_by_type"
                checked={form.folder_sort_by_type}
                disabled={isScanActive}
                onChange={handleCheckboxChange('folder_sort_by_type')}
              >
                {t('settingsPage.sections.folderStructure.sortByType')}
              </Switch>
              <span className="ui-field__hint settings-hint--tight-top">
                {t('settingsPage.sections.folderStructure.sortByTypeHint')}
              </span>

              {form.folder_sort_by_type && (
                <div className="settings-nested-block">
                  <Stack gap="md">
                    <Input
                      label={t('settingsPage.sections.folderStructure.moviesDirName')}
                      value={form.folder_movies_name}
                      disabled={isScanActive}
                      onChange={handleChange('folder_movies_name')}
                      placeholder={t('settingsPage.sections.folderStructure.defaultMoviesName')}
                    />
                    <Input
                      label={t('settingsPage.sections.folderStructure.tvDirName')}
                      value={form.folder_tv_name}
                      disabled={isScanActive}
                      onChange={handleChange('folder_tv_name')}
                      placeholder={t('settingsPage.sections.folderStructure.defaultTvName')}
                    />

                  </Stack>
                </div>
              )}

              {form.include_adult && (
                <div className="settings-section-stack">
                  <h3 className="settings-section-heading">
                    {t('settingsPage.sections.folderStructure.adultFoldersTitle')}
                  </h3>
                  <Stack gap="md">
                    <Input
                      label={t('settingsPage.sections.folderStructure.adultDirName')}
                      value={form.folder_adult_name}
                      disabled={isScanActive}
                      onChange={handleChange('folder_adult_name')}
                      placeholder={t('settingsPage.sections.folderStructure.defaultAdultName')}
                    />
                    <Switch
                      id="naming_adult_subfolders_enabled"
                      checked={form.naming_adult_subfolders_enabled}
                      disabled={isScanActive}
                      onChange={handleCheckboxChange('naming_adult_subfolders_enabled')}
                    >
                      {t('settingsPage.sections.folderStructure.organizeAdultByType')}
                    </Switch>
                    <span className="ui-field__hint settings-hint--tight-top">
                      {t('settingsPage.sections.folderStructure.organizeAdultByTypeHint')}
                    </span>
                    {form.naming_adult_subfolders_enabled && (
                      <div className="settings-nested-block">
                        <Stack gap="md">
                          <Input
                            label={t('settingsPage.sections.folderStructure.adultMoviesDirName')}
                            value={form.folder_adult_movies_name}
                            disabled={isScanActive}
                            onChange={handleChange('folder_adult_movies_name')}
                            placeholder={t('settingsPage.sections.folderStructure.defaultAdultMoviesName')}
                          />
                          <Input
                            label={t('settingsPage.sections.folderStructure.adultTvDirName')}
                            value={form.folder_adult_tv_name}
                            disabled={isScanActive}
                            onChange={handleChange('folder_adult_tv_name')}
                            placeholder={t('settingsPage.sections.folderStructure.defaultAdultTvName')}
                          />
                          <Input
                            label={t('settingsPage.sections.folderStructure.adultScenesDirName')}
                            value={form.folder_adult_scenes_name}
                            disabled={isScanActive}
                            onChange={handleChange('folder_adult_scenes_name')}
                            placeholder={t('settingsPage.sections.folderStructure.defaultAdultScenesName')}
                          />

                        </Stack>
                      </div>
                    )}
                  </Stack>
                </div>
              )}

              <Switch
                id="folder_remove_empty"
                checked={form.folder_remove_empty}
                disabled={isScanActive}
                onChange={handleCheckboxChange('folder_remove_empty')}
              >
                {t('settingsPage.sections.folderStructure.removeEmpty')}
              </Switch>
              <span className="ui-field__hint settings-hint--tight-top">
                {t('settingsPage.sections.folderStructure.removeEmptyHint')}
              </span>
            </>
          )}
        </Stack>
      </Card>

      {form.folder_organization_enabled && (
        <Card
          title={t('settingsPage.sections.folderStructure.structureTitle')}
          eyebrow={t('settingsPage.sections.folderStructure.structureEyebrow')}
        >
          <Stack gap="xl">
            <div className="settings-section-stack">
              <h3 className="settings-section-heading">
                {t('settingsPage.sections.folderStructure.movieShowFoldersTitle')}
              </h3>
              <Stack gap="xl">
                <div>
                  <Switch
                    id="folder_create_movie_subdir"
                    checked={form.folder_create_movie_subdir}
                    disabled={isScanActive}
                    onChange={handleCheckboxChange('folder_create_movie_subdir')}
                  >
                    {t('settingsPage.sections.folderStructure.createMovieSubdir')}
                  </Switch>
                  <span className="ui-field__hint settings-hint--block-compact">
                    {t('settingsPage.sections.folderStructure.createMovieSubdirHint')}
                  </span>

                  {form.folder_create_movie_subdir && (
                    <TemplateFieldSection
                      t={t}
                      inputRef={formInputs.folderMovie}
                      label={t('settingsPage.sections.folderStructure.movieTemplate')}
                      value={form.folder_movie_template}
                      disabled={isScanActive}
                      onChange={handleChange('folder_movie_template')}
                      placeholder="{title} ({year})"
                      tags={FOLDER_MOVIE_TAGS}
                      fieldKey="folder_movie_template"
                      insertTag={insertTag}
                      previewText={getPreview(form.folder_movie_template, 'movie', { isFile: false, sortOptions })}
                      className="settings-nested-block settings-nested-block--top"
                    />
                  )}
                </div>

                <div>
                  <Switch
                    id="folder_create_show_dir"
                    checked={form.folder_create_show_dir}
                    disabled={isScanActive}
                    onChange={handleCheckboxChange('folder_create_show_dir')}
                  >
                    {t('settingsPage.sections.folderStructure.createShowDir')}
                  </Switch>
                  <span className="ui-field__hint settings-hint--block-compact">
                    {t('settingsPage.sections.folderStructure.createShowDirHint')}
                  </span>

                  {form.folder_create_show_dir && (
                    <TemplateFieldSection
                      t={t}
                      inputRef={formInputs.folderTv}
                      label={t('settingsPage.sections.folderStructure.showTemplate')}
                      value={form.folder_tv_template}
                      disabled={isScanActive}
                      onChange={handleChange('folder_tv_template')}
                      placeholder="{tv_title} ({year_range})"
                      tags={FOLDER_SHOW_TAGS}
                      fieldKey="folder_tv_template"
                      insertTag={insertTag}
                      previewText={getPreview(form.folder_tv_template, 'tv', { isFile: false, sortOptions })}
                      className="settings-nested-block settings-nested-block--top"
                    />
                  )}
                </div>
              </Stack>
            </div>

            <div className="settings-section-stack">
              <h3 className="settings-section-heading">
                {t('settingsPage.sections.folderStructure.seasonEpisodeFoldersTitle')}
              </h3>
              <Stack gap="xl">
                <div>
                  <Switch
                    id="folder_create_season_dir"
                    checked={form.folder_create_season_dir}
                    disabled={isScanActive}
                    onChange={handleCheckboxChange('folder_create_season_dir')}
                  >
                    {t('settingsPage.sections.folderStructure.createSeasonDir')}
                  </Switch>
                  <span className="ui-field__hint settings-hint--block-compact">
                    {t('settingsPage.sections.folderStructure.createSeasonDirHint')}
                  </span>

                  {form.folder_create_season_dir && (
                    <TemplateFieldSection
                      t={t}
                      inputRef={formInputs.folderSeason}
                      label={t('settingsPage.sections.folderStructure.seasonTemplate')}
                      value={form.folder_season_template}
                      disabled={isScanActive}
                      onChange={handleChange('folder_season_template')}
                      placeholder={t('settingsPage.sections.folderStructure.seasonTemplatePlaceholder')}
                      tags={FOLDER_SEASON_TAGS}
                      fieldKey="folder_season_template"
                      insertTag={insertTag}
                      previewText={getPreview(form.folder_season_template, 'season', { isFile: false, sortOptions })}
                      className="settings-nested-block settings-nested-block--top"
                    />
                  )}
                </div>

                <div>
                  <Switch
                    id="folder_create_episode_dir"
                    checked={form.folder_create_episode_dir}
                    disabled={isScanActive}
                    onChange={handleCheckboxChange('folder_create_episode_dir')}
                  >
                    {t('settingsPage.sections.folderStructure.createEpisodeDir')}
                  </Switch>
                  <span className="ui-field__hint settings-hint--block-compact">
                    {t('settingsPage.sections.folderStructure.createEpisodeDirHint')}
                  </span>

                  {form.folder_create_episode_dir && (
                    <TemplateFieldSection
                      t={t}
                      inputRef={formInputs.folderEpisode}
                      label={t('settingsPage.sections.folderStructure.episodeTemplate')}
                      value={form.folder_episode_template}
                      disabled={isScanActive}
                      onChange={handleChange('folder_episode_template')}
                      placeholder="{tv_title} - {season}{episode}"
                      tags={FOLDER_EPISODE_TAGS}
                      fieldKey="folder_episode_template"
                      insertTag={insertTag}
                      previewText={getPreview(form.folder_episode_template, 'episode', { isFile: false, sortOptions })}
                      className="settings-nested-block settings-nested-block--top"
                    />
                  )}
                </div>
              </Stack>
            </div>
          </Stack>
        </Card>
      )}

      <SettingsLiveImpact
        form={form}
        t={t}
        title={t('settingsPage.sections.liveImpact.title')}
        eyebrow={t('settingsPage.sections.liveImpact.eyebrow')}
        hint={t('settingsPage.sections.liveImpact.folderStructureHint')}
      />
    </Stack>
  );
}


