import { Eye, Film, Tv, FolderPlus, PlayCircle, Captions, Volume2, Image, Info } from 'lucide-react';

export const MAIN_TABS = [
  { value: 'manual', labelKey: 'organizer.tabs.manual', icon: Eye, tone: 'warning' },
  { value: 'movies', labelKey: 'organizer.tabs.movies', icon: Film, tone: 'success' },
  { value: 'episodes', labelKey: 'organizer.tabs.episodes', icon: Tv, tone: 'success' },
  { value: 'scenes', labelKey: 'organizer.tabs.scenes', icon: Film, tone: 'success' },
  { value: 'extras', labelKey: 'organizer.tabs.extras', icon: FolderPlus },
];

export const MANUAL_TABS = [
  { value: 'movies', labelKey: 'organizer.tabs.movies', icon: Film, tone: 'warning' },
  { value: 'episodes', labelKey: 'organizer.tabs.episodes', icon: Tv, tone: 'warning' },
  { value: 'scenes', labelKey: 'organizer.tabs.scenes', icon: Film, tone: 'warning' },
];

export const EXTRAS_TABS = [
  { value: 'bonus', labelKey: 'organizer.extrasTabs.bonus', icon: PlayCircle },
  { value: 'subtitles', labelKey: 'organizer.extrasTabs.subtitles', icon: Captions },
  { value: 'audio', labelKey: 'organizer.extrasTabs.audio', icon: Volume2 },
  { value: 'images', labelKey: 'organizer.extrasTabs.images', icon: Image },
  { value: 'metadata', labelKey: 'organizer.extrasTabs.metadata', icon: Info },
];

export const EMPTY_ORGANIZER = {
  manual: [],
  movies: [],
  tv: [],
  extras: [],
  collisions: [],
};

