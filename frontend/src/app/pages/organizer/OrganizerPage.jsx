import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useQueryClient } from '@tanstack/react-query';
import Page from '../../ui/Page';
import Button from '../../ui/Button';
import SegmentedControl from '../../ui/SegmentedControl';
import Dropdown from '../../ui/Dropdown';
import OrganizerDetailsPanel from './OrganizerDetailsPanel';
import OrganizerHeaderPanel from './OrganizerHeaderPanel';
import OrganizerResultsPanel from './OrganizerResultsPanel';
import { useOrganizerCountQuery, useOrganizerQuery, useScanStatusQuery, useSettingsQuery, useStatsQuery } from '../../queries';
import { useUi } from '../../providers/UiProvider';
import { useTranslation } from '../../providers/LanguageContext';
import {
  normalizeStatusTone,
  PAGE_SIZE_OPTIONS,
} from './organizerMappers';
import { EMPTY_ORGANIZER } from './organizerConstants';
import { useOrganizerActions } from './useOrganizerActions.jsx';
import { useOrganizerColumns } from './useOrganizerColumns.jsx';
import { useOrganizerPageState } from './useOrganizerPageState';
import { useOrganizerTabs } from './useOrganizerTabs';
import { useOrganizerViewModel } from './useOrganizerViewModel';
import { OrganizerModalProvider } from './providers/OrganizerModalProvider';
import { useOrganizerDeleteActions } from './useOrganizerDeleteActions';
import { useLibraryModeStore } from '../../stores/useLibraryModeStore';

const EMPTY_SETTINGS = {};

const getRestoreDismissedLabel = (t, count) => `${t('organizer.buttons.restoreDismissed')} (${count})`;


