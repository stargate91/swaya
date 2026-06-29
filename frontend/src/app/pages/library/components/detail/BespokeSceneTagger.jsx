import { useState, useRef, useEffect } from 'react';
import { Plus, X, Search, ChevronDown, ChevronLeft, ChevronRight } from 'lucide-react';
import Pill from '@/ui/Pill';
import { useAllTagsQuery } from '@/queries/libraryQueries';
import { useMediaDetailContext } from './MediaDetailContext';
import './BespokeSceneTagger.css';

function HorizontalPillList({ children }) {
  const containerRef = useRef(null);
  const [showLeft, setShowLeft] = useState(false);
  const [showRight, setShowRight] = useState(false);

  const checkScroll = () => {
    const el = containerRef.current;
    if (!el) return;
    setShowLeft(el.scrollLeft > 1);
    setShowRight(el.scrollLeft < el.scrollWidth - el.clientWidth - 1);
  };

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    checkScroll();

    window.addEventListener('resize', checkScroll);
    const observer = new MutationObserver(checkScroll);
    observer.observe(el, { childList: true, subtree: true });

    return () => {
      window.removeEventListener('resize', checkScroll);
      observer.disconnect();
    };
  }, []);

  const handleScroll = (direction) => {
    const el = containerRef.current;
    if (!el) return;
    const scrollAmount = 150;
    el.scrollBy({
      left: direction === 'left' ? -scrollAmount : scrollAmount,
      behavior: 'smooth',
    });
  };

  return (
    <div className="bespoke-scene-tagger-scroller-wrapper">
      {showLeft && (
        <button
          type="button"
          onClick={() => handleScroll('left')}
          className="bespoke-scene-tagger-scroller-btn bespoke-scene-tagger-scroller-btn--left"
        >
          <ChevronLeft size={12} />
        </button>
      )}
      <div
        ref={containerRef}
        onScroll={checkScroll}
        className="bespoke-scene-tagger-pills-row bespoke-scene-tagger-pills-row--nowrap"
      >
        {children}
      </div>
      {showRight && (
        <button
          type="button"
          onClick={() => handleScroll('right')}
          className="bespoke-scene-tagger-scroller-btn bespoke-scene-tagger-scroller-btn--right"
        >
          <ChevronRight size={12} />
        </button>
      )}
    </div>
  );
}

