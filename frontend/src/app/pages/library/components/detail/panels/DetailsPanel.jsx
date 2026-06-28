import { countEpisodesInNumber } from '../../../utils/detailUtils';
import { useMediaDetailContext } from '../MediaDetailContext';
import Pill from '@/ui/Pill';
import { buildTmdbImageUrl, resolveMediaImageUrl, TMDB_IMAGE_SIZES } from '@/lib/imageUrls';
import './PanelsCommon.css';
import './DetailsPanel.css';



export default function DetailsPanel() {
  const { state, t } = useMediaDetailContext();
  const {
    item,
    isMovie
  } = state;

  const isSceneType = item?.type === 'scene';
  const tmdbId = item?.tmdb_id || item?.tv_tmdb_id;
  const imdbId = item?.imdb_id;
  const hasImdb = !isSceneType && item?.rating_imdb != null && Number(item.rating_imdb) > 0;
  const hasTmdb = !isSceneType && item?.rating_tmdb != null && Number(item.rating_tmdb) > 0;
  const hasRotten = !isSceneType && item?.rating_rotten != null && item?.rating_rotten !== '';
  const hasMeta = !isSceneType && item?.rating_meta != null && Number(item.rating_meta) > 0;

  const ratings = [];
  if (hasImdb) {
    ratings.push({
      id: 'imdb',
      logo: '/rating/imdb.png',
      alt: 'IMDb',
      value: `${item.rating_imdb.toFixed(1)}/10`
    });
  }
  if (hasTmdb) {
    ratings.push({
      id: 'tmdb',
      logo: '/rating/tmdb.png',
      alt: 'TMDb',
      value: `${item.rating_tmdb.toFixed(1)}/10`
    });
  }
  if (hasRotten) {
    ratings.push({
      id: 'rotten',
      logo: '/rating/rottan_tomatoes.png',
      alt: 'Rotten Tomatoes',
      value: item.rating_rotten
    });
  }
  if (hasMeta) {
    ratings.push({
      id: 'meta',
      logo: '/rating/metacritic.png',
      alt: 'Metacritic',
      value: `${item.rating_meta}/100`
    });
  }
  
  const hasPorndb = item?.rating_porndb != null && Number(item.rating_porndb) > 0;
  if (hasPorndb) {
    ratings.push({
      id: 'porndb',
      logo: '/rating/theporndb.png',
      alt: 'ThePornDB',
      value: `${item.rating_porndb.toFixed(1)}/10`
    });
  }

  const formatCurrency = (num) => {
    if (num === undefined || num === null || num === 0) return '-';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      maximumFractionDigits: 0
    }).format(num);
  };

  const hasBoxOffice = !!((item.budget && item.budget > 0) || (item.revenue && item.revenue > 0));

  const companies = item.companies || [];
  const networks = item.networks || [];

  const nonSpecialSeasons = !isMovie && Array.isArray(item?.seasons)
    ? item.seasons.filter(s => s.season_number !== 0)
    : [];
  const derivedSeasonCount = nonSpecialSeasons.length;
  const derivedEpisodeCount = nonSpecialSeasons.reduce((acc, s) => {
    if (s.episodes && s.episodes.length > 0) {
      return acc + s.episodes.reduce((sum, ep) => sum + countEpisodesInNumber(ep.episode_number), 0);
    }
    return acc + 0;
  }, 0);
  const seasonCount = Number(item?.number_of_seasons ?? 0) || derivedSeasonCount;
  const episodeCount = Number(item?.number_of_episodes ?? 0) || derivedEpisodeCount;
  const tvStatus = item?.release_status;

  return (
    <div className="details-panel details-panel--custom">
      {(ratings.length > 0) && (
        <div>
            <h4 className="details-panel__ratings-title">
              {t('library.details.ratingsSection') || 'Ratings'}
            </h4>
            <div className="ratings-container">
              {ratings.map((rating, idx) => {
                const isLast = idx === ratings.length - 1;
                const isOddTotal = ratings.length % 2 !== 0;
                const isSpan2 = (isLast && isOddTotal);

                return (
                  <div
                    key={rating.id}
                    className={`rating-card${isSpan2 ? ' rating-card--span-2' : ''}`}
                  >
                    <img src={rating.logo} alt={rating.alt} className="rating-card__logo" />
                    <span className="rating-card__value">
                      {rating.value}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )
      }

      {!isMovie && (
        <div className="details-panel__section">
          <h4 className="details-panel__section-title">
            {t('library.details.tvInfo') || 'Tv Info'}
          </h4>
          <div className="specs-grid">
            <div className="specs-card specs-card--tall">
              <span className="specs-card__label">{t('library.details.seasons') || 'Seasons'}</span>
              <span className="specs-card__value" title={seasonCount}>{seasonCount}</span>
            </div>
            <div className="specs-card specs-card--tall">
              <span className="specs-card__label">{t('library.details.episodes') || 'Episodes'}</span>
              <span className="specs-card__value" title={episodeCount}>{episodeCount}</span>
            </div>
            {tvStatus && (
              <div className="specs-card specs-card--tall specs-card--span-2">
                <span className="specs-card__label">{t('library.details.status') || 'Status'}</span>
                <span className="specs-card__value" title={tvStatus}>{tvStatus}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {hasBoxOffice && (
        <div className="details-panel__section">
          <h4 className="details-panel__section-title">
            {t('library.details.boxOffice') || 'Box Office'}
          </h4>
          <div className="specs-grid">
            {item.budget > 0 && (
              <div className="specs-card">
                <span className="specs-card__label">{t('library.details.budget') || 'Budget'}</span>
                <span className="specs-card__value" title={formatCurrency(item.budget)}>
                  {formatCurrency(item.budget)}
                </span>
              </div>
            )}
            {item.revenue > 0 && (
              <div className="specs-card">
                <span className="specs-card__label">{t('library.details.revenue') || 'Revenue'}</span>
                <span className="specs-card__value" title={formatCurrency(item.revenue)}>
                  {formatCurrency(item.revenue)}
                </span>
              </div>
            )}
            {item.budget > 0 && item.revenue > 0 && (
              <div className="specs-card specs-card--span-2">
                <span className="specs-card__label">{t('library.details.profit') || 'Profit'}</span>
                <span
                  className={`specs-card__value ${(item.revenue - item.budget) >= 0 ? 'specs-card__value--success' : 'specs-card__value--danger'}`}
                  title={formatCurrency(item.revenue - item.budget)}
                >
                  {formatCurrency(item.revenue - item.budget)}
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      {companies.length > 0 && !isSceneType && (
        <div className="details-panel__section">
          <h4 className="details-panel__section-title">
            {item.is_adult ? (t('library.details.studio') || 'Studio') : (t('library.details.productionCompanies') || 'Production Companies')}
          </h4>
          <div className="companies-networks-container">
            {companies.map((it, idx) => {
              const logoUrl = it.logo_path
                ? (it.logo_path.startsWith('http') || it.logo_path.startsWith('/media/') || it.logo_path.startsWith('data/'))
                  ? resolveMediaImageUrl(it.logo_path, 'logo')
                  : buildTmdbImageUrl(it.logo_path, TMDB_IMAGE_SIZES.posterThumb)
                : null;
              return (
                <div
                  key={idx}
                  className="specs-card specs-card--company"
                  title={it.name}
                >
                  {logoUrl && (
                    <img
                      src={logoUrl}
                      alt={it.name}
                      className="specs-card__company-logo"
                    />
                  )}
                  {!logoUrl && (
                    <span className="specs-card__company-text">
                      {it.name}
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {networks.length > 0 && !isSceneType && (
        <div className="details-panel__section">
          <h4 className="details-panel__section-title">
            {item.is_adult ? (t('library.details.network') || 'Network') : (t('library.details.platformsNetworks') || 'Platforms & Networks')}
          </h4>
          <div className="companies-networks-container">
            {networks.map((it, idx) => {
              const logoUrl = it.logo_path
                ? (it.logo_path.startsWith('http') || it.logo_path.startsWith('/media/') || it.logo_path.startsWith('data/'))
                  ? resolveMediaImageUrl(it.logo_path, 'logo')
                  : buildTmdbImageUrl(it.logo_path, TMDB_IMAGE_SIZES.posterThumb)
                : null;
              return (
                <div
                  key={idx}
                  className="specs-card specs-card--company"
                  title={it.name}
                >
                  {logoUrl && (
                    <img
                      src={logoUrl}
                      alt={it.name}
                      className="specs-card__company-logo"
                    />
                  )}
                  {!logoUrl && (
                    <span className="specs-card__company-text">
                      {it.name}
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}





      {Array.isArray(item?.keywords) && item.keywords.filter(Boolean).length > 0 && (
        <div className="details-panel__section">
          <h4 className="details-panel__section-title">
            {t('library.details.keywords') || 'Keywords'}
          </h4>
          <div className="details-panel__keywords-list">
            {item.keywords.filter(Boolean).map((keyword, idx) => (
              <Pill
                key={idx}
                variant="meta"
                className="details-panel__keyword-pill"
              >
                {keyword}
              </Pill>
            ))}

          </div>
        </div>
      )}
    </div>

  );
}
