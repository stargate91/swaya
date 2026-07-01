import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, ChevronDown, ArrowUpRight, Clapperboard, Film, Tv, Users, Video, Loader2 } from 'lucide-react';
import api from '../lib/api';
import { useSettingsQuery } from '../queries/settingsQueries';
import { resolveMediaImageUrl } from '../lib/imageUrls';
import './GlobalSearch.css';

const SOURCES = [
  { id: 'tmdb', name: 'TMDb', adult: false },
  { id: 'stashdb', name: 'StashDB', adult: true },
  { id: 'fansdb', name: 'FansDB', adult: true },
  { id: 'porndb', name: 'PornDB', adult: true },
];

const TYPES_BY_SOURCE = {
  tmdb: [
    { id: 'all', name: 'All', icon: Clapperboard },
    { id: 'movie', name: 'Movies', icon: Film },
    { id: 'tv', name: 'TV Shows', icon: Tv },
    { id: 'person', name: 'People', icon: Users },
  ],
  stashdb: [
    { id: 'scene', name: 'Scenes', icon: Video },
    { id: 'person', name: 'Performers', icon: Users },
  ],
  fansdb: [
    { id: 'scene', name: 'Scenes', icon: Video },
    { id: 'person', name: 'Performers', icon: Users },
  ],
  porndb: [
    { id: 'scene', name: 'Scenes', icon: Video },
    { id: 'person', name: 'Performers', icon: Users },
  ],
};

