import { useState, useEffect } from 'react';
import { useAddPersonTmdbMutation } from '@/queries';
import api from '@/lib/api';
import Spinner from '@/ui/Spinner';
import Pill from '@/ui/Pill';
import { Check } from 'lucide-react';
import { resolveMediaImageUrl } from '@/lib/imageUrls';

const getBulkImportResolveStatePrefix = (isAdult) => `bulkImportResolvedRows:${isAdult ? 'nsfw' : 'sfw'}:`;

const BULLET_POINT = '• ';
const QUESTION_MARK = '?';


export default function BulkImportResolveModalContent({ t, isAdult = false }) {
  const [bulkReport, setBulkReport] = useState(null);
  const [isLoadingReport, setIsLoadingReport] = useState(true);
  const [resolvedRows, setResolvedRows] = useState({});
  const [pendingAdds, setPendingAdds] = useState({});
  const [hoveredResolvedRow, setHoveredResolvedRow] = useState(null);

  useEffect(() => {
    const fetchReport = async () => {
      try {
        const rep = await api.people.bulkImportReport('all', { adultOnly: isAdult });
        if (rep && rep.status === 'completed') {
          setBulkReport(rep.report);
        }
      } catch (err) {
        console.error('Failed to load bulk import report:', err);
      } finally {
        setIsLoadingReport(false);
      }
    };
    fetchReport();
  }, [isAdult]);

  const addPersonMutation = useAddPersonTmdbMutation();
  const resolveStateStorageKey = bulkReport?.finished_at
    ? `${getBulkImportResolveStatePrefix(isAdult)}${bulkReport.finished_at}`
    : null;

  const [prevResolveStateStorageKey, setPrevResolveStateStorageKey] = useState(resolveStateStorageKey);
  if (resolveStateStorageKey !== prevResolveStateStorageKey) {
    setPrevResolveStateStorageKey(resolveStateStorageKey);
    let parsed = {};
    if (resolveStateStorageKey) {
      try {
        const saved = localStorage.getItem(resolveStateStorageKey);
        parsed = saved ? JSON.parse(saved) : {};
      } catch {
        parsed = {};
      }
    }
    setResolvedRows(parsed);
  }

  const resolveProfileUrl = (path) => {
    return resolveMediaImageUrl(path, 'personThumb');
  };

  const textKey = (adultKey, defaultKey) => (isAdult ? adultKey : defaultKey);

  if (isLoadingReport) {
    return (
      <div className="bulk-people-resolve-modal__loading">
        <Spinner label={t(textKey('library.addPeople.adultLoadingReport', 'library.addPeople.loadingReport'))} />
      </div>
    );
  }

  if (!bulkReport) {
    return (
      <div className="bulk-people-resolve-modal__empty">
        {t(textKey('library.addPeople.adultNoReportFound', 'library.addPeople.noReportFound'))}
      </div>
    );
  }

  return (
    <div className="add-people-modal bulk-people-resolve-modal">
      <div className="bulk-people-resolve-modal__report">
        <strong className="bulk-people-resolve-modal__report-title">
          {t(textKey('library.addPeople.adultImportResults', 'library.addPeople.importResults'))}
        </strong>
        <div>{BULLET_POINT}{t('library.addPeople.addedCount')} {bulkReport.added_count}</div>
        <div>{BULLET_POINT}{t('library.addPeople.alreadyInLibraryCount')} {bulkReport.already_in_library_count}</div>
        {bulkReport.multiple_match_count > 0 && (
          <div className="bulk-people-resolve-modal__report-line bulk-people-resolve-modal__report-line--warning">
            {BULLET_POINT}{t('library.addPeople.multipleMatchCountBanner')} {bulkReport.multiple_match_count}
          </div>
        )}
        {bulkReport.no_match_count > 0 && (
          <div className="bulk-people-resolve-modal__report-line bulk-people-resolve-modal__report-line--danger">
            {BULLET_POINT}{t('library.addPeople.noMatchCountBanner')} {bulkReport.no_match_count}
          </div>
        )}
      </div>

      <div className="bulk-people-resolve-modal__body">
        {bulkReport.multiple_matches && bulkReport.multiple_matches.length > 0 && (
          <section className="bulk-people-resolve-section">
            <div className="bulk-people-resolve-section__header">
              <strong className="bulk-people-resolve-section__title">
                {t(textKey('library.addPeople.adultSelectMatchingPeople', 'library.addPeople.selectMatchingPeople'))}
              </strong>
            </div>
            {bulkReport.multiple_matches.map((row) => {
              const isResolved = resolvedRows[row.line_number] !== undefined;
              return (
                <article key={row.line_number} className="bulk-people-match-row">
                  <div className="bulk-people-match-row__header">
                    <div className="bulk-people-match-row__prompt">
                      <span className="bulk-people-match-row__eyebrow">{t(textKey('library.addPeople.adultMatchInputLabel', 'library.addPeople.matchInputLabel'))}</span>
                      <span className="bulk-people-match-row__name">{row.raw}</span>
                    </div>
                    {isResolved && (
                      <button
                        type="button"
                        className={`bulk-people-match-row__status bulk-people-match-row__status-button${hoveredResolvedRow === row.line_number ? ' is-rematch' : ''}`}
                        onMouseEnter={() => setHoveredResolvedRow(row.line_number)}
                        onMouseLeave={() => setHoveredResolvedRow(null)}
                        onClick={() => {
                          setResolvedRows((prev) => {
                            const next = { ...prev };
                            delete next[row.line_number];
                            if (resolveStateStorageKey) {
                              try {
                                localStorage.setItem(resolveStateStorageKey, JSON.stringify(next));
                              } catch {
                                // Ignore storage failures here.
                              }
                            }
                            return next;
                          });
                        }}
                      >
                        <Check size={14} />
                        {hoveredResolvedRow === row.line_number
                          ? t('library.addPeople.rematch')
                          : t('library.addPeople.importedState')}
                      </button>
                    )}
                  </div>
                  {!isResolved && (
                    <div className="bulk-people-candidate-grid">
                      {row.candidates.map((candidate) => {
                        const isPending = pendingAdds[candidate.id];
                        return (
                          <button
                            key={candidate.id}
                            onClick={async () => {
                              setPendingAdds((prev) => ({ ...prev, [candidate.id]: true }));
                              try {
                                await addPersonMutation.mutateAsync({
                                  tmdb_id: candidate.id,
                                  name: candidate.name,
                                  profile_path: candidate.profile_path,
                                  gender: candidate.gender,
                                  is_adult: candidate.is_adult !== undefined ? candidate.is_adult : isAdult
                                });
                                setResolvedRows((prev) => {
                                  const next = { ...prev, [row.line_number]: candidate.id };
                                  if (resolveStateStorageKey) {
                                    try {
                                      localStorage.setItem(resolveStateStorageKey, JSON.stringify(next));
                                    } catch {
                                      // Ignore storage failures here.
                                    }
                                  }
                                  return next;
                                });
                              } catch (err) {
                                console.error(err);
                              } finally {
                                setPendingAdds((prev) => ({ ...prev, [candidate.id]: false }));
                              }
                            }}
                            disabled={isPending}
                            className="ui-selectable-card ui-selectable-card--default bulk-people-candidate-card"
                          >
                            <div className="bulk-people-candidate-card__avatar">
                              {candidate.profile_path ? (
                                <img
                                  src={resolveProfileUrl(candidate.profile_path)}
                                  alt={candidate.name || ''}
                                  className="bulk-people-candidate-card__avatar-image"
                                />
                              ) : (
                                <div className="bulk-people-candidate-card__avatar-placeholder">{QUESTION_MARK}</div>
                              )}
                            </div>
                            <div className="bulk-people-candidate-card__copy">
                              <span className="bulk-people-candidate-card__meta">
                                {candidate.known_for_department || ''}
                              </span>
                              {candidate.known_for && candidate.known_for.length > 0 && (
                                <span className="bulk-people-candidate-card__known-for">
                                  {candidate.known_for.join(', ')}
                                </span>
                              )}
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  )}
                </article>
              );
            })}
          </section>
        )}

        {bulkReport.no_match && bulkReport.no_match.length > 0 && (
          <div className="bulk-people-resolve-modal__no-match">
            <strong className="bulk-people-resolve-modal__no-match-title">{t(textKey('library.addPeople.adultNoMatchesFoundTitle', 'library.addPeople.noMatchesFoundTitle'))}</strong>
            <div className="bulk-people-resolve-modal__no-match-list">
              {bulkReport.no_match.map((nm) => (
                <Pill key={nm.line_number} variant="danger">
                  {nm.raw}
                </Pill>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
