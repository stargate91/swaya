/* eslint-disable react/forbid-dom-props, jsx-a11y/no-static-element-interactions */
import { useState, useRef, useEffect } from 'react';
import { Star, Heart, Edit3, Search, X } from 'lucide-react';
import Page from '@/ui/Page';
import Table from '@/ui/Table';
import { Tabs } from '@/ui/Tabs';
import PaginationBar from '@/ui/PaginationBar';
import Input from '@/ui/Input';
import Button from '@/ui/Button';
import Spinner from '@/ui/Spinner';
import { useTranslation } from '@/providers/LanguageContext';
import { useRatingsPageState } from './useRatingsPageState';
import './RatingsPage.css';

// Compact Star Rating component
function StarRating({ value, onChange }) {
  const [hoveredValue, setHoveredValue] = useState(null);
  const stars = Array.from({ length: 10 }, (_, i) => i + 1);

  const displayValue = hoveredValue !== null ? hoveredValue : (value || 0);

  return (
    <div className="inline-rating-stars" onMouseLeave={() => setHoveredValue(null)}>
      {stars.map((star) => {
        const isFilled = star <= displayValue;
        const isHovered = hoveredValue !== null && star <= hoveredValue;

        return (
          <Star
            key={star}
            size={14}
            className={`inline-rating-star ${isFilled ? 'is-filled' : ''} ${isHovered ? 'is-hovered' : ''}`}
            onClick={(e) => {
              e.stopPropagation();
              const nextVal = value === star ? null : star;
              onChange(nextVal);
            }}
            onMouseEnter={() => setHoveredValue(star)}
          />
        );
      })}
      {displayValue > 0 && (
        <span className="inline-rating-value">
          {displayValue}
        </span>
      )}
    </div>
  );
}

