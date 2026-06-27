import { Mars, User, Venus, VenusAndMars, Ruler, Eye, Brush, Gem, Palette, Globe } from 'lucide-react';
import { Briefcase, Calendar, CalendarX2, Check, Layers, MapPin, X } from 'lucide-react';
import { isTvLikeMediaType } from '@/lib/mediaTypes';

export function getGenderLabel(gender, t) {
  if (gender === 1 || gender === '1') {
    return t('library.details.female') || 'Female';
  }
  if (gender === 2 || gender === '2') {
    return t('library.details.male') || 'Male';
  }
  if (gender === 3 || gender === '3') {
    return t('library.details.nonBinary') || 'Non-binary';
  }
  return null;
}

export function getGenderIcon(gender) {
  if (gender === 1 || gender === '1') {
    return Venus;
  }
  if (gender === 2 || gender === '2') {
    return Mars;
  }
  if (gender === 3 || gender === '3') {
    return VenusAndMars;
  }
  return User;
}

export function normalizeCreditType(item) {
  return isTvLikeMediaType(item?.media_type || item?.type) ? 'tv' : 'movie';
}

export function normalizeCreditTitle(item) {
  return String(item?.title || item?.name || '')
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-zA-Z0-9]+/g, ' ')
    .trim()
    .toLowerCase();
}

export function getCreditIdentityCandidates(item) {
  return [
    item?.tmdb_id,
    item?.tv_tmdb_id,
    item?.library_tv_tmdb_id,
    item?.library_item_id,
    item?.id,
  ]
    .filter((value) => value !== null && value !== undefined && value !== '')
    .map((value) => String(value));
}

export function isKnownForMatch(entry, knownForEntry) {
  if (normalizeCreditType(entry) !== normalizeCreditType(knownForEntry)) {
    return false;
  }

  const entryIds = getCreditIdentityCandidates(entry);
  const knownForIds = getCreditIdentityCandidates(knownForEntry);
  if (entryIds.some((id) => knownForIds.includes(id))) {
    return true;
  }

  const entryTitle = normalizeCreditTitle(entry);
  const knownForTitle = normalizeCreditTitle(knownForEntry);
  const entryYear = String(entry?.year || '');
  const knownForYear = String(knownForEntry?.year || '');

  if (!entryTitle || !knownForTitle) {
    return false;
  }

  if (entryTitle === knownForTitle && entryYear === knownForYear) {
    return true;
  }

  return entryTitle === knownForTitle;
}

export function prioritizePersonCredits(items, knownForItems) {
  if (!items?.length) {
    return [];
  }

  const knownForRank = new Map(
    (knownForItems || []).map((entry, index) => {
      const ids = getCreditIdentityCandidates(entry);
      const key = ids[0] || `${normalizeCreditType(entry)}:${normalizeCreditTitle(entry)}:${entry?.year || ''}`;
      return [key, index];
    })
  );

  return [...items]
    .map((entry) => {
      const matchedKnownFor = (knownForItems || []).find((knownForEntry) => isKnownForMatch(entry, knownForEntry));
      const matchIds = matchedKnownFor ? getCreditIdentityCandidates(matchedKnownFor) : [];
      const fallbackKey = `${normalizeCreditType(entry)}:${normalizeCreditTitle(entry)}:${entry?.year || ''}`;
      const rankKey = matchIds[0] || fallbackKey;
      return {
        ...entry,
        is_known_for: Boolean(matchedKnownFor),
        known_for_rank: matchedKnownFor ? (knownForRank.get(rankKey) ?? Number.MAX_SAFE_INTEGER) : Number.MAX_SAFE_INTEGER,
      };
    })
    .sort((a, b) => {
      if (Boolean(a?.is_known_for) !== Boolean(b?.is_known_for)) {
        return a?.is_known_for ? -1 : 1;
      }

      if (a?.is_known_for && b?.is_known_for) {
        return (a?.known_for_rank ?? Number.MAX_SAFE_INTEGER) - (b?.known_for_rank ?? Number.MAX_SAFE_INTEGER);
      }

      if (Boolean(a?.in_library) !== Boolean(b?.in_library)) {
        return a?.in_library ? -1 : 1;
      }

      const yearDiff = (Number(b?.year) || 0) - (Number(a?.year) || 0);
      if (yearDiff !== 0) {
        return yearDiff;
      }

      return String(a?.title || '').localeCompare(String(b?.title || ''));
    });
}

