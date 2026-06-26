import { memo, useState, useEffect } from 'react';
import MediaCard from './MediaCard';
import Pill from './Pill';
import IconButton from './IconButton';
import { Star, Check } from 'lucide-react';
import './PosterCard.css';

const PosterCard = memo(function PosterCard({
  as: Component,
  className = '',
  variant = 'default',
  imageUrl,
  backgroundColor,
  icon: IconComponent,
  placeholderText,
  title,
  subtitle,
  badge,
  topRightBadge,
  topRightAction,
  isWatched = false,
  overlay,
  playOverlay,
  ratingImdb,
  ratingTmdb,
  ratingPorndb,
  onClick,
  disabled = false,
  active = false,
  style,
  customStyle,
  children,
  ...props
}) {
  const isInteractive = !!onClick;
  const DefaultComponent = Component || (isInteractive ? 'button' : 'div');
  const isOverlayTitle = variant === 'overlay-title';

  const [imageError, setImageError] = useState(false);

  useEffect(() => {
    setImageError(false);
  }, [imageUrl]);

  const cardClassName = `ui-poster-card ${isOverlayTitle ? 'ui-poster-card--overlay-title' : ''} ${active ? 'is-active' : ''} ${className}`.trim();

  return (
    /* eslint-disable-next-line react/forbid-dom-props */
    <div className={cardClassName} style={customStyle || style}>
      <div className="ui-poster-card__media-shell">
        <DefaultComponent
          type={DefaultComponent === 'button' ? 'button' : undefined}
          className="ui-poster-card__image-wrapper"
          onClick={onClick}
          disabled={disabled || undefined}
          {...props}
        >
          <MediaCard className="ui-poster-card__media">
            {imageUrl && !imageError ? (
              <img
                src={imageUrl}
                alt=""
                className="ui-poster-card__image"
                onError={() => setImageError(true)}
              />
            ) : (
              <div
                className="ui-poster-card__placeholder"
                /* eslint-disable-next-line react/forbid-dom-props */
                style={backgroundColor ? { background: backgroundColor } : undefined}
              >
                {IconComponent && <IconComponent size={32} className="ui-poster-card__placeholder-icon" />}
                {placeholderText && <span className="ui-poster-card__placeholder-text">{placeholderText}</span>}
              </div>
            )}
            {overlay}
            {badge}
            {topRightBadge}
            {isWatched && (
              <div className="ui-poster-card__watched-badge">
                <Check size={14} strokeWidth={3} />
              </div>
            )}
            {isOverlayTitle && title ? (
              <div className="ui-poster-card__title-overlay">
                <div className="ui-poster-card__title-overlay-gradient" />
                <div className="ui-poster-card__title-overlay-label" title={title}>{title}</div>
              </div>
            ) : null}
            {children}
          </MediaCard>
        </DefaultComponent>
        {topRightAction}
        {playOverlay ? (
          <IconButton
            variant="play-overlay"
            onClick={playOverlay.onClick}
            title={playOverlay.title}
            label={playOverlay.label}
            disabled={playOverlay.disabled}
          >
            {playOverlay.icon}
          </IconButton>
        ) : null}
      </div>

      {!isOverlayTitle && (title || subtitle || ratingImdb || ratingTmdb || ratingPorndb) && (
        <div className="ui-poster-card__details">
          {title && <div className="ui-poster-card__title" title={title}>{title}</div>}
          {(subtitle || ratingImdb || ratingTmdb || ratingPorndb) && (
            <div className="ui-poster-card__subtitle-row">
              {subtitle && <div className="ui-poster-card__subtitle">{subtitle}</div>}
              {(() => {
                const hasImdb = ratingImdb !== undefined && ratingImdb !== null && ratingImdb !== '';
                const hasTmdb = ratingTmdb !== undefined && ratingTmdb !== null && ratingTmdb !== '';
                const hasPorndb = ratingPorndb !== undefined && ratingPorndb !== null && ratingPorndb !== '';
                if (hasImdb) {
                  const val = parseFloat(ratingImdb);
                  return (
                    <Pill variant="imdb">
                      <Star size={10} fill="currentColor" strokeWidth={1.8} />
                      {isNaN(val) ? ratingImdb : val.toFixed(1)}
                    </Pill>
                  );
                } else if (hasTmdb) {
                  const val = parseFloat(ratingTmdb);
                  return (
                    <Pill variant="tmdb">
                      <Star size={10} fill="currentColor" strokeWidth={1.8} />
                      {isNaN(val) ? ratingTmdb : val.toFixed(1)}
                    </Pill>
                  );
                } else if (hasPorndb) {
                  const val = parseFloat(ratingPorndb);
                  return (
                    <Pill variant="porndb">
                      <Star size={10} fill="currentColor" strokeWidth={1.8} />
                      {isNaN(val) ? ratingPorndb : val.toFixed(1)}
                    </Pill>
                  );
                }
                return null;
              })()}
            </div>
          )}
        </div>
      )}
    </div>
  );
});

export default PosterCard;
