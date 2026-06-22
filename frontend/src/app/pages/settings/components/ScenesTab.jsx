import Card from '@/ui/Card';
import Dropdown from '@/ui/Dropdown';
import Input from '@/ui/Input';
import Stack from '@/ui/Stack';
import Switch from '@/ui/Switch';
import { FOLDER_SCENE_TAGS, SCENE_TAGS } from '../settingsTemplateTags.js';
import { useTemplatePreview } from '../hooks';
import { useSettingsFormContext } from '../SettingsFormContext.jsx';
import TemplateFieldSection from './TemplateFieldSection.jsx';

const formatPreviewDate = (format) => String(format || '%Y-%m-%d')
  .replaceAll('%Y', '2024')
  .replaceAll('%m', '06')
  .replaceAll('%d', '14');

export default function ScenesTab({
  form,
  t,
  handleChange,
  handleCheckboxChange,
  insertTag,
  formInputs,
}) {
  const getPreview = useTemplatePreview(form);
  const { renderContext } = useSettingsFormContext();
  const isScanActive = Boolean(renderContext?.isBackgroundActive);

  const studioName = form.naming_squeeze_studio_names ? 'VelvetStudios' : 'Velvet Studios';
  const parentStudioName = form.naming_squeeze_studio_names ? 'VelvetMediaGroup' : 'Velvet Media Group';
  const performerSeparator = form.naming_performer_splitchar || ' & ';
  const tagBlacklist = new Set(
    String(form.scene_tag_blacklist || '')
      .split(',')
      .map((tag) => tag.trim().toLocaleLowerCase())
      .filter(Boolean)
  );
  const tagLimit = Math.max(0, Number.parseInt(form.scene_tag_limit, 10) || 0);
  let previewTags = ['Audition', 'Brunette', 'Couples', 'Feature', 'HD', 'Roleplay']
    .filter((tag) => !tagBlacklist.has(tag.toLocaleLowerCase()))
    .sort((left, right) => left.localeCompare(right));
  previewTags = tagLimit > 0 ? previewTags.slice(0, tagLimit) : [];
  const sceneContext = {
    date: formatPreviewDate(form.naming_scene_date_format),
    studio: studioName,
    parent_studio: parentStudioName,
    studio_family: parentStudioName,
    performers: ['Lana Rose', 'Alex Stone'].join(performerSeparator),
    performer: ['Lana Rose', 'Alex Stone'].join(performerSeparator),
    tags: previewTags.join(form.scene_tag_separator || ' '),
  };
  const scenePreview = getPreview(form.naming_scene_template, 'scene', { contextOverrides: sceneContext });
  const folderPreview = form.folder_scene_template
    ? getPreview(form.folder_scene_template, 'scene', { isFile: false, contextOverrides: sceneContext })
    : '';
  const dateFormatOptions = [
    { value: '%Y-%m-%d', label: t('settingsPage.sections.scenes.dateFormatOptions.yearMonthDayDash') },
    { value: '%Y.%m.%d', label: t('settingsPage.sections.scenes.dateFormatOptions.yearMonthDayDot') },
    { value: '%d-%m-%Y', label: t('settingsPage.sections.scenes.dateFormatOptions.dayMonthYearDash') },
    { value: '%d.%m.%Y', label: t('settingsPage.sections.scenes.dateFormatOptions.dayMonthYearDot') },
    { value: '%Y', label: t('settingsPage.sections.scenes.dateFormatOptions.yearOnly') },
  ];
  const tagSeparatorOptions = [
    { value: ' ', label: t('settingsPage.sections.scenes.tagSeparatorOptions.space') },
    { value: ', ', label: t('settingsPage.sections.scenes.tagSeparatorOptions.comma') },
    { value: ' - ', label: t('settingsPage.sections.scenes.tagSeparatorOptions.dash') },
    { value: ' · ', label: t('settingsPage.sections.scenes.tagSeparatorOptions.middleDot') },
    { value: '_', label: t('settingsPage.sections.scenes.tagSeparatorOptions.underscore') },
  ];
  const groupingOptions = [
    { value: 'none', label: t('settingsPage.sections.scenes.groupingOptions.none') },
    { value: 'studio', label: t('settingsPage.sections.scenes.groupingOptions.studio') },
    { value: 'parent_studio', label: t('settingsPage.sections.scenes.groupingOptions.parentStudio') },
    { value: 'parent_studio_studio', label: t('settingsPage.sections.scenes.groupingOptions.parentStudioStudio') },
  ];
  const performerSortOptions = [
    { value: 'order', label: t('settingsPage.sections.scenes.performerSortOptions.order') },
    { value: 'name', label: t('settingsPage.sections.scenes.performerSortOptions.name') },
    { value: 'popularity', label: t('settingsPage.sections.scenes.performerSortOptions.popularity') },
  ];
  const performerGenderOptions = [
    { value: 'all', label: t('settingsPage.sections.scenes.performerGenderOptions.all') },
    { value: 'female', label: t('settingsPage.sections.scenes.performerGenderOptions.female') },
    { value: 'male', label: t('settingsPage.sections.scenes.performerGenderOptions.male') },
  ];

  return (
    <Stack gap="xl">
      <Card title={t('settingsPage.sections.scenes.scanTitle')} eyebrow={t('settingsPage.sections.scenes.scanEyebrow')}>
        <Stack gap="lg">
          <Input
            label={t('settingsPage.sections.scenes.minVideoSizeMb')}
            hint={t('settingsPage.sections.scenes.minVideoSizeMbHint')}
            type="number"
            min="0"
            step="0.1"
            value={form.adult_min_video_size_mb}
            disabled={isScanActive}
            onChange={handleChange('adult_min_video_size_mb')}
          />
          <Input
            label={t('settingsPage.sections.scenes.minVideoDurationMinutes')}
            hint={t('settingsPage.sections.scenes.minVideoDurationMinutesHint')}
            type="number"
            min="0"
            step="0.05"
            value={form.adult_min_video_duration_minutes}
            disabled={isScanActive}
            onChange={handleChange('adult_min_video_duration_minutes')}
          />
          <Input
            label={t('settingsPage.sections.scenes.fansdbMinVideoDurationMinutes')}
            hint={t('settingsPage.sections.scenes.fansdbMinVideoDurationMinutesHint')}
            type="number"
            min="0"
            step="0.05"
            value={form.fansdb_adult_min_video_duration_minutes}
            disabled={isScanActive}
            onChange={handleChange('fansdb_adult_min_video_duration_minutes')}
          />
        </Stack>
      </Card>

      <Card title={t('settingsPage.sections.scenes.namingTitle')} eyebrow={t('settingsPage.sections.scenes.eyebrow')}>
        <Stack gap="lg">
          <TemplateFieldSection
            t={t}
            inputRef={formInputs.namingScene}
            label={t('settingsPage.sections.scenes.filenameTemplate')}
            hint={t('settingsPage.sections.scenes.filenameTemplateHint')}
            value={form.naming_scene_template}
            disabled={isScanActive}
            onChange={handleChange('naming_scene_template')}
            placeholder="{studio} {performers} {date} {title} [{resolution}]"
            tags={SCENE_TAGS}
            fieldKey="naming_scene_template"
            insertTag={insertTag}
            previewText={scenePreview}
          />
          <Dropdown
            label={t('settingsPage.sections.scenes.dateFormat')}
            hint={t('settingsPage.sections.scenes.dateFormatHint')}
            value={form.naming_scene_date_format}
            options={dateFormatOptions}
            disabled={isScanActive}
            onChange={handleChange('naming_scene_date_format')}
          />
          <Switch
            id="naming_scene_prevent_title_performer"
            checked={form.naming_scene_prevent_title_performer}
            disabled={isScanActive}
            onChange={handleCheckboxChange('naming_scene_prevent_title_performer')}
          >
            {t('settingsPage.sections.scenes.preventTitlePerformer')}
          </Switch>
          <span className="ui-field__hint settings-hint--tight-top">
            {t('settingsPage.sections.scenes.preventTitlePerformerHint')}
          </span>
        </Stack>
      </Card>

      <Card title={t('settingsPage.sections.scenes.groupingTitle')} eyebrow={t('settingsPage.sections.scenes.eyebrow')}>
        <Stack gap="lg">
          <Dropdown
            label={t('settingsPage.sections.scenes.groupingMode')}
            hint={t('settingsPage.sections.scenes.groupingModeHint')}
            value={form.scene_grouping_mode}
            options={groupingOptions}
            disabled={isScanActive}
            onChange={handleChange('scene_grouping_mode')}
          />
          <TemplateFieldSection
            t={t}
            inputRef={formInputs.folderScene}
            label={t('settingsPage.sections.scenes.folderTemplate')}
            hint={t('settingsPage.sections.scenes.folderTemplateHint')}
            value={form.folder_scene_template}
            disabled={isScanActive}
            onChange={handleChange('folder_scene_template')}
            placeholder="{year} - {title}"
            tags={FOLDER_SCENE_TAGS}
            fieldKey="folder_scene_template"
            insertTag={insertTag}
            previewText={folderPreview}
          />
        </Stack>
      </Card>

      <Card title={t('settingsPage.sections.scenes.tagsTitle')} eyebrow={t('settingsPage.sections.scenes.eyebrow')}>
        <Stack gap="lg">
          <Input
            label={t('settingsPage.sections.scenes.tagLimit')}
            hint={t('settingsPage.sections.scenes.tagLimitHint')}
            type="number"
            min="0"
            value={form.scene_tag_limit}
            disabled={isScanActive}
            onChange={handleChange('scene_tag_limit')}
          />
          <Dropdown
            label={t('settingsPage.sections.scenes.tagSeparator')}
            hint={t('settingsPage.sections.scenes.tagSeparatorHint')}
            value={form.scene_tag_separator}
            options={tagSeparatorOptions}
            disabled={isScanActive}
            onChange={handleChange('scene_tag_separator')}
          />
          <Input
            label={t('settingsPage.sections.scenes.tagBlacklist')}
            hint={t('settingsPage.sections.scenes.tagBlacklistHint')}
            value={form.scene_tag_blacklist}
            disabled={isScanActive}
            onChange={handleChange('scene_tag_blacklist')}
            placeholder="Compilation, Trailer, VR"
          />
        </Stack>
      </Card>

      <Card title={t('settingsPage.sections.scenes.performersTitle')} eyebrow={t('settingsPage.sections.scenes.eyebrow')}>
        <Stack gap="lg">
          <Input
            label={t('settingsPage.sections.scenes.performerLimit')}
            hint={t('settingsPage.sections.scenes.performerLimitHint')}
            type="number"
            min="1"
            value={form.naming_performer_limit}
            disabled={isScanActive}
            onChange={handleChange('naming_performer_limit')}
          />
          <Switch
            id="naming_performer_limit_keep"
            checked={form.naming_performer_limit_keep}
            disabled={isScanActive}
            onChange={handleCheckboxChange('naming_performer_limit_keep')}
          >
            {t('settingsPage.sections.scenes.keepPerformersAtLimit')}
          </Switch>
          <Input
            label={t('settingsPage.sections.scenes.performerSeparator')}
            value={form.naming_performer_splitchar}
            disabled={isScanActive}
            onChange={handleChange('naming_performer_splitchar')}
            placeholder=" & "
          />
          <Dropdown
            label={t('settingsPage.sections.scenes.performerSort')}
            hint={t('settingsPage.sections.scenes.performerSortHint')}
            value={form.naming_performer_sort}
            options={performerSortOptions}
            disabled={isScanActive}
            onChange={handleChange('naming_performer_sort')}
          />
          <Dropdown
            label={t('settingsPage.sections.scenes.performerGender')}
            value={form.naming_performer_gender_filter}
            options={performerGenderOptions}
            disabled={isScanActive}
            onChange={handleChange('naming_performer_gender_filter')}
          />
          <Switch
            id="naming_squeeze_studio_names"
            checked={form.naming_squeeze_studio_names}
            disabled={isScanActive}
            onChange={handleCheckboxChange('naming_squeeze_studio_names')}
          >
            {t('settingsPage.sections.scenes.squeezeStudioNames')}
          </Switch>
          <span className="ui-field__hint settings-hint--tight-top">
            {t('settingsPage.sections.scenes.squeezeStudioNamesHint')}
          </span>
        </Stack>
      </Card>
    </Stack>
  );
}