export function getTmdbBackdropScore(item) {
  const rating = Number(item?.rating_tmdb ?? item?.rating ?? 0);
  const voteCount = Number(item?.vote_count ?? 0);
  return (rating * 100) + (Math.log10(Math.max(voteCount, 1)) * 24);
}

export function sortBackdropCredits(items) {
  return [...(items || [])].sort((a, b) => {
    const scoreDiff = getTmdbBackdropScore(b) - getTmdbBackdropScore(a);
    if (scoreDiff !== 0) {
      return scoreDiff;
    }
    const yearDiff = (Number(b?.year) || 0) - (Number(a?.year) || 0);
    if (yearDiff !== 0) {
      return yearDiff;
    }
    return String(a?.title || '').localeCompare(String(b?.title || ''));
  });
}

export function normalizeBackdropKey(path) {
  if (!path) {
    return '';
  }
  const normalized = String(path).trim();
  const parts = normalized.split('/');
  return parts[parts.length - 1] || normalized;
}

export function mergeBackdropCreditPages(pages) {
  const seen = new Set();
  const merged = [];
  (pages || []).forEach((page) => {
    (page?.items || []).forEach((entry) => {
      const key = String(entry?.tmdb_id || entry?.id || `${entry?.title || entry?.name || ''}-${entry?.year || ''}`);
      if (!key || seen.has(key)) {
        return;
      }
      seen.add(key);
      merged.push(entry);
    });
  });
  return merged;
}