export default function RatingsPage() {
  const { t } = useTranslation();
  const state = useRatingsPageState();

  // Review Drawer state
  const [editingItem, setEditingItem] = useState(null);
  const [reviewText, setReviewText] = useState('');
  const drawerRef = useRef(null);

  const handleOpenReviewDrawer = (e, item) => {
    e.stopPropagation();
    setEditingItem(item);
    setReviewText(item.user_comment || '');
  };

  const handleSaveReview = async () => {
    if (!editingItem) return;
    await state.handleSaveComment(editingItem, reviewText);
    setEditingItem(null);
  };

  // Close drawer on ESC
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') setEditingItem(null);
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Main Tabs configuration
  const mainTabs = [
    { value: 'unrated', label: t('ratings.tabs.unrated', { defaultValue: 'To Be Rated' }) },
    { value: 'rated', label: t('ratings.tabs.rated', { defaultValue: 'Rated & Reviewed' }) },
    { value: 'analytics', label: t('ratings.tabs.analytics', { defaultValue: 'Analytics' }) },
  ];

  // Media Type Filter configuration
  const subTabs = [
    { value: 'movies', label: t('ratings.subtabs.movies', { defaultValue: 'Movies' }) },
    { value: 'series', label: t('ratings.subtabs.series', { defaultValue: 'Series' }) },
    { value: 'scenes', label: t('ratings.subtabs.scenes', { defaultValue: 'Scenes' }) },
    { value: 'people', label: t('ratings.subtabs.people', { defaultValue: 'People' }) },
  ];

  // Define table columns dynamically based on state
  const columns = [
    {
      key: 'name',
      label: t('ratings.table.name', { defaultValue: 'Name' }),
      render: (val, row) => (
        <span className="ratings-row-name">
          {row.name || row.title || row.displayTitle}
        </span>
      ),
    },
    {
      key: 'rating',
      label: t('ratings.table.rating', { defaultValue: 'My Rating' }),
      width: '180px',
      render: (val, row) => (
        <StarRating
          value={row.user_rating}
          onChange={(newVal) => state.handleRateItem(row, newVal)}
        />
      ),
    },
    ...(state.mediaType === 'people'
      ? [
          {
            key: 'favorite',
            label: t('ratings.table.favorite', { defaultValue: 'Favorite' }),
            width: '80px',
            align: 'center',
            render: (val, row) => (
              <button
                type="button"
                className={`fav-heart-btn ${row.is_favorite ? 'is-favorite' : ''}`}
                onClick={(e) => {
                  e.stopPropagation();
                  state.handleToggleFavorite(row);
                }}
              >
                <Heart size={16} fill={row.is_favorite ? 'currentColor' : 'none'} />
              </button>
            ),
          },
        ]
      : []),
    {
      key: 'comment',
      label: t('ratings.table.comment', { defaultValue: 'Comment / Review' }),
      render: (val, row) => {
        const hasComment = row.user_comment && String(row.user_comment).trim();
        return (
          <div className="review-preview-cell">
            {hasComment ? (
              <span className="review-preview-text">{row.user_comment}</span>
            ) : (
              <span className="review-preview-empty">
                {t('ratings.dialog.placeholder', { defaultValue: 'Write a review...' })}
              </span>
            )}
            <Button
              variant="secondary-neutral"
              size="xs"
              className="review-edit-btn"
              onClick={(e) => handleOpenReviewDrawer(e, row)}
            >
              <Edit3 size={12} />
              {hasComment ? t('common.edit') || 'Edit' : t('common.add') || 'Add'}
            </Button>
          </div>
        );
      },
    },
  ];

  const handleKeyDownBackdrop = (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      setEditingItem(null);
    }
  };

  return (
    <Page
      eyebrow={t('ratings.title', { defaultValue: 'Ratings & Reviews' })}
      title={t('ratings.title', { defaultValue: 'Ratings & Reviews' })}
      description={t('ratings.description', { defaultValue: 'Manage your ratings, comments, and favorites.' })}
      className="ratings-page"
    >
      <div className="ratings-main">
        {/* Navigation & Controls panel */}
        <div className="ratings-panel">
          <div className="ratings-panel__row">
            <Tabs
              tabs={mainTabs}
              value={state.activeTab}
              onChange={state.setActiveTab}
            />

            {state.activeTab !== 'analytics' && (
              <div className="ratings-search">
                <Search size={14} className="ratings-search__icon" />
                <Input
                  type="text"
                  placeholder={t('common.search') || 'Search...'}
                  value={state.searchQuery}
                  onChange={(e) => state.setSearchQuery(e.target.value)}
                />
              </div>
            )}
          </div>

          {state.activeTab !== 'analytics' && (
            <div className="ratings-panel__row">
              <Tabs
                tabs={subTabs}
                value={state.mediaType}
                onChange={state.setMediaType}
                variant="sub"
              />
            </div>
          )}
        </div>

        {/* Content Tabs */}
        {state.activeTab === 'analytics' ? (
          /* Analytics Dashboard tab */
          <div className="analytics-dashboard">
            <div className="analytics-card">
              <span className="analytics-card__title">
                {t('ratings.stats.average', { defaultValue: 'Average Rating' })}
              </span>
              <div className="analytics-card-row">
                <span className="analytics-card__value">{state.analytics.average}</span>
                <Star size={24} className="is-filled analytics-star-icon" fill="currentColor" />
              </div>
            </div>

            <div className="analytics-card">
              <span className="analytics-card__title">
                {t('ratings.stats.totalRated', { defaultValue: 'Total Rated' })}
              </span>
              <span className="analytics-card__value">{state.analytics.totalRated}</span>
            </div>

            <div className="analytics-card">
              <span className="analytics-card__title">
                {t('ratings.stats.totalUnrated', { defaultValue: 'Total Unrated' })}
              </span>
              <span className="analytics-card__value analytics-card__value--muted">
                {state.analytics.totalUnrated}
              </span>
            </div>

            <div className="analytics-card">
              <span className="analytics-card__title">
                {t('ratings.stats.favoritesCount', { defaultValue: 'Favorites' })}
              </span>
              <div className="analytics-card-row">
                <span className="analytics-card__value">{state.analytics.favoritesCount}</span>
                <Heart size={24} className="analytics-heart-icon" fill="currentColor" />
              </div>
            </div>

            <div className="analytics-card analytics-card--double">
              <span className="analytics-card__title">
                {t('ratings.stats.distribution', { defaultValue: 'Rating Distribution' })}
              </span>
              <div className="analytics-distribution">
                {state.analytics.distribution.map((count, index) => {
                  const maxCount = Math.max(...state.analytics.distribution, 1);
                  const percentage = (count / maxCount) * 100;
                  return (
                    <div key={index} className="analytics-distribution__row">
                      <span className="analytics-distribution__label">{index + 1}</span>
                      <div className="analytics-distribution__bar-container">
                        <div
                          className="analytics-distribution__bar"
                          style={{ width: `${percentage}%` }}
                        />
                      </div>
                      <span className="analytics-distribution__count">{count}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        ) : (
          /* Table of Rated / Unrated items */
          <div className="ratings-table-container">
            {state.isLoading ? (
              <div className="ratings-loading-container">
                <Spinner size="md" />
              </div>
            ) : (
              <>
                <Table
                  columns={columns}
                  rows={state.paginatedItems}
                  emptyText={t('ratings.table.empty', { defaultValue: 'No items match selected criteria.' })}
                />
                {state.totalPages > 1 && (
                  <div className="ratings-pagination-container">
                    <PaginationBar
                      currentPage={state.currentPage}
                      totalPages={state.totalPages}
                      onPageChange={state.setCurrentPage}
                    />
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>

      {/* Review Drawer Panel */}
      {editingItem && (
        <>
          <div
            className="review-drawer-backdrop"
            onClick={() => setEditingItem(null)}
            onKeyDown={handleKeyDownBackdrop}
            role="button"
            tabIndex={0}
          />
          <div ref={drawerRef} className={`review-drawer ${editingItem ? 'is-open' : ''}`}>
            <div className="review-drawer__header">
              <span className="review-drawer__title">
                {t('ratings.dialog.editReview', { defaultValue: 'Edit Review' })}
              </span>
              <Button
                variant="secondary-neutral"
                size="xs"
                onClick={() => setEditingItem(null)}
                className="review-drawer-close-btn"
              >
                <X size={16} />
              </Button>
            </div>
            <div className="review-drawer__content">
              <span className="review-drawer-media-title">
                {editingItem.name || editingItem.title || editingItem.displayTitle}
              </span>
              <textarea
                className="review-drawer__textarea"
                placeholder={t('ratings.dialog.placeholder', { defaultValue: 'Write review...' })}
                value={reviewText}
                onChange={(e) => setReviewText(e.target.value)}
                autoFocus
              />
            </div>
            <div className="review-drawer__footer">
              <Button variant="secondary" onClick={() => setEditingItem(null)}>
                {t('ratings.dialog.cancel', { defaultValue: 'Cancel' })}
              </Button>
              <Button variant="primary" onClick={handleSaveReview}>
                {t('ratings.dialog.save', { defaultValue: 'Save Review' })}
              </Button>
            </div>
          </div>
        </>
      )}
    </Page>
  );
}
