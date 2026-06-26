import { useState, useEffect, useMemo } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useSettingsQuery } from '@/queries';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from '@/providers/LanguageContext';
import { useUi } from '@/providers/UiProvider';
import {
  useLinkPersonSourceMutation,
  useUnlinkPersonSourceMutation,
  useSetPrimaryPersonSourceMutation,
  useDeletePersonMutation
} from '@/queries/libraryQueries';
import { usePersonDetailQuery } from '@/queries/metadataQueries';
import api from '@/lib/api';
import Input from '@/ui/Input';
import Button from '@/ui/Button';
import IconButton from '@/ui/IconButton';
import Tooltip from '@/ui/Tooltip';
import EmptyState from '@/ui/EmptyState';
import NavButton from '@/ui/NavButton';
import { resolveMediaImageUrl } from '@/lib/imageUrls';
import Spinner from '@/ui/Spinner';
import { Search, Link as LinkIcon, User, Trash2, GitFork, Star, ArrowLeft } from 'lucide-react';

const FemaleSilhouette = () => (
  <svg viewBox="0 0 24 24" className="performer-gender-silhouette" fill="currentColor" style={{ color: '#ec4899' }}>
    <circle cx="12" cy="7" r="4.5" />
    <path d="M12 13c-4.4 0-8 3-8 7.5V22h16v-1.5c0-4.5-3.6-7.5-8-7.5zm-5 7.5c.3-2.3 2.1-4.5 5-4.5s4.7 2.2 5 4.5H7z" />
  </svg>
);

const MaleSilhouette = () => (
  <svg viewBox="0 0 24 24" className="performer-gender-silhouette" fill="currentColor" style={{ color: '#3b82f6' }}>
    <circle cx="12" cy="7" r="4" />
    <path d="M12 12.5c-4.8 0-8.8 3-8.8 7.5V22h17.6v-2c0-4.5-4-7.5-8.8-7.5zm-6 6.5c.5-2.5 3-4.5 6-4.5s5.5 2 6 4.5H6z" />
  </svg>
);

const OtherSilhouette = () => (
  <svg viewBox="0 0 24 24" className="performer-gender-silhouette" fill="currentColor" style={{ color: '#a855f7' }}>
    <circle cx="12" cy="8" r="4" />
    <path d="M12 14c-6.1 0-10 4-10 8h20c0-4-3.9-8-10-8zm-7.9 6c.9-2.5 4-4 7.9-4s7 1.5 7.9 4H4.1z" />
  </svg>
);