export default function OrganizerPage() {
  const { t } = useTranslation();
  const { closeModal, openModal, toast } = useUi();
  const queryClient = useQueryClient();
  const organizerQuery = useOrganizerQuery();
  const organizerCountQuery = useOrganizerCountQuery();
  const statsQuery = useStatsQuery();
  const settingsQuery = useSettingsQuery();
  const scanStatusQuery = useScanStatusQuery({
    select: (data) => ({
      active: Boolean(data?.active),
      phase: data?.phase || 'idle',
      stop_requested: Boolean(data?.stop_requested),
      last_completed: data?.last_completed || 0,
    }),
  });
  const organizer = organizerQuery.data || EMPTY_ORGANIZER;
  const scanStatus = scanStatusQuery.data || null;
  const settings = settingsQuery.data || EMPTY_SETTINGS;
  const sessionMode = useLibraryModeStore((state) => state.sessionMode);
  const [scanMode, setScanMode] = useState('movies_tv');
  const [provider, setProvider] = useState('tmdb');
  const [utilityBarTarget, setUtilityBarTarget] = useState(null);

  useEffect(() => {
    if (scanMode === 'scenes') {
      setProvider('stashdb');
    } else {
      setProvider('tmdb');
    }
  }, [scanMode]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setUtilityBarTarget(document.getElementById('shell-utility-bar-center'));
  }, []);
  const scanModeOptions = useMemo(() => {
    const options = [
      { value: 'movies_tv', label: t('organizer.scanModes.moviesTv') },
    ];
    if (settings.include_adult && sessionMode === 'nsfw') {
      options.push({ value: 'scenes', label: t('organizer.scanModes.scenes') });
    }
    return options;
  }, [sessionMode, settings.include_adult, t]);

  useEffect(() => {
    if (!scanModeOptions.some((option) => option.value === scanMode)) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setScanMode('movies_tv');
    }
  }, [scanMode, scanModeOptions]);
  const isScanActive = Boolean(scanStatus?.active);
  const rawOrganizerItemCount = organizerCountQuery.data?.count ?? statsQuery.data?.unmatched;
  const organizerItemCount = rawOrganizerItemCount == null ? null : Number(rawOrganizerItemCount);
  const isOrganizerCountReady = Number.isFinite(organizerItemCount);
  const organizerRuleSignature = useMemo(() => JSON.stringify({
    collision_strategy: settings.collision_strategy || 'keep_both',
    collision_duration_tolerance_seconds: settings.collision_duration_tolerance_seconds || '10',
    naming_filename_casing: settings.naming_filename_casing || 'default',
    naming_word_separator: settings.naming_word_separator || 'space',
    naming_movie_template: settings.naming_movie_template || '',
    naming_episode_template: settings.naming_episode_template || '',
    naming_custom_tag: settings.naming_custom_tag || '',
    naming_video_exts: settings.naming_video_exts || '',
    folder_organization_enabled: settings.folder_organization_enabled !== false,
    folder_move_to_library: settings.folder_move_to_library !== false,
    folder_sort_by_type: settings.folder_sort_by_type !== false,
    folder_movies_name: settings.folder_movies_name || '',
    folder_tv_name: settings.folder_tv_name || '',
    folder_adult_name: settings.folder_adult_name || '',
    naming_adult_subfolders_enabled: settings.naming_adult_subfolders_enabled !== false,
    folder_adult_movies_name: settings.folder_adult_movies_name || '',
    folder_adult_tv_name: settings.folder_adult_tv_name || '',
    folder_adult_scenes_name: settings.folder_adult_scenes_name || '',
    naming_scene_template: settings.naming_scene_template || '',
    naming_scene_date_format: settings.naming_scene_date_format || '',
    naming_scene_prevent_title_performer: settings.naming_scene_prevent_title_performer !== false,
    scene_tag_limit: settings.scene_tag_limit ?? 0,
    scene_tag_separator: settings.scene_tag_separator ?? ' ',
    scene_tag_blacklist: settings.scene_tag_blacklist || '',
    naming_squeeze_studio_names: Boolean(settings.naming_squeeze_studio_names),
    naming_performer_limit: settings.naming_performer_limit || '3',
    naming_performer_limit_keep: Boolean(settings.naming_performer_limit_keep),
    naming_performer_splitchar: settings.naming_performer_splitchar || '',
    naming_performer_gender_filter: settings.naming_performer_gender_filter || 'all',
    naming_performer_sort: settings.naming_performer_sort || 'order',
    scene_grouping_mode: settings.scene_grouping_mode || 'none',
    folder_scene_template: settings.folder_scene_template || '',
    folder_create_movie_subdir: settings.folder_create_movie_subdir !== false,
    folder_movie_template: settings.folder_movie_template || '',
    folder_create_show_dir: settings.folder_create_show_dir !== false,
    folder_tv_template: settings.folder_tv_template || '',
    folder_create_season_dir: settings.folder_create_season_dir !== false,
    folder_season_template: settings.folder_season_template || '',
    folder_create_episode_dir: Boolean(settings.folder_create_episode_dir),
    folder_episode_template: settings.folder_episode_template || '',
    folder_remove_empty: settings.folder_remove_empty !== false,
    folder_create_collection_dir: settings.folder_create_collection_dir !== false,
    folder_collection_mode: settings.folder_collection_mode || '',
    folder_collection_threshold: settings.folder_collection_threshold || '',
    folder_collection_template: settings.folder_collection_template || '',
    extras_enabled: settings.extras_enabled !== false,
    extras_folder_mode: settings.extras_folder_mode || '',
    extras_subfolder_name: settings.extras_subfolder_name || '',
    extras_video_action: settings.extras_video_action || 'rename',
    extras_sub_action: settings.extras_sub_action || 'rename',
    extras_audio_action: settings.extras_audio_action || 'rename',
    extras_img_action: settings.extras_img_action || 'rename',
    extras_meta_action: settings.extras_meta_action || 'rename',
    extras_video_template: settings.extras_video_template || '',
    extras_sub_template: settings.extras_sub_template || '',
    extras_audio_template: settings.extras_audio_template || '',
    extras_img_template: settings.extras_img_template || '',
    extras_meta_template: settings.extras_meta_template || '',
    include_adult: Boolean(settings.include_adult),
  }), [
    settings,
  ]);
  const previousRuleSignatureRef = useRef(organizerRuleSignature);
  const {
    activeExtrasTab,
    activeManualTab,
    activeImage,
    activeImageIndex,
    activeImages,
    activeMainTab,
    activeRow,
    currentPage,
    focusFirstAvailableResult,
    handleAdvanceDetailsImage,
    handleSortToggle,
    handleToggleAll,
    handleToggleDetails,
    handleToggleRow,
    isDetailsCollapsed,
    pageSize,
    pageStart,
    pageEnd,
    paginatedRows,
    searchQuery,
    selectedRows,
    selectedRowIds,
    clearSelectedRows,
    setActiveExtrasTab,
    setActiveManualTab,
    setActiveMainTab,
    setActiveRowId,
    setPageAndScrollToTop,
    setPageSize,
    setSearchQuery,
    shouldShowDetailsCarousel,
    shouldShowDetailsPoster,
    sortConfig,
    sortedRows,
    tabCounts,
    totalPages,
    dismissRows,
    restoreDismissedRows,
    dismissedCount,
    dismissedRowIds,
  } = useOrganizerPageState({ organizer, t, scanMode, sessionMode });

  const {
    handleBrowseAndScan,
    handleLoadAll,
    handleRename,
    handleScanPaths,
    isBrowseStarting,
    isLoadingAll,
    isRenameStarting,
  } = useOrganizerActions({
    defaultScanDir: settingsQuery.data?.default_scan_dir,
    organizerCountQuery,
    organizerQuery,
    isScanActive,
    onResultsReady: focusFirstAvailableResult,
    queryClient,
    t,
    toast,
    openModal,
    closeModal,
    dismissedRowIds,
    scanStatusQuery,
    scanMode,
    includeAdult: Boolean(settings.include_adult && sessionMode === 'nsfw'),
    provider,
  });


  const { computedExtrasTabs, computedManualTabs, computedMainTabs } = useOrganizerTabs({
    organizerExtras: organizer.extras,
    t,
    tabCounts,
    dismissedRowIds,
    scanMode,
  });

  const {
    browseButtonLabel,
    emptyState: organizerEmptyState,
    hasDatabaseItems,
    hasVisibleItems,
    loadAllButtonLabel,
    loadRestButtonLabel,
    loadingState: organizerLoadingState,
    renameButtonLabel,
    shouldShowDetailsPanel,
    shouldShowLoadRest,
    summaryText,
  } = useOrganizerViewModel({
    organizer,
    organizerItemCount,
    isBrowseStarting,
    isOrganizerCountReady,
    isLoadingAll,
    isRenameStarting,
    isScanActive,
    pageEnd,
    pageStart,
    scanPhase: scanStatus?.phase,
    sortedRows,
    t,
  });

  useEffect(() => {
    if (!utilityBarTarget) {
      return undefined;
    }

    const detailsInset = !shouldShowDetailsPanel ? '0px' : isDetailsCollapsed ? '44px' : '320px';
    utilityBarTarget.style.setProperty('--utility-bar-right-inset', detailsInset);

    return () => {
      utilityBarTarget.style.removeProperty('--utility-bar-right-inset');
    };
  }, [isDetailsCollapsed, shouldShowDetailsPanel, utilityBarTarget]);
  const emptyStateActions = organizerEmptyState ? (
    <>
      {hasDatabaseItems ? (
        <>
          <Button
            variant="secondary"
            size="sm"
            onClick={handleBrowseAndScan}
            disabled={isScanActive || isBrowseStarting}
          >
            {browseButtonLabel}
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={handleLoadAll}
            disabled={isLoadingAll}
          >
            {loadAllButtonLabel}
          </Button>
        </>
      ) : (
        <Button
          variant="primary"
          size="sm"
          onClick={handleBrowseAndScan}
          disabled={isScanActive || isBrowseStarting}
        >
          {browseButtonLabel}
        </Button>
      )}
    </>
  ) : null;

  const handleRemoveAll = () => {
    const allItems = [
      ...(organizer.manual || []),
      ...(organizer.movies || []),
      ...(organizer.tv || []),
      ...(organizer.collisions || []),
    ];
    const ids = allItems.map((item) => `item-${item.id}`);
    dismissRows(ids);
  };

  const allMediaItems = [
    ...(organizer.manual || []),
    ...(organizer.movies || []),
    ...(organizer.tv || []),
    ...(organizer.collisions || []),
  ];
  const hasActiveVisibleItems = allMediaItems.some(item => !dismissedRowIds.has(`item-${item.id}`));

  const headerActions = (hasVisibleItems || dismissedCount > 0) ? (
    <>
      {hasActiveVisibleItems ? (
        <Button
          variant="secondary-neutral"
          size="sm"
          className="organizer-panel__browse-btn"
          onClick={handleRemoveAll}
        >
          {t('organizer.buttons.removeAll')}
        </Button>
      ) : null}
      {dismissedCount > 0 ? (
        <Button
          variant="secondary-neutral"
          size="sm"
          className="organizer-panel__browse-btn"
          onClick={restoreDismissedRows}
        >
          {getRestoreDismissedLabel(t, dismissedCount)}
        </Button>
      ) : null}
      {hasVisibleItems ? (
        <>
          <Button
            variant="secondary"
            size="sm"
            className="organizer-panel__browse-btn"
            onClick={handleBrowseAndScan}
            disabled={isScanActive || isBrowseStarting}
          >
            {browseButtonLabel}
          </Button>
          {shouldShowLoadRest ? (
            <Button
              variant="secondary"
              size="sm"
              className="organizer-panel__browse-btn"
              onClick={handleLoadAll}
              disabled={isLoadingAll}
            >
              {loadRestButtonLabel}
            </Button>
          ) : null}
          <Button
            variant="primary"
            size="sm"
            className="organizer-panel__browse-btn"
            onClick={handleRename}
            disabled={isScanActive || isRenameStarting}
          >
            {renameButtonLabel}
          </Button>
        </>
      ) : null}
    </>
  ) : null;

  const { refreshOrganizer } = useOrganizerDeleteActions({
    t,
    closeModal,
    toast,
    queryClient,
    focusFirstAvailableResult,
    clearSelectedRows,
  });

  useEffect(() => {
    if (previousRuleSignatureRef.current === organizerRuleSignature) {
      return;
    }

    previousRuleSignatureRef.current = organizerRuleSignature;

    if (!organizerQuery.data || isScanActive) {
      return;
    }

    refreshOrganizer().catch(() => {
      toast(t('organizer.toasts.refreshRulesFailed'), 'danger');
    });
  }, [
    organizerQuery.data,
    focusFirstAvailableResult,
    isScanActive,
    organizerRuleSignature,
    queryClient,
    toast,
    refreshOrganizer,
    t,
  ]);

  return (
    <OrganizerModalProvider
      focusFirstAvailableResult={focusFirstAvailableResult}
      clearSelectedRows={clearSelectedRows}
      dismissRows={dismissRows}
      selectedRows={selectedRows}
    >
      {utilityBarTarget && scanModeOptions.length > 1 && createPortal(
        <div className="organizer-utility-bar-wrapper">
          <SegmentedControl
            value={scanMode}
            onChange={setScanMode}
            options={scanModeOptions}
            className="main-scan-mode"
          />
          {sessionMode === 'nsfw' && (
            <div key={scanMode} className="provider-segmented-control-wrapper animate-slide-in">
              <SegmentedControl
                variant="filter"
                value={provider}
                onChange={setProvider}
                options={
                  scanMode === 'scenes'
                    ? [
                        { value: 'stashdb', label: 'StashDB' },
                        { value: 'porndb', label: 'PornDB' },
                        { value: 'fansdb', label: 'FansDB' },
                      ]
                    : [
                        { value: 'tmdb', label: 'TMDb' },
                        { value: 'porndb', label: 'PornDB' },
                      ]
                }
              />
            </div>
          )}
        </div>,
        utilityBarTarget
      )}
      <OrganizerPageContent
        activeExtrasTab={activeExtrasTab}
        activeManualTab={activeManualTab}
        activeImage={activeImage}
        activeImageIndex={activeImageIndex}
        activeImages={activeImages}
        activeMainTab={activeMainTab}
        activeRow={activeRow}
        currentPage={currentPage}
        handleAdvanceDetailsImage={handleAdvanceDetailsImage}
        handleSortToggle={handleSortToggle}
        handleToggleAll={handleToggleAll}
        handleToggleDetails={handleToggleDetails}
        handleToggleRow={handleToggleRow}
        isDetailsCollapsed={isDetailsCollapsed}
        pageSize={pageSize}
        paginatedRows={paginatedRows}
        searchQuery={searchQuery}
        selectedRowIds={selectedRowIds}
        setActiveExtrasTab={setActiveExtrasTab}
        setActiveManualTab={setActiveManualTab}
        setActiveMainTab={setActiveMainTab}
        setActiveRowId={setActiveRowId}
        setPageAndScrollToTop={setPageAndScrollToTop}
        setPageSize={setPageSize}
        setSearchQuery={setSearchQuery}
        shouldShowDetailsCarousel={shouldShowDetailsCarousel}
        shouldShowDetailsPoster={shouldShowDetailsPoster}
        sortConfig={sortConfig}
        sortedRows={sortedRows}
        totalPages={totalPages}
        settingsQuery={settingsQuery}
        organizerQuery={organizerQuery}
        computedExtrasTabs={computedExtrasTabs}
        computedManualTabs={computedManualTabs}
        computedMainTabs={computedMainTabs}
        organizerEmptyState={organizerEmptyState}
        organizerLoadingState={organizerLoadingState}
        shouldShowDetailsPanel={shouldShowDetailsPanel}
        summaryText={summaryText}
        emptyStateActions={emptyStateActions}
        headerActions={headerActions}
        onDropPaths={handleScanPaths}
        isDropzoneDisabled={isScanActive || isBrowseStarting || isLoadingAll || isRenameStarting}
        scanMode={scanMode}
        scanModeOptions={scanModeOptions}
        setScanMode={setScanMode}
        sessionMode={sessionMode}
        provider={provider}
        setProvider={setProvider}
        t={t}
      />
    </OrganizerModalProvider>
  );
}