export function buildPersonExternalLinks(item, t) {
  if (!item?.id) {
    return [];
  }

  const externalIds = item.external_ids || {};
  const links = [];
  const seenUrls = new Set();

  const addLink = (linkObj) => {
    if (!linkObj.href) return;
    try {
      const normalized = new URL(linkObj.href).href.replace(/\/$/, '').toLowerCase();
      if (seenUrls.has(normalized)) return;
      seenUrls.add(normalized);
      links.push(linkObj);
    } catch {
      if (seenUrls.has(linkObj.href.toLowerCase())) return;
      seenUrls.add(linkObj.href.toLowerCase());
      links.push(linkObj);
    }
  };

  const detectSiteName = (url, site) => {
    if (site && site !== 'Link' && site !== 'Website' && site !== 'Other') {
      return site;
    }
    try {
      const hostname = new URL(url).hostname.replace('www.', '').toLowerCase();
      if (hostname.includes('onlyfans.com')) return 'OnlyFans';
      if (hostname.includes('fansly.com')) return 'Fansly';
      if (hostname.includes('twitter.com') || hostname.includes('x.com')) return 'X (Twitter)';
      if (hostname.includes('instagram.com')) return 'Instagram';
      if (hostname.includes('tiktok.com')) return 'TikTok';
      if (hostname.includes('pornhub.com')) return 'Pornhub';
      if (hostname.includes('stashdb.org')) return 'StashDB';
      if (hostname.includes('theporndb.net') || hostname.includes('theporndb.org')) return 'ThePornDB';
      if (hostname.includes('fansdb.cc') || hostname.includes('fansdb.xyz')) return 'FansDB';
      if (hostname.includes('manyvids.com')) return 'ManyVids';
      if (hostname.includes('fancentro.com')) return 'Fancentro';
      if (hostname.includes('babepedia.com')) return 'Babepedia';
      if (hostname.includes('freeones.com')) return 'FreeOnes';
      if (hostname.includes('iafd.com')) return 'IAFD';
      if (hostname.includes('data18.com')) return 'Data18';
      if (hostname.includes('wikidata.org')) return 'Wikidata';
      if (hostname.includes('imdb.com')) return 'IMDb';
      if (hostname.includes('themoviedb.org')) return 'TMDb';
      if (hostname.includes('linktr.ee')) return 'Linktree';
      if (hostname.includes('thenude.com')) return 'theNude';
      if (hostname.includes('eurobabeindex.com')) return 'EuroBabeIndex';
      if (hostname.includes('adultfilmdatabase.com')) return 'AFDB';
      if (hostname.includes('facebook.com')) return 'Facebook';
      if (hostname.includes('youtube.com') || hostname.includes('youtu.be')) return 'YouTube';

      const parts = hostname.split('.');
      if (parts.length > 1) {
        const domain = parts[parts.length - 2];
        return domain.charAt(0).toUpperCase() + domain.slice(1);
      }
      return hostname;
    } catch {
      return site || 'Link';
    }
  };

  const tmdbId = externalIds.tmdb_id || (!item.is_adult && Number(item.id) < 100000000 ? item.id : null);
  if (tmdbId) {
    addLink({
      key: 'tmdb',
      label: t('library.details.tmdb') || 'TMDb',
      href: `https://www.themoviedb.org/person/${tmdbId}`,
      iconSrc: '/links/tmdb.png',
      brandColor: 'var(--color-brand-tmdb)',
    });
  }

  if (item.homepage) {
    addLink({
      key: 'website',
      label: t('library.details.website') || 'Website',
      href: item.homepage,
      iconSrc: '/links/homepage.png',
      brandColor: 'var(--color-text-primary)',
    });
  }

  if (externalIds.imdb_id) {
    addLink({
      key: 'imdb',
      label: t('library.details.imdb') || 'IMDb',
      href: `https://www.imdb.com/name/${externalIds.imdb_id}`,
      iconSrc: '/links/imdb.png',
      brandColor: 'var(--color-brand-imdb)',
    });
  }

  const instagramId = externalIds.instagram_id || externalIds.instagram;
  if (instagramId) {
    addLink({
      key: 'instagram',
      label: 'Instagram',
      href: String(instagramId).startsWith('http') ? instagramId : `https://www.instagram.com/${instagramId}`,
      iconSrc: '/links/instagram.ico',
      brandColor: '#f77737',
    });
  }

  const facebookId = externalIds.facebook_id || externalIds.facebook;
  if (facebookId) {
    addLink({
      key: 'facebook',
      label: 'Facebook',
      href: String(facebookId).startsWith('http') ? facebookId : `https://www.facebook.com/${facebookId}`,
      iconSrc: '/links/facebook.ico',
      brandColor: '#1877f2',
    });
  }

  const twitterId = externalIds.twitter_id || externalIds.twitter || externalIds.x || externalIds.x_id;
  if (twitterId) {
    addLink({
      key: 'x',
      label: 'X',
      href: String(twitterId).startsWith('http') ? twitterId : `https://x.com/${twitterId}`,
      iconSrc: '/links/twitter.png',
      brandColor: '#ffffff',
    });
  }

  const youtubeId = externalIds.youtube_id || externalIds.youtube;
  if (youtubeId) {
    addLink({
      key: 'youtube',
      label: 'YouTube',
      href: String(youtubeId).startsWith('http') ? youtubeId : `https://www.youtube.com/${String(youtubeId).startsWith('@') ? youtubeId : `@${youtubeId}`}`,
      iconSrc: '/links/youtube.ico',
      brandColor: '#ff0033',
    });
  }

  const tiktokId = externalIds.tiktok_id || externalIds.tiktok;
  if (tiktokId) {
    addLink({
      key: 'tiktok',
      label: 'TikTok',
      href: String(tiktokId).startsWith('http') ? tiktokId : `https://www.tiktok.com/@${String(tiktokId).replace(/^@/, '')}`,
      iconSrc: '/links/tiktok.png',
      brandColor: '#25f4ee',
    });
  }

  if (externalIds.threads_id) {
    addLink({
      key: 'threads',
      label: 'Threads',
      href: `https://www.threads.net/@${externalIds.threads_id.replace(/^@/, '')}`,
      iconSrc: '/links/threads.png',
      brandColor: '#000000',
    });
  }

  if (externalIds.twitch_id) {
    addLink({
      key: 'twitch',
      label: 'Twitch',
      href: `https://www.twitch.tv/${externalIds.twitch_id}`,
      iconSrc: '/links/twitch.jpg',
      brandColor: '#9146ff',
    });
  }

  if (externalIds.kick_id) {
    addLink({
      key: 'kick',
      label: 'Kick',
      href: `https://kick.com/${externalIds.kick_id}`,
      iconSrc: '/links/kick.ico',
      brandColor: '#53fc18',
    });
  }

  if (externalIds.bluesky_id) {
    addLink({
      key: 'bluesky',
      label: 'BlueSky',
      href: `https://bsky.app/profile/${externalIds.bluesky_id}`,
      iconSrc: '/links/bluesky.png',
      brandColor: '#0285FF',
    });
  }

  if (externalIds.onlyfans_id) {
    addLink({
      key: 'onlyfans',
      label: 'OnlyFans',
      href: `https://onlyfans.com/${externalIds.onlyfans_id}`,
      iconSrc: '/links/onylfans.ico',
      brandColor: '#00aff0',
    });
  }

  if (externalIds.fansly_id) {
    addLink({
      key: 'fansly',
      label: 'Fansly',
      href: `https://fansly.com/${externalIds.fansly_id}`,
      iconSrc: '/links/fansly.png',
      brandColor: '#5b93fa',
    });
  }

  if (externalIds.patreon_id) {
    addLink({
      key: 'patreon',
      label: 'Patreon',
      href: `https://www.patreon.com/${externalIds.patreon_id}`,
      iconSrc: '/links/patreon.ico',
      brandColor: '#ff424d',
    });
  }

  if (externalIds.loyalfans_id) {
    addLink({
      key: 'loyalfans',
      label: 'LoyalFans',
      href: `https://www.loyalfans.com/${externalIds.loyalfans_id}`,
      iconSrc: '/links/loyalfans.ico',
      brandColor: '#eb1b4b',
    });
  }

  if (externalIds.manyvids_id) {
    addLink({
      key: 'manyvids',
      label: 'ManyVids',
      href: `https://www.manyvids.com/${externalIds.manyvids_id}`,
      iconSrc: '/links/manyvids.ico',
      brandColor: '#ff5c00',
    });
  }

  if (externalIds.linktree_id) {
    addLink({
      key: 'linktree',
      label: 'Linktree',
      href: `https://linktr.ee/${externalIds.linktree_id}`,
      iconSrc: '/links/linktree.png',
      brandColor: '#39e09b',
    });
  }

  if (externalIds.pornhub_id) {
    addLink({
      key: 'pornhub',
      label: 'Pornhub',
      href: `https://www.pornhub.com/${externalIds.pornhub_id}`,
      iconSrc: '/links/pornhub.ico',
      brandColor: '#ff9900',
    });
  }

  if (externalIds.clips4sale_id) {
    addLink({
      key: 'clips4sale',
      label: 'Clips4Sale',
      href: `https://www.clips4sale.com/${externalIds.clips4sale_id}`,
      iconSrc: '/links/clip4sale.ico',
      brandColor: '#ff0000',
    });
  }

  if (externalIds.allmylinks_id) {
    addLink({
      key: 'allmylinks',
      label: 'AllMyLinks',
      href: `https://allmylinks.com/${externalIds.allmylinks_id}`,
      iconSrc: '/links/allmylinks.ico',
      brandColor: '#00c2ff',
    });
  }

  if (externalIds.beacons_id) {
    addLink({
      key: 'beacons',
      label: 'Beacons',
      href: `https://beacons.ai/${externalIds.beacons_id}`,
      iconSrc: '/links/beacons.png',
      brandColor: '#8A2BE2',
    });
  }

  if (externalIds.iafd_id) {
    addLink({
      key: 'iafd',
      label: 'IAFD',
      href: `https://www.iafd.com/person.rme/${externalIds.iafd_id}`,
      iconSrc: '/links/iafd.ico',
      brandColor: '#1d2a44',
    });
  }

  if (externalIds.babepedia_id) {
    addLink({
      key: 'babepedia',
      label: 'Babepedia',
      href: `https://www.babepedia.com/babe/${externalIds.babepedia_id}`,
      iconSrc: '/links/babepedia.ico',
      brandColor: '#ff0066',
    });
  }

  if (externalIds.freeones_id) {
    addLink({
      key: 'freeones',
      label: 'FreeOnes',
      href: `https://www.freeones.com/${externalIds.freeones_id}`,
      iconSrc: '/links/freeones.png',
      brandColor: '#0066cc',
    });
  }

  if (externalIds.data18_id) {
    addLink({
      key: 'data18',
      label: 'DATA18',
      href: `https://www.data18.com/star/${externalIds.data18_id}`,
      iconSrc: '/links/data18.ico',
      brandColor: '#f25b29',
    });
  }

  // Adult Sources specific links
  if (externalIds.stashdb_id) {
    addLink({
      key: 'stashdb',
      label: 'StashDB',
      href: `https://stashdb.org/performers/${externalIds.stashdb_id}`,
      iconSrc: '/links/stashdb.png',
      brandColor: '#081c24',
    });
  }

  if (externalIds.fansdb_id) {
    addLink({
      key: 'fansdb',
      label: 'FansDB',
      href: `https://fansdb.cc/performers/${externalIds.fansdb_id}`,
      iconSrc: '/links/fansdb.webp',
      brandColor: '#00aff0',
    });
  }

  if (externalIds.theporndb_id) {
    addLink({
      key: 'theporndb',
      label: 'THEPornDB',
      href: `https://theporndb.net/performers/${externalIds.theporndb_id}`,
      iconSrc: '/links/theporndb.png',
      brandColor: '#ff0055',
    });
  }

  const getIconForUrl = (url) => {
    try {
      const hostname = new URL(url).hostname.replace('www.', '').toLowerCase();
      if (hostname.includes('twitter.com') || hostname.includes('x.com')) return '/links/x.svg';
      if (hostname.includes('instagram.com')) return '/links/instagram.ico';
      if (hostname.includes('tiktok.com')) return '/links/tiktok.png';
      if (hostname.includes('wikidata.org')) return '/links/wikidata.svg';
      if (hostname.includes('facebook.com')) return '/links/facebook.ico';
      if (hostname.includes('youtube.com') || hostname.includes('youtu.be')) return '/links/youtube.ico';
      if (hostname.includes('onlyfans.com')) return '/links/onylfans.ico';
      if (hostname.includes('fansly.com')) return '/links/fansly.png';
      if (hostname.includes('patreon.com')) return '/links/patreon.ico';
      if (hostname.includes('pornhub.com')) return '/links/pornhub.ico';
      if (hostname.includes('manyvids.com')) return '/links/manyvids.ico';
      if (hostname.includes('linktr.ee')) return '/links/linktree.png';
      if (hostname.includes('stashdb.org')) return '/links/stashdb.png';
      if (hostname.includes('theporndb.net') || hostname.includes('theporndb.org')) return '/links/theporndb.png';
      if (hostname.includes('fansdb.cc') || hostname.includes('fansdb.xyz')) return '/links/fansdb.webp';
      if (hostname.includes('threads.net')) return '/links/threads.png';
      if (hostname.includes('twitch.tv')) return '/links/twitch.jpg';
      if (hostname.includes('kick.com')) return '/links/kick.ico';
      if (hostname.includes('bluesky.app')) return '/links/bluesky.png';
      if (hostname.includes('clips4sale.com')) return '/links/clip4sale.ico';
      if (hostname.includes('allmylinks.com')) return '/links/allmylinks.ico';
      if (hostname.includes('beacons.ai')) return '/links/beacons.png';
      if (hostname.includes('iafd.com')) return '/links/iafd.ico';
      if (hostname.includes('babepedia.com')) return '/links/babepedia.ico';
      if (hostname.includes('freeones.com')) return '/links/freeones.png';
      if (hostname.includes('data18.com')) return '/links/data18.ico';
    } catch {
      /* ignore invalid URL */
    }
    return '/links/website.svg';
  };

  // Dynamic performer links fetched from adult GraphQL
  if (Array.isArray(externalIds.urls)) {
    externalIds.urls.forEach((u, i) => {
      if (u && u.url) {
        addLink({
          key: `extra-${i}`,
          label: detectSiteName(u.url, u.site),
          href: u.url,
          iconSrc: getIconForUrl(u.url),
          brandColor: 'var(--color-text-primary)',
        });
      }
    });
  }

  return links;
}


