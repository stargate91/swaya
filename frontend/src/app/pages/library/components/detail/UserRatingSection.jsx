/* eslint-disable react/forbid-dom-props */
import { PenLine } from 'lucide-react';
import Pill from '@/ui/Pill';
import { useMediaDetailContext } from './MediaDetailContext';
import './UserRatingSection.css';


export default function UserRatingSection() {
  const { state, actions, t } = useMediaDetailContext();
  const {
    displayRating,
    verticalBarText
  } = state;

  const {
    handleOpenReviewModal,
    handleMouseMove,
    handleMouseLeave,
    handleClick
  } = actions;

  return (
    <div className="media-detail-page__meta-row">
      <Pill variant="meta-large" className="rating-pill--large">
        <button
          onClick={handleOpenReviewModal}
          className="review-trigger-btn"
          title={t('library.details.writeReview') || 'Write Review'}
        >
          <PenLine size={15} />
        </button>
        <span className="pill-vertical-separator">{verticalBarText}</span>

        <div
          className="rating-segmented-bar"
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
          onMouseUp={handleClick}
          role="slider"
          tabIndex={0}
          aria-label={t('library.details.yourRating') || 'Your Rating'}
          aria-valuemin={0}
          aria-valuemax={10}
          aria-valuenow={displayRating ?? 0}
        >
          {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((val) => {
            let fill = 0;
            if (displayRating >= val) {
              fill = 100;
            } else if (displayRating > val - 1) {
              fill = (displayRating - (val - 1)) * 100;
            }
            return (
              <div key={val} className="rating-segment">
                <div
                  className="rating-segment-fill"
                  style={{ width: `${fill}%` }}
                />
              </div>
            );
          })}
        </div>
        <span className={`user-rating-label ${displayRating !== undefined && displayRating !== null ? 'has-value' : ''}`}>
          {displayRating !== undefined && displayRating !== null
            ? displayRating.toFixed(1)
            : (t('library.details.yourRating') || 'Your Rating')}
        </span>
      </Pill>
    </div>
  );
}
