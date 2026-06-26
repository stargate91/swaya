import { useState, useEffect } from 'react';
import { Check } from 'lucide-react';
import './BackdropCard.css';

export default function BackdropCard({
  imageUrl,
  alt = 'Backdrop image',
  isSelected = false,
  isPending = false,
  infoLeft,
  infoRight,
  onClick,
  disabled,
  className = '',
  children,
  ...props
}) {
  const cardClass = [
    'ui-backdrop-card',
    isSelected && 'ui-backdrop-card--selected',
    (isPending || disabled) && 'ui-backdrop-card--disabled',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  const [imageError, setImageError] = useState(false);

  useEffect(() => {
    setImageError(false);
  }, [imageUrl]);

  return (
    <button
      type="button"
      className={cardClass}
      onClick={onClick}
      disabled={isPending || disabled}
      {...props}
    >
      {imageUrl && !imageError ? (
        <img
          src={imageUrl}
          alt={alt}
          className="ui-backdrop-card__img"
          loading="lazy"
          decoding="async"
          draggable="false"
          onError={() => setImageError(true)}
        />
      ) : (
        <div className="ui-backdrop-card__placeholder">
          {alt || 'No Image'}
        </div>
      )}
      {isPending && (
        <div className="ui-backdrop-card__spinner-overlay">
          <div className="ui-backdrop-card__spinner" />
        </div>
      )}
      {isSelected && !isPending && (
        <div className="ui-backdrop-card__selected-overlay">
          <Check size={18} />
        </div>
      )}
      {(infoLeft || infoRight) && (
        <div className="ui-backdrop-card__info-overlay">
          {infoLeft && <span>{infoLeft}</span>}
          {infoRight && <span>{infoRight}</span>}
        </div>
      )}
      {children}
    </button>
  );
}