export function buildEntityMetaPills({ isPeople, item, t }) {
  if (!isPeople) {
    return [
      item?.total_count !== undefined
        ? {
          key: 'total-count',
          content: (
            <span className="entity-detail-page__meta-pill-content">
              <Layers size={14} />
              <span>
                {t('library.details.totalCount', {
                  count: item.total_count,
                  defaultValue: `${item.total_count} total`,
                })}
              </span>
            </span>
          ),
        }
        : null,
      item?.owned_count !== undefined
        ? {
          key: 'owned-count',
          content: (
            <span className="entity-detail-page__meta-pill-content">
              {Number(item.owned_count) === 0 ? <X size={14} /> : <Check size={14} />}
              <span>
                {t('library.details.inLibraryCount', {
                  count: item.owned_count,
                  defaultValue: `${item.owned_count} in library`,
                })}
              </span>
            </span>
          ),
        }
        : null,
    ].filter(Boolean);
  }


  return [
    (() => {
      const GenderIcon = getGenderIcon(item?.gender);
      const genderLabel = getGenderLabel(item?.gender, t);
      if (!genderLabel) {
        return null;
      }

      return {
        key: 'gender',
        content: (
          <span className="entity-detail-page__meta-pill-content">
            <GenderIcon size={14} />
            <span>{genderLabel}</span>
          </span>
        ),
      };
    })(),
    item?.known_for_department ? {
      key: 'department',
      content: (
        <span className="entity-detail-page__meta-pill-content">
          <Briefcase size={14} />
          <span>{item.known_for_department}</span>
        </span>
      ),
    } : null,
    item?.birthday ? {
      key: 'birthday',
      content: (
        <span className="entity-detail-page__meta-pill-content">
          <Calendar size={14} />
          <span>{item.birthday}</span>
        </span>
      ),
    } : null,
    item?.deathday ? {
      key: 'deathday',
      content: (
        <span className="entity-detail-page__meta-pill-content">
          <CalendarX2 size={14} />
          <span>{item.deathday}</span>
        </span>
      ),
    } : null,
    item?.place_of_birth ? {
      key: 'place-of-birth',
      content: (
        <span className="entity-detail-page__meta-pill-content">
          <MapPin size={14} />
          <span>{item.place_of_birth}</span>
        </span>
      ),
    } : null,
  ].filter(Boolean);
}

