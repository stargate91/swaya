import { Users } from 'lucide-react';
import { useMediaDetailContext } from '../MediaDetailContext';
import './CastPanel.css';

import { API_BASE } from '@/lib/backend';
import { resolveMediaImageUrl } from '@/lib/imageUrls';

export default function CastPanel() {
  const { state, t, navigate } = useMediaDetailContext();
  const {
    item,
    settings
  } = state;

  const isAdult = item.is_adult;
  const genderPref = settings?.adult_gender_preference; // 'all', 'female', 'male'

  const filterPeople = (list) => {
    if (!list) return [];
    if (!isAdult || !genderPref || genderPref === 'all') return list;
    return list.filter(person => {
      if (genderPref === 'female') return person.gender === 1;
      if (genderPref === 'male') return person.gender === 2;
      return true;
    });
  };

  const filteredDirectors = filterPeople(item.directors);
  const filteredWriters = filterPeople(item.writers);
  const filteredCast = filterPeople(item.cast);
  const resolvePersonAvatarUrl = (path) => resolveMediaImageUrl(path, 'person', API_BASE);

  return (
    <div className="cast-panel">
      {filteredDirectors && filteredDirectors.length > 0 && (
        <div>
          <h4 className="cast-panel__title">
            {t('library.details.directors') || 'Directors / Creators'}
          </h4>
          <div className="cast-panel__list">
            {filteredDirectors.map(director => {
              return (
                // eslint-disable-next-line jsx-a11y/no-static-element-interactions
                <div
                  key={director.id}
                  className="person-card"
                  onClick={() => navigate(`/library/people/${director.id}`, { state: { allowAdult: true } })}
                >
                  {director.profile_path ? (
                    <img
                      src={resolvePersonAvatarUrl(director.profile_path)}
                      alt={director.name}
                      className="person-card__avatar"
                    />
                  ) : (
                    <div className="person-card__avatar-fallback">
                      <Users size={16} />
                    </div>
                  )}
                  <div className="person-card__info">
                    <span className="person-card__name">{director.name}</span>
                    <span className="person-card__role">
                      {t(`library.people.roles.${String(director.job || 'director').toLowerCase()}`, director.job || 'Director')}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {filteredWriters && filteredWriters.length > 0 && (
        <div>
          <h4 className="cast-panel__title">
            {t('library.details.writers') || 'Writers / Creators'}
          </h4>
          <div className="cast-panel__list">
            {filteredWriters.map(writer => {
              return (
                // eslint-disable-next-line jsx-a11y/no-static-element-interactions
                <div
                  key={writer.id}
                  className="person-card"
                  onClick={() => navigate(`/library/people/${writer.id}`, { state: { allowAdult: true } })}
                >
                  {writer.profile_path ? (
                    <img
                      src={resolvePersonAvatarUrl(writer.profile_path)}
                      alt={writer.name}
                      className="person-card__avatar"
                    />
                  ) : (
                    <div className="person-card__avatar-fallback">
                      <Users size={16} />
                    </div>
                  )}
                  <div className="person-card__info">
                    <span className="person-card__name">{writer.name}</span>
                    <span className="person-card__role">
                      {t(`library.people.roles.${String(writer.job || 'writer').toLowerCase()}`, writer.job || 'Writer')}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {filteredCast && filteredCast.length > 0 && (
        <div>
          <h4 className="cast-panel__title">
            {t('library.details.actors') || 'Actors'}
          </h4>
          <div className="cast-panel__list cast-panel__list--actors">
            {filteredCast.map(actor => {
              return (
                // eslint-disable-next-line jsx-a11y/no-static-element-interactions
                <div
                  key={actor.id}
                  className="person-card"
                  onClick={() => navigate(`/library/people/${actor.id}`, { state: { allowAdult: true } })}
                >
                  {actor.profile_path ? (
                    <img
                      src={resolvePersonAvatarUrl(actor.profile_path)}
                      alt={actor.name}
                      className="person-card__avatar person-card__avatar--actor"
                    />
                  ) : (
                    <div className="person-card__avatar-fallback person-card__avatar-fallback--actor">
                      <Users size={18} />
                    </div>
                  )}
                  <div className="person-card__info">
                    <span className="person-card__name">{actor.name}</span>
                    <span className="person-card__role">
                      {actor.character || t('library.people.roles.actor') || 'Actor'}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
