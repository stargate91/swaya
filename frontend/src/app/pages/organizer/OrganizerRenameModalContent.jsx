import { useState, useMemo } from 'react';
import { Search } from 'lucide-react';
import { compareOrganizerValues } from './organizerMappers';
import Input from '../../ui/Input';
import SortButton from '../../ui/SortButton';
import Tooltip from '../../ui/Tooltip';
import Checkbox from '../../ui/Checkbox';
import { useOrganizerSort } from './useOrganizerSort';
import { useLocalListSearch } from '../../hooks/useLocalListSearch';
import '../../styles/RenameModal.css';

const RENAME_SEARCH_KEYS = ['source', 'target', 'type'];

export default function OrganizerRenameModalContent({ items = [], t, organizeInPlace, setOrganizeInPlace }) {
  const [searchQuery, setSearchQuery] = useState('');
  const { sortConfig, handleSortToggle } = useOrganizerSort('target', 'asc');

  const filteredItems = useLocalListSearch(items, searchQuery, RENAME_SEARCH_KEYS);

  const sortedItems = useMemo(() => {
    const result = [...filteredItems];
    if (sortConfig.key) {
      result.sort((a, b) => {
        const valA = a[sortConfig.key] || '';
        const valB = b[sortConfig.key] || '';
        const comp = compareOrganizerValues(valA, valB);
        return sortConfig.direction === 'asc' ? comp : -comp;
      });
    }
    return result;
  }, [filteredItems, sortConfig]);

  return (
    <div className="organizer-rename-modal">
      <div className="organizer-rename-modal__search">
        <Input
          type="text"
          placeholder={t('organizer.searchPlaceholder') || 'Search files...'}
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          icon={Search}
        />
      </div>

      <div className="organizer-rename-modal__summary" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
        <span>
          {t('organizer.renameModal.showing')
            .replace('{count}', sortedItems.length)
            .replace('{total}', items.length)}
        </span>
        <Checkbox
          checked={organizeInPlace}
          onChange={(e) => setOrganizeInPlace(e.target.checked)}
        >
          {t('organizer.renameModal.organizeInPlaceCheckbox') || 'Keep original filenames (Organize in Place)'}
        </Checkbox>
      </div>

      <div className="organizer-rename-modal__list-container">
        <table className="organizer-rename-modal__table">
          <thead>
            <tr className="organizer-rename-modal__header-row">
              <th className="organizer-rename-modal__header-col organizer-rename-modal__header-col--source">
                <SortButton
                  isActive={sortConfig.key === 'source'}
                  label={t('organizer.renameModal.currentFilename') || 'Current Filename'}
                  onToggle={() => handleSortToggle('source')}
                  sortDirection={sortConfig.direction}
                />
              </th>
              <th className="organizer-rename-modal__header-col organizer-rename-modal__header-col--target">
                <SortButton
                  isActive={sortConfig.key === 'target'}
                  label={t('organizer.renameModal.newFilename') || 'New Filename'}
                  onToggle={() => handleSortToggle('target')}
                  sortDirection={sortConfig.direction}
                />
              </th>
              <th className="organizer-rename-modal__header-col organizer-rename-modal__header-col--type">
                <SortButton
                  isActive={sortConfig.key === 'type'}
                  label={t('organizer.table.type') || 'Type'}
                  onToggle={() => handleSortToggle('type')}
                  sortDirection={sortConfig.direction}
                />
              </th>
            </tr>
          </thead>
          <tbody>
            {sortedItems.map((item) => (
              <tr key={item.id} className="organizer-rename-modal__row">
                <td className="organizer-rename-modal__col organizer-rename-modal__col--source">
                  <Tooltip content={item.sourcePath} side="top" align="start">
                    <span className="organizer-rename-modal__cell-text">
                      {item.source}
                    </span>
                  </Tooltip>
                </td>
                <td className="organizer-rename-modal__col organizer-rename-modal__col--target">
                  <Tooltip content={organizeInPlace ? item.sourcePath : item.targetPath} side="top" align="start">
                    <span className="organizer-rename-modal__cell-text" style={organizeInPlace ? { opacity: 0.55, fontStyle: 'italic' } : {}}>
                      {organizeInPlace ? item.source : item.target}
                    </span>
                  </Tooltip>
                </td>
                <td className="organizer-rename-modal__col organizer-rename-modal__col--type">
                  {item.type}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {sortedItems.length === 0 && (
          <div className="organizer-rename-modal__empty">
            {t('organizer.renameModal.noMatching')}
          </div>
        )}
      </div>
    </div>
  );
}