function OrganizerPageContent({
  activeExtrasTab,
  activeManualTab,
  activeImage,
  activeImageIndex,
  activeImages,
  activeMainTab,
  activeRow,
  currentPage,
  handleAdvanceDetailsImage,
  handleSortToggle,
  handleToggleAll,
  handleToggleDetails,
  handleToggleRow,
  isDetailsCollapsed,
  pageSize,
  paginatedRows,
  searchQuery,
  selectedRowIds,
  setActiveExtrasTab,
  setActiveManualTab,
  setActiveMainTab,
  setActiveRowId,
  setPageAndScrollToTop,
  setPageSize,
  setSearchQuery,
  shouldShowDetailsCarousel,
  shouldShowDetailsPoster,
  sortConfig,
  sortedRows,
  totalPages,
  settingsQuery,
  organizerQuery,
  computedExtrasTabs,
  computedManualTabs,
  computedMainTabs,
  organizerEmptyState,
  organizerLoadingState,
  shouldShowDetailsPanel,
  summaryText,
  emptyStateActions,
  headerActions,
  onDropPaths,
  isDropzoneDisabled,
  scanMode,
  scanModeOptions,
  setScanMode,
  sessionMode,
  provider,
  setProvider,
  t,
}) {
  const { columns } = useOrganizerColumns({
    activeExtrasTab,
    activeMainTab,
    collisionStrategy: settingsQuery.data?.collision_strategy,
    handleSortToggle,
    handleToggleAll,
    handleToggleRow,
    normalizeStatusTone,
    paginatedRows,
    selectedRowIds,
    sortConfig,
    t,
  });

  const currentContextLabel =
    activeMainTab === 'manual'
      ? computedManualTabs.find((tab) => tab.value === activeManualTab)?.label || t('organizer.tabs.manual')
      : activeMainTab === 'extras'
        ? computedExtrasTabs.find((tab) => tab.value === activeExtrasTab)?.label || t('organizer.tabs.extras')
        : computedMainTabs.find((tab) => tab.value === activeMainTab)?.label || t('organizer.tabs.manual');

  const organizerInlineEmptyText = organizerQuery.isLoading
    ? t('organizer.table.emptyLoading')
    : searchQuery.trim()
      ? t('organizer.table.emptySearch', { context: currentContextLabel }) || `No items match your search in ${currentContextLabel}.`
      : t('organizer.table.emptyCategory', { context: currentContextLabel }) || `No items in ${currentContextLabel}.`;

  return (
    <Page className="organizer-page">
      <div className={`organizer-main ${!shouldShowDetailsPanel ? 'is-details-hidden' : isDetailsCollapsed ? 'is-details-collapsed' : ''}`}>
        <div className="organizer-main__content">
          <OrganizerHeaderPanel
            activeExtrasTab={activeExtrasTab}
            activeManualTab={activeManualTab}
            activeMainTab={activeMainTab}
            actions={headerActions}
            scanMode={scanMode}
            scanModeLabel={t('organizer.scanModeLabel')}
            scanModeOptions={scanModeOptions}
            onChangeScanMode={setScanMode}
            computedExtrasTabs={computedExtrasTabs}
            computedManualTabs={computedManualTabs}
            computedMainTabs={computedMainTabs}
            onChangeExtrasTab={setActiveExtrasTab}
            onChangeManualTab={setActiveManualTab}
            onChangeMainTab={setActiveMainTab}
            provider={provider}
            onChangeProvider={setProvider}
            sessionMode={sessionMode}
            searchPlaceholder={
              activeMainTab === 'manual'
                ? t('organizer.searchPlaceholderManual')
                : activeMainTab === 'movies'
                ? t('organizer.searchPlaceholderMovies')
                : activeMainTab === 'episodes'
                ? t('organizer.searchPlaceholderEpisodes')
                : activeMainTab === 'extras'
                ? t('organizer.searchPlaceholderExtras')
                : t('organizer.searchPlaceholder')
            }
            searchQuery={searchQuery}
            setSearchQuery={setSearchQuery}
            title={sessionMode === 'nsfw' ? t('organizer.adultTitle') : t('organizer.title')}
          />

          <OrganizerResultsPanel
            activeRowId={activeRow?.id || null}
            columns={columns}
            currentPage={currentPage}
            dropOverlayDescription={t('organizer.dropzone.description')}
            dropOverlayLabel={t('organizer.dropzone.label')}
            onDropPaths={onDropPaths}
            isDropzoneDisabled={isDropzoneDisabled}
            emptyActions={emptyStateActions}
            emptyState={organizerEmptyState}
            emptyText={organizerInlineEmptyText}
            labels={t('organizer.pagination')}
            loadingState={organizerLoadingState}
            onPageChange={setPageAndScrollToTop}
            onPageSizeChange={setPageSize}
            onRowClick={(row) => setActiveRowId(row.id)}
            pageSize={pageSize}
            pageSizeOptions={PAGE_SIZE_OPTIONS}
            rows={paginatedRows}
            showPageSizes
            summaryText={summaryText}
            totalItems={sortedRows.length}
            totalPages={totalPages}
          />
        </div>

        {shouldShowDetailsPanel ? (
          <OrganizerDetailsPanel
            activeImage={activeImage}
            activeImageIndex={activeImageIndex}
            activeImages={activeImages}
            activeRow={activeRow}
            isDetailsCollapsed={isDetailsCollapsed}
            onAdvanceImage={handleAdvanceDetailsImage}
            onToggleDetails={handleToggleDetails}
            shouldShowDetailsCarousel={shouldShowDetailsCarousel}
            shouldShowDetailsPoster={shouldShowDetailsPoster}
          />
        ) : null}
      </div>
    </Page>
  );
}