export default function GlobalSearch() {
  const { data: settings } = useSettingsQuery();
  const navigate = useNavigate();
  
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  
  // Selection state
  const [selectedSource, setSelectedSource] = useState('tmdb');
  const [selectedType, setSelectedType] = useState('all');
  
  // UI visibility states
  const [isSelectorOpen, setIsSelectorOpen] = useState(false);
  const [isOverlayOpen, setIsOverlayOpen] = useState(false);
  
  const containerRef = useRef(null);
  const selectorRef = useRef(null);
  const debounceTimer = useRef(null);

  const hasAdult = settings?.include_adult;
  const filteredSources = SOURCES.filter(s => !s.adult || hasAdult);

  // Close menus when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (containerRef.current && !containerRef.current.contains(event.target)) {
        setIsOverlayOpen(false);
      }
      if (selectorRef.current && !selectorRef.current.contains(event.target)) {
        setIsSelectorOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Perform search
  const performSearch = async (searchQuery) => {
    if (!searchQuery.trim()) {
      setResults([]);
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    try {
      const data = await api.metadata.globalSearch({
        query: searchQuery,
        source: selectedSource,
        searchType: selectedType,
        includeAdult: hasAdult,
      });
      setResults(data || []);
      setIsOverlayOpen(true);
    } catch (err) {
      console.error('Global search error:', err);
      setResults([]);
    } finally {
      setIsLoading(false);
    }
  };

  // Debounced search trigger
  useEffect(() => {
    if (debounceTimer.current) {
      clearTimeout(debounceTimer.current);
    }
    if (query.trim().length >= 2) {
      debounceTimer.current = setTimeout(() => {
        performSearch(query);
      }, 300);
    } else {
      setResults([]);
      setIsOverlayOpen(false);
    }
    return () => clearTimeout(debounceTimer.current);
  }, [query, selectedSource, selectedType]);

  const handleSourceSelect = (sourceId) => {
    setSelectedSource(sourceId);
    // Auto-select first available type for this source
    const availableTypes = TYPES_BY_SOURCE[sourceId] || [];
    const hasSameType = availableTypes.some(t => t.id === selectedType);
    if (!hasSameType && availableTypes.length > 0) {
      setSelectedType(availableTypes[0].id);
    }
  };

  const handleResultClick = (item) => {
    setIsOverlayOpen(false);
    setQuery('');
    
    if (item.media_type === 'movie') {
      const prefix = item.provider === 'porndb' ? 'porndb_' : 'tmdb_';
      const id = String(item.id).startsWith(prefix) ? item.id : `${prefix}${item.id}`;
      navigate(`/library/movie/${id}`, { state: { allowAdult: true } });
    } else if (item.media_type === 'tv') {
      navigate(`/library/tv/${item.id}`, { state: { allowAdult: true } });
    } else if (item.media_type === 'person') {
      navigate(`/library/people/${item.id}`, { state: { allowAdult: true } });
    } else if (item.media_type === 'scene') {
      const prefix = item.provider === 'porndb' ? 'porndb' : item.provider === 'fansdb' ? 'fansdb' : 'stash';
      const id = String(item.id).startsWith(`${prefix}_`) ? item.id : `${prefix}_${item.id}`;
      navigate(`/library/scene/${id}`, { state: { allowAdult: true } });
    }
  };

  // Get active icons/labels
  const activeSourceObj = SOURCES.find(s => s.id === selectedSource) || SOURCES[0];
  const activeTypeObj = (TYPES_BY_SOURCE[selectedSource] || []).find(t => t.id === selectedType) || { name: 'All', icon: Clapperboard };
  const ActiveTypeIcon = activeTypeObj.icon;

  return (
    <div className="global-search" ref={containerRef}>
      <div className="global-search__bar">
        {/* Source & Type Selector Trigger */}
        <div className="global-search__selector-wrapper" ref={selectorRef}>
          <button
            type="button"
            className="global-search__selector-btn"
            onClick={() => setIsSelectorOpen(!isSelectorOpen)}
          >
            <ActiveTypeIcon className="global-search__active-icon" size={14} />
            <span className="global-search__active-label">
              {activeTypeObj.name}
            </span>
            <ChevronDown className={`global-search__chevron ${isSelectorOpen ? 'is-open' : ''}`} size={12} />
          </button>

          {/* 2-Level Cascading Dropdown */}
          {isSelectorOpen && (
            <div className="global-search__dropdown">
              {/* Left Column: Sources */}
              <div className="global-search__dropdown-column global-search__dropdown-column--sources">
                <div className="global-search__dropdown-header">Source</div>
                {filteredSources.map(source => (
                  <button
                    key={source.id}
                    type="button"
                    className={`global-search__dropdown-item ${selectedSource === source.id ? 'is-active' : ''}`}
                    onClick={() => handleSourceSelect(source.id)}
                  >
                    {source.name}
                  </button>
                ))}
              </div>
              
              {/* Right Column: Types */}
              <div className="global-search__dropdown-column global-search__dropdown-column--types">
                <div className="global-search__dropdown-header">Type</div>
                {(TYPES_BY_SOURCE[selectedSource] || []).map(type => {
                  const TypeIcon = type.icon;
                  return (
                    <button
                      key={type.id}
                      type="button"
                      className={`global-search__dropdown-item ${selectedType === type.id ? 'is-active' : ''}`}
                      onClick={() => {
                        setSelectedType(type.id);
                        setIsSelectorOpen(false);
                      }}
                    >
                      <TypeIcon size={12} className="global-search__item-icon" />
                      {type.name}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        <div className="global-search__divider" />

        {/* Input Field */}
        <div className="global-search__input-wrapper">
          <Search className="global-search__search-icon" size={14} />
          <input
            type="text"
            className="global-search__input"
            placeholder={`Search ${activeSourceObj.name === 'TMDb' ? activeTypeObj.name.toLowerCase() : activeTypeObj.name.toLowerCase() + ' on ' + activeSourceObj.name}...`}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => query.trim().length >= 2 && setIsOverlayOpen(true)}
          />
          {isLoading && <Loader2 className="global-search__loader animate-spin" size={14} />}
        </div>
      </div>

      {/* Suggestion Results Overlay */}
      {isOverlayOpen && results.length > 0 && (
        <div className="global-search__overlay">
          <div className="global-search__results-list">
            {results.map((item, idx) => (
              <div
                key={`${item.id}-${item.media_type}-${idx}`}
                className="global-search__result-item"
                onClick={() => handleResultClick(item)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => e.key === 'Enter' && handleResultClick(item)}
              >
                {item.poster_path ? (
                  <img src={resolveMediaImageUrl(item.poster_path, 'posterThumb')} alt="" className="global-search__item-poster" loading="lazy" />
                ) : (
                  <div className="global-search__item-poster-placeholder">
                    <ActiveTypeIcon size={16} />
                  </div>
                )}
                <div className="global-search__item-info">
                  <div className="global-search__item-title-row">
                    <span className="global-search__item-title">{item.title}</span>
                    {item.year && <span className="global-search__item-year">({item.year})</span>}
                  </div>
                  <div className="global-search__item-meta">
                    <span className="global-search__item-badge">
                      {item.media_type === 'person' ? 'performer' : item.media_type}
                    </span>
                    {item.overview && (
                      <span className="global-search__item-overview">
                        • {item.overview.length > 60 ? item.overview.slice(0, 60) + '...' : item.overview}
                      </span>
                    )}
                  </div>
                </div>
                <ArrowUpRight className="global-search__arrow-icon" size={14} />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