export default function BespokeSceneTagger() {
  const { state, mutations, type, t } = useMediaDetailContext();
  const { item, cleanId, effectiveId } = state;
  const { updateStatusMutation } = mutations;

  const [searchQuery, setSearchQuery] = useState('');
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const dropdownRef = useRef(null);

  const { data: allTags = [] } = useAllTagsQuery(item?.is_adult);

  const currentTags = item?.custom_tags || [];
  const suggestedTags = item?.suggested_tags || [];

  // Filter out suggestions that are already in active tags
  const unassignedSuggestions = suggestedTags.filter(
    (tag) => !currentTags.some((ct) => ct.toLowerCase() === tag.toLowerCase())
  );

  // Filter all global tags for autocomplete dropdown, excluding already assigned ones
  const filteredTags = allTags.filter((tag) => {
    const isAssigned = currentTags.some((ct) => ct.toLowerCase() === tag.name.toLowerCase());
    const matchesSearch = tag.name.toLowerCase().includes(searchQuery.toLowerCase());
    return !isAssigned && matchesSearch;
  });

  const handleToggleTag = (tagName) => {
    const isAssigned = currentTags.includes(tagName);
    const nextTags = isAssigned
      ? currentTags.filter((name) => name !== tagName)
      : [...currentTags, tagName];

    updateStatusMutation.mutate({
      itemId: effectiveId,
      tvId: cleanId,
      payload: {
        custom_tags: nextTags,
        media_type: type,
      },
    });
  };

  const handleAddTag = (tagName) => {
    if (currentTags.includes(tagName)) return;
    const nextTags = [...currentTags, tagName];

    updateStatusMutation.mutate({
      itemId: effectiveId,
      tvId: cleanId,
      payload: {
        custom_tags: nextTags,
        media_type: type,
      },
    });
    setSearchQuery('');
    setIsDropdownOpen(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      const trimmed = searchQuery.trim();
      if (!trimmed) return;

      // Find if tag exists in allTags case-insensitively
      const existing = allTags.find((t) => t.name.toLowerCase() === trimmed.toLowerCase());
      const tagNameToAdd = existing ? existing.name : trimmed;
      handleAddTag(tagNameToAdd);
    }
  };

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className="bespoke-scene-tagger-card">
      <div className="bespoke-scene-tagger-header">
        <span className="bespoke-scene-tagger-title">
          {t('library.details.tagger') || 'Tags & Keywords'}
        </span>
      </div>

      <div className="bespoke-scene-tagger-body">
        {/* Active Tags */}
        <div className="bespoke-scene-tagger-active-section">
          <span className="bespoke-scene-tagger-label">
            {t('library.details.activeTags') || 'Active Tags'}
          </span>
          {currentTags.length > 0 ? (
            <HorizontalPillList>
              {currentTags.map((tagName) => {
                const tagColor = allTags.find((t) => t.name === tagName)?.color || 'var(--color-accent-blue)';
                return (
                  <Pill
                    key={tagName}
                    variant="custom"
                    style={{
                      backgroundColor: `color-mix(in srgb, ${tagColor} 12%, rgba(255, 255, 255, 0.02))`,
                      borderColor: `color-mix(in srgb, ${tagColor} 30%, var(--color-border-default))`,
                      color: `color-mix(in srgb, ${tagColor} 85%, white)`,
                    }}
                    className="bespoke-scene-tagger-pill-active"
                  >
                    <span>{tagName}</span>
                    <button
                      type="button"
                      className="bespoke-scene-tagger-pill-remove"
                      onClick={() => handleToggleTag(tagName)}
                      title="Remove tag"
                    >
                      <X size={10} />
                    </button>
                  </Pill>
                );
              })}
            </HorizontalPillList>
          ) : (
            <span className="bespoke-scene-tagger-empty-text">
              {t('library.details.noTagsAssigned') || 'No tags assigned.'}
            </span>
          )}
        </div>

        {/* Add Tag Autocomplete Input */}
        <div className="bespoke-scene-tagger-input-wrapper" ref={dropdownRef}>
          <div className="bespoke-scene-tagger-input-container">
            <Search size={13} className="bespoke-scene-tagger-search-icon" />
            <input
              type="text"
              placeholder={t('library.tags.searchOrAdd') || 'Search or add tag...'}
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setIsDropdownOpen(true);
              }}
              onFocus={() => setIsDropdownOpen(true)}
              onKeyDown={handleKeyDown}
              className="bespoke-scene-tagger-input"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                className="bespoke-scene-tagger-clear-btn"
              >
                <X size={12} />
              </button>
            )}
          </div>

          {isDropdownOpen && (filteredTags.length > 0 || searchQuery.trim()) && (
            <div className="bespoke-scene-tagger-dropdown">
              {filteredTags.map((tag) => (
                <button
                  key={tag.name}
                  type="button"
                  onClick={() => handleAddTag(tag.name)}
                  className="bespoke-scene-tagger-dropdown-item"
                >
                  <span
                    className="bespoke-scene-tagger-dropdown-color-dot"
                    style={{ backgroundColor: tag.color }}
                  />
                  <span>{tag.name}</span>
                </button>
              ))}
              {searchQuery.trim() && !allTags.some((t) => t.name.toLowerCase() === searchQuery.trim().toLowerCase()) && (
                <button
                  type="button"
                  onClick={() => handleAddTag(searchQuery.trim())}
                  className="bespoke-scene-tagger-dropdown-item bespoke-scene-tagger-dropdown-item--create"
                >
                  <Plus size={12} />
                  <span>Create tag &quot;{searchQuery.trim()}&quot;</span>
                </button>
              )}
            </div>
          )}
        </div>

        {/* Suggested Tags / Keywords */}
        {unassignedSuggestions.length > 0 && (
          <div className="bespoke-scene-tagger-suggested-section">
            <span className="bespoke-scene-tagger-label">
              {t('library.details.suggestedTags') || 'Suggested Tags'}
            </span>
            <HorizontalPillList>
              {unassignedSuggestions.map((tag) => (
                <button
                  key={tag}
                  type="button"
                  onClick={() => handleAddTag(tag)}
                  className="bespoke-scene-tagger-pill-suggested"
                  title="Add tag"
                >
                  <Plus size={10} />
                  <span>{tag}</span>
                </button>
              ))}
            </HorizontalPillList>
          </div>
        )}
      </div>
    </div>
  );
}