export default function PerformerLinkingTab({ personId, defaultQuery = '', person: initialPerson }) {
  const queryClient = useQueryClient();
  const { data: fetchedPerson } = usePersonDetailQuery(personId);
  const person = fetchedPerson || initialPerson;
  const { data: settings } = useSettingsQuery();
  const { t } = useTranslation();
  const { toast } = useUi();
  const [activeSearchSource, setActiveSearchSource] = useState(null);
  const [query, setQuery] = useState(defaultQuery);
  const [results, setResults] = useState([]);

  const filteredResults = useMemo(() => {
    if (!person?.is_adult || !settings?.adult_gender_preference || settings.adult_gender_preference === 'all') {
      return results;
    }
    const pref = settings.adult_gender_preference;
    return results.filter((item) => {
      const g = item.gender;
      if (pref === 'female') return g === 1 || g === '1';
      if (pref === 'male') return g === 2 || g === '2';
      return true;
    });
  }, [results, person?.is_adult, settings?.adult_gender_preference]);
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState('');
  const [hasSearched, setHasSearched] = useState(false);

  const navigate = useNavigate();
  const linkMutation = useLinkPersonSourceMutation();
  const unlinkMutation = useUnlinkPersonSourceMutation();
  const setPrimaryMutation = useSetPrimaryPersonSourceMutation();
  const deleteMutation = useDeletePersonMutation();

  const handleSetPrimary = async (sourceKey) => {
    try {
      await setPrimaryMutation.mutateAsync({
        personId,
        source: sourceKey,
      });
      toast(t('library.details.primarySourceSet') || 'Primary source updated successfully!', 'success');
    } catch (err) {
      toast(err.message || 'Failed to set primary source', 'danger');
    }
  };

  const SOURCE_BUCKETS = [
    { key: 'tmdb', label: 'TMDb', dbName: 'tmdb' },
    { key: 'stashdb', label: 'StashDB', dbName: 'stashdb' },
    { key: 'fansdb', label: 'FansDB', dbName: 'fansdb' },
    { key: 'theporndb', label: 'THEPornDB', dbName: 'porndb' },
  ];

  const getLinkedInfo = (bucket) => {
    if (!person) return null;
    if (person.external_links && person.external_links.length > 0) {
      const link = person.external_links.find(
        (l) => l.provider === bucket.dbName || l.provider === bucket.key
      );
      if (link) return link;
    }
    const extIds = person.external_ids || {};
    const idValue = extIds[bucket.key] || extIds[bucket.dbName] || extIds[`${bucket.key}_id`] || extIds[`${bucket.dbName}_id`];
    if (idValue) {
      return {
        provider: bucket.dbName,
        external_id: idValue,
        profile_url: null
      };
    }
    return null;
  };

  const renderSilhouette = (gender) => {
    if (gender === 1 || gender === '1') return <FemaleSilhouette />;
    if (gender === 2 || gender === '2') return <MaleSilhouette />;
    return <OtherSilhouette />;
  };

  const handleSearch = async (e) => {
    if (e) e.preventDefault();
    if (!query.trim() || !activeSearchSource) return;

    setIsSearching(true);
    setError('');
    try {
      const res = await api.people.searchTmdb(query.trim(), { adultOnly: true, source: activeSearchSource });
      setResults(res || []);
      setHasSearched(true);
    } catch (err) {
      setError(err.message || 'Search failed');
    } finally {
      setIsSearching(false);
    }
  };

  useEffect(() => {
    if (defaultQuery && activeSearchSource) {
      const performSearch = async () => {
        setIsSearching(true);
        setError('');
        try {
          const res = await api.people.searchTmdb(defaultQuery.trim(), { adultOnly: true, source: activeSearchSource });
          setResults(res || []);
          setHasSearched(true);
        } catch (err) {
          setError(err.message || 'Search failed');
        } finally {
          setIsSearching(false);
        }
      };
      performSearch();
    }
  }, [defaultQuery, activeSearchSource]);

  const handleLink = async (item) => {
    let cleanId = item.id;
    if (typeof cleanId === 'string' && cleanId.includes(':')) {
      cleanId = cleanId.split(':')[1] || cleanId;
    }
    try {
      await linkMutation.mutateAsync({
        personId,
        source: activeSearchSource,
        externalId: String(cleanId),
        overrides: {},
        profileUrl: item.profile_path || item.poster_path || null,
      });
      toast(t('library.details.sourceLinked') || 'Source linked successfully!', 'success');
      setActiveSearchSource(null);
      setResults([]);
      setHasSearched(false);
    } catch (err) {
      toast(err.message || 'Failed to link source', 'danger');
    }
  };

  const handleUnlink = (sourceKey, action) => {
    const linkedSourcesCount = SOURCE_BUCKETS.filter(bucket => !!getLinkedInfo(bucket)).length;
    if (action === 'remove' && linkedSourcesCount === 1) {
      deleteMutation.mutate(personId, {
        onSuccess: () => {
          toast('Performer removed from database successfully.', 'success');
          navigate('/library', { replace: true });
        },
        onError: (err) => {
          toast(err.message || 'Failed to delete performer', 'danger');
        }
      });
      return;
    }

    unlinkMutation.mutate(
      { personId, source: sourceKey, action },
      {
        onSuccess: () => {
          toast(
            t('library.details.unlinkSuccess', { source: sourceKey }) || `Successfully unlinked from ${sourceKey}.`,
            'success'
          );
        },
        onError: (err) => {
          toast(
            err.message || 'Failed to unlink source',
            'danger'
          );
        },
      }
    );
  };

  if (activeSearchSource) {
    return (
      <div className="performer-linker performer-linker--search">
        <div className="performer-linker__header">
          <NavButton
            onClick={() => {
              setActiveSearchSource(null);
              setResults([]);
              setHasSearched(false);
            }}
            className="performer-linker__back"
            icon={ArrowLeft}
          >
            Back to Sources
          </NavButton>
          <span className="performer-linker__title">
            Search {SOURCE_BUCKETS.find((b) => b.key === activeSearchSource)?.label}
          </span>
        </div>

        <form onSubmit={handleSearch} className="performer-linker__search-form">
          <div className="performer-linker__input-wrapper">
            <Input
              type="text"
              placeholder={t('library.addPeople.adultTmdbSearchPlaceholder') || 'Search performer...'}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              autoFocus
            />
          </div>
          <Tooltip content={isSearching ? 'Searching...' : 'Search'} side="top">
            <IconButton
              type="submit"
              variant="secondary"
              disabled={isSearching}
            >
              <Search size={16} />
            </IconButton>
          </Tooltip>
        </form>

        <div className="performer-linker__results">
          {isSearching ? (
            <div className="performer-linker__loading">
              <Spinner size="md" />
            </div>
          ) : error ? (
            <div className="performer-linker__error">{error}</div>
          ) : filteredResults.length > 0 ? (
            <div className="performer-linker__results-grid">
              {filteredResults.map((item) => {
                const rawProfileUrl = item.profile_path || item.poster_path;
                const profileUrl = rawProfileUrl ? resolveMediaImageUrl(rawProfileUrl, 'personThumb') : null;
                return (
                  <div key={item.id} className="performer-linker__result-card">
                    <div className="performer-linker__result-image-wrapper">
                      {profileUrl ? (
                        <img src={profileUrl} alt={item.name} className="performer-linker__result-img" />
                      ) : (
                        <div className="performer-linker__result-avatar-placeholder">
                          {renderSilhouette(item.gender !== undefined ? item.gender : person?.gender)}
                        </div>
                      )}
                    </div>
                    <div className="performer-linker__result-content">
                      <div className="performer-linker__result-info">
                        <div className="performer-linker__result-name" title={item.name}>{item.name}</div>
                        {item.disambiguation && (
                          <div className="performer-linker__result-disambiguation" title={item.disambiguation}>
                            {item.disambiguation}
                          </div>
                        )}
                      </div>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => handleLink(item)}
                        disabled={linkMutation.isPending}
                        icon={LinkIcon}
                        className="performer-linker__result-link-btn"
                      >
                        Link
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : hasSearched ? (
            <div className="performer-linker__placeholder">No results match the query. Try a different name.</div>
          ) : (
            <div className="performer-linker__placeholder">
              Type a name above and press search to locate performer data.
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="performer-linker performer-linker--grid">
      <div className="performer-linker-grid">
        {SOURCE_BUCKETS.map((bucket) => {
          const linkedInfo = getLinkedInfo(bucket);
          const isLinked = !!linkedInfo;
          const isPrimary = person?.primary_provider === bucket.dbName;
          const profileImg = isLinked ? (linkedInfo.profile_url ? resolveMediaImageUrl(linkedInfo.profile_url, 'personThumb') : (person.profile_path ? resolveMediaImageUrl(person.profile_path, 'personThumb') : null)) : null;

          return (
            <div
              key={bucket.key}
              className={`performer-linker-card performer-linker-card--${bucket.key} ${isLinked ? 'performer-linker-card--linked' : 'performer-linker-card--unlinked'} ${isPrimary ? 'performer-linker-card--primary' : ''}`}
            >
              <div className="performer-linker-card__image-wrapper">
                {isLinked ? (
                  profileImg ? (
                    <img src={profileImg} alt={person.name} className="performer-linker-card__img" />
                  ) : (
                    <div className="performer-linker-card__avatar-placeholder">
                      <User size={32} />
                    </div>
                  )
                ) : (
                  <div className="performer-linker-card__silhouette">
                    {renderSilhouette(person?.gender)}
                  </div>
                )}
                <div className="performer-linker-card__badge">{bucket.label}</div>
              </div>

              <div className="performer-linker-card__content">
                <div className="performer-linker-card__info">
                  {isLinked ? (
                    <>
                      <div className="performer-linker-card__name">{person.name}</div>
                      <div className="performer-linker-card__ext-id" title={linkedInfo.external_id}>
                        ID: {linkedInfo.external_id}
                      </div>
                    </>
                  ) : (
                    <div className="performer-linker-card__unlinked-text">Not Connected</div>
                  )}
                </div>

                <div className="performer-linker-card__actions">
                  {isLinked ? (
                    <div className="performer-linker-card__linked-actions-wrapper">
                      <div className="performer-linker-card__linked-actions">
                        <Tooltip content="Separate profile connection" side="top">
                          <Button
                            variant="secondary-neutral"
                            size="sm"
                            onClick={() => handleUnlink(bucket.key, 'split')}
                            disabled={unlinkMutation.isPending}
                            icon={GitFork}
                            className="performer-linker-card__action-btn"
                          >
                            Split
                          </Button>
                        </Tooltip>
                        <Tooltip content="Remove profile link" side="top">
                          <Button
                            variant="danger"
                            size="sm"
                            onClick={() => handleUnlink(bucket.key, 'remove')}
                            disabled={unlinkMutation.isPending}
                            icon={Trash2}
                            className="performer-linker-card__action-btn"
                          >
                            Remove
                          </Button>
                        </Tooltip>
                      </div>

                       <Button
                        variant={isPrimary ? "primary" : "secondary-neutral"}
                        size="sm"
                        onClick={() => handleSetPrimary(isPrimary ? "none" : bucket.key)}
                        disabled={setPrimaryMutation.isPending}
                        icon={Star}
                        className="performer-linker-card__primary-btn"
                      >
                        {isPrimary ? "Primary Source" : "Set Primary"}
                      </Button>
                    </div>
                  ) : (
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => {
                        setActiveSearchSource(bucket.key);
                        setQuery(person?.name || '');
                      }}
                      icon={Search}
                      className="performer-linker-card__link-btn"
                    >
                      Connect
                    </Button>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