const toTitleCase = (str) => {
  if (!str) return '';
  return str
    .toLowerCase()
    .split(/[\s_-]+/)
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
};

const formatListAttribute = (list) => {
  if (!list) return null;
  if (Array.isArray(list)) {
    if (list.length === 0) return null;
    const locations = list.map(item => item.location || item.description).filter(Boolean);
    if (locations.length === 0) return 'Yes';
    return toTitleCase(locations.join(', '));
  }
  if (typeof list === 'string') {
    const formatted = toTitleCase(list);
    if (formatted === 'No Piercings' || formatted === 'No Tattoos') return 'No';
    return formatted;
  }
  return null;
};

export function buildEntityExtraMetaPills({ isPeople, item, t }) {
  if (!isPeople || !item) return [];

  const externalIds = item.external_ids || {};
  const attrs = externalIds.attributes || {};

  const tattooText = formatListAttribute(attrs.tattoos);
  const piercingText = formatListAttribute(attrs.piercings);

  const COLON_SPACE = ': ';

  // For tattoos
  let tattooPillText = null;
  let tattooTooltip = null;
  if (tattooText) {
    if (Array.isArray(attrs.tattoos)) {
      tattooPillText = `${t('library.details.tattoos') || 'Tattoos'}${COLON_SPACE}${attrs.tattoos.length}`;
      tattooTooltip = tattooText;
    } else if (tattooText.length <= 16) {
      tattooPillText = `${t('library.details.tattoos') || 'Tattoos'}${COLON_SPACE}${tattooText}`;
    } else {
      tattooPillText = `${t('library.details.tattoos') || 'Tattoos'}${COLON_SPACE}Yes`;
      tattooTooltip = tattooText;
    }
  }

  // For piercings
  let piercingPillText = null;
  let piercingTooltip = null;
  if (piercingText) {
    if (Array.isArray(attrs.piercings)) {
      piercingPillText = `${t('library.details.piercings') || 'Piercings'}${COLON_SPACE}${attrs.piercings.length}`;
      piercingTooltip = piercingText;
    } else if (piercingText.length <= 16) {
      piercingPillText = `${t('library.details.piercings') || 'Piercings'}${COLON_SPACE}${piercingText}`;
    } else {
      piercingPillText = `${t('library.details.piercings') || 'Piercings'}${COLON_SPACE}Yes`;
      piercingTooltip = piercingText;
    }
  }

  const CM_SUFFIX = ' cm';

  return [
    attrs.height ? {
      key: 'height',
      content: (
        <span className="entity-detail-page__meta-pill-content">
          <Ruler size={14} />
          <span>{attrs.height}{CM_SUFFIX}</span>
        </span>
      ),
    } : null,
    attrs.measurements ? {
      key: 'measurements',
      content: (
        <span className="entity-detail-page__meta-pill-content">
          <Ruler size={14} />
          <span>{attrs.measurements}</span>
        </span>
      ),
    } : null,
    attrs.ethnicity ? {
      key: 'ethnicity',
      content: (
        <span className="entity-detail-page__meta-pill-content">
          <Globe size={14} />
          <span>{toTitleCase(attrs.ethnicity)}</span>
        </span>
      ),
    } : null,
    attrs.eye_color ? {
      key: 'eye-color',
      content: (
        <span className="entity-detail-page__meta-pill-content">
          <Eye size={14} />
          <span>{toTitleCase(attrs.eye_color)}</span>
        </span>
      ),
    } : null,
    attrs.hair_color ? {
      key: 'hair-color',
      content: (
        <span className="entity-detail-page__meta-pill-content">
          <Palette size={14} />
          <span>{toTitleCase(attrs.hair_color)}</span>
        </span>
      ),
    } : null,
    tattooPillText ? {
      key: 'tattoos',
      tooltip: tattooTooltip,
      content: (
        <span className="entity-detail-page__meta-pill-content">
          <Brush size={14} />
          <span>{tattooPillText}</span>
        </span>
      ),
    } : null,
    piercingPillText ? {
      key: 'piercings',
      tooltip: piercingTooltip,
      content: (
        <span className="entity-detail-page__meta-pill-content">
          <Gem size={14} />
          <span>{piercingPillText}</span>
        </span>
      ),
    } : null,
  ].filter(Boolean);
}

export function enrichKnownForItems(knownForItems, movies, tv) {
  if (!knownForItems?.length) {
    return [];
  }

  const movieRatings = new Map(
    (movies || [])
      .filter((entry) => entry?.id != null)
      .map((entry) => [String(entry.id), entry.rating_imdb])
  );

  const tvRatings = new Map();
  for (const entry of tv || []) {
    const rating = entry?.rating_imdb;
    const keys = [entry?.tv_tmdb_id, entry?.tmdb_id, entry?.id];
    for (const key of keys) {
      if (key != null && !tvRatings.has(String(key)) && rating != null) {
        tvRatings.set(String(key), rating);
      }
    }
  }

  return knownForItems.map((entry) => {
    const isTv = isTvLikeMediaType(entry.media_type || entry.type);
    const lookupKeys = isTv
      ? [entry.tv_tmdb_id, entry.library_tv_tmdb_id, entry.tmdb_id, entry.id]
      : [entry.library_item_id, entry.tmdb_id, entry.id];

    const sourceMap = isTv ? tvRatings : movieRatings;
    const fallbackImdb = lookupKeys
      .map((key) => (key != null ? sourceMap.get(String(key)) : null))
      .find((value) => value != null);

    return {
      ...entry,
      rating_imdb: entry.rating_imdb ?? fallbackImdb ?? null,
    };
  });
}
