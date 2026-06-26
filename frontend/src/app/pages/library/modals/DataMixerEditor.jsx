import { useState, useEffect } from 'react';
import { useTranslation } from '@/providers/LanguageContext';
import { useUi } from '@/providers/UiProvider';
import { useSetPersonFieldRoutingMutation, useSavePersonCustomFieldsMutation } from '@/queries/libraryQueries';
import { usePersonDetailQuery } from '@/queries/metadataQueries';
import { Check, Pencil } from 'lucide-react';
import './LinkSourceModalContent.css'; // Reuse basic styles and override

export default function DataMixerEditor({ person: initialPerson, onBack }) {
  const { t } = useTranslation();
  const { toast } = useUi();
  const routingMutation = useSetPersonFieldRoutingMutation();
  const saveCustomFieldsMutation = useSavePersonCustomFieldsMutation();

  const { data: fetchedPerson } = usePersonDetailQuery(initialPerson?.id);
  const person = fetchedPerson || initialPerson;

  const [localRouting, setLocalRouting] = useState(null);
  const [editingField, setEditingField] = useState(null);
  const [editValue, setEditValue] = useState('');

  useEffect(() => {
    if (person?.field_routing) {
      setLocalRouting(person.field_routing);
    } else {
      setLocalRouting({});
    }
  }, [person?.field_routing]);

  const currentRouting = localRouting || {};

  const FIELDS = [
    { key: 'biography', label: 'Biography', type: 'text' },
    { key: 'birthday', label: 'Birthday', type: 'string' },
    { key: 'place_of_birth', label: 'Place of Birth', type: 'string' },
    { key: 'gender', label: 'Gender', type: 'gender' },
    { key: 'height', label: 'Height', type: 'height' },
    { key: 'hair_color', label: 'Hair Color', type: 'string' },
    { key: 'eye_color', label: 'Eye Color', type: 'string' },
    { key: 'ethnicity', label: 'Ethnicity', type: 'string' },
    { key: 'measurements', label: 'Measurements', type: 'string' },
    { key: 'cup_size', label: 'Cup Size', type: 'string' },
    { key: 'band_size', label: 'Band Size', type: 'string' },
    { key: 'waist', label: 'Waist', type: 'string' },
    { key: 'hip', label: 'Hip', type: 'string' },
    { key: 'tattoos', label: 'Tattoos', type: 'string' },
    { key: 'piercings', label: 'Piercings', type: 'string' },
    { key: 'breast_type', label: 'Breast Type', type: 'string' },
    { key: 'orientation', label: 'Orientation', type: 'string' },
  ];

  const PROVIDERS = [
    { key: 'tmdb', label: 'TMDb' },
    { key: 'stashdb', label: 'StashDB' },
    { key: 'fansdb', label: 'FansDB' },
    { key: 'porndb', label: 'THEPornDB' },
    { key: 'manual', label: 'Custom' },
  ];

  // Helper to format values nicely in the grid
  const formatValue = (val, type) => {
    if (val === undefined || val === null || val === '') return '-';
    if (type === 'gender') {
      if (val === 1 || val === '1') return 'Female';
      if (val === 2 || val === '2') return 'Male';
      return 'Other';
    }
    if (type === 'height') {
      return `${val} cm`;
    }
    if (type === 'text') {
      // Show biography snippet
      if (typeof val === 'object') {
        const text = val.en || val.hu || Object.values(val)[0] || '';
        return text.length > 60 ? text.substring(0, 60) + '...' : text;
      }
      return val.length > 60 ? val.substring(0, 60) + '...' : val;
    }
    const strVal = String(val);
    const lower = strVal.toLowerCase();
    if (lower === 'no piercings' || lower === 'no tattoos') {
      return 'No';
    }
    return strVal;
  };

  // Helper to get raw value of a field from a specific provider
  const getProviderValue = (providerKey, fieldKey) => {
    const link = person?.external_links?.find(l => l.provider === providerKey);
    if (!link || !link.source_data) return null;
    if (fieldKey === 'biography') {
      return link.source_data.biographies || link.source_data.biography;
    }
    return link.source_data[fieldKey];
  };

  const handleSelectRoute = async (fieldKey, providerKey) => {
    const newRouting = { ...currentRouting };
    if (providerKey === 'auto') {
      delete newRouting[fieldKey];
    } else {
      newRouting[fieldKey] = providerKey;
    }

    setLocalRouting(newRouting);

    try {
      await routingMutation.mutateAsync({
        personId: person.id,
        routing: newRouting,
      });
      toast('Metadata routing updated successfully!', 'success');
    } catch (err) {
      setLocalRouting(person?.field_routing || {});
      toast(err.message || 'Failed to update routing', 'danger');
    }
  };

  const handleSaveCustomValue = async (fieldKey) => {
    setEditingField(null);
    try {
      await saveCustomFieldsMutation.mutateAsync({
        personId: person.id,
        fields: { [fieldKey]: editValue },
      });
      await handleSelectRoute(fieldKey, 'manual');
    } catch (err) {
      toast(err.message || 'Failed to save custom value', 'danger');
    }
  };

  // Check if a specific source is linked
  const isSourceLinked = (providerKey) => {
    if (providerKey === 'manual') return true;
    return person?.external_links?.some(l => l.provider === providerKey);
  };

  return (
    <div className="link-source-modal link-source-modal--mixer-view">
      <div className="data-mixer-grid-container">
        <table className="data-mixer-table">
          <thead>
            <tr>
              <th className="mixer-th-field">Field</th>
              <th className="mixer-th-source">Auto (Default)</th>
              {PROVIDERS.map(p => (
                <th key={p.key} className={`mixer-th-source ${!isSourceLinked(p.key) ? 'mixer-th-disabled' : ''}`}>
                  {p.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {FIELDS.map(field => {
              const activeRoute = currentRouting[field.key] || 'auto';
              
              return (
                <tr key={field.key} className="mixer-row">
                  <td className="mixer-td-field-label">
                    {field.label}
                  </td>
                  {/* Auto routing option */}
                  <td 
                    onClick={() => handleSelectRoute(field.key, 'auto')}
                    className={`mixer-td-cell mixer-td-cell--auto ${activeRoute === 'auto' ? 'mixer-td-cell--active' : ''}`}
                  >
                    <div className="mixer-cell-content">
                      <span className="mixer-cell-value">Default Priority</span>
                      {activeRoute === 'auto' && <Check size={14} className="mixer-check-icon" />}
                    </div>
                  </td>
                  {/* Provider options */}
                  {PROVIDERS.map(p => {
                    const isLinked = isSourceLinked(p.key);
                    const rawVal = getProviderValue(p.key, field.key);
                    const formatted = formatValue(rawVal, field.type);
                    const isSelected = activeRoute === p.key;
                    const isEditing = p.key === 'manual' && editingField === field.key;

                    const hasValue = (() => {
                      if (p.key === 'manual') return true;
                      if (rawVal === null || rawVal === undefined || rawVal === '') return false;
                      if (formatted === '-') return false;
                      if (typeof rawVal === 'object') {
                        const values = Object.values(rawVal);
                        if (values.length === 0) return false;
                        if (values.every(v => v === null || v === undefined || String(v).trim() === '')) return false;
                      }
                      if (String(rawVal).trim() === '') return false;
                      return true;
                    })();

                    const handleCellClick = () => {
                      if (p.key === 'manual') {
                        setEditingField(field.key);
                        setEditValue(rawVal !== null && rawVal !== undefined ? String(rawVal) : '');
                      } else {
                        if (isLinked && hasValue) {
                          handleSelectRoute(field.key, p.key);
                        }
                      }
                    };

                    return (
                      <td
                        key={p.key}
                        onClick={handleCellClick}
                        className={`mixer-td-cell ${!isLinked || !hasValue ? 'mixer-td-cell--disabled' : ''} ${isSelected ? 'mixer-td-cell--active' : ''} ${p.key === 'manual' ? 'mixer-td-cell--manual' : ''} ${isEditing ? 'mixer-td-cell--editing' : ''}`}
                      >
                        <div className="mixer-cell-content">
                          {isEditing ? (
                            field.type === 'gender' ? (
                              <select
                                value={editValue}
                                onChange={(e) => setEditValue(e.target.value)}
                                onBlur={() => handleSaveCustomValue(field.key)}
                                autoFocus
                                className="mixer-custom-select"
                                onClick={(e) => e.stopPropagation()}
                              >
                                <option value="">- Select -</option>
                                <option value="1">Female</option>
                                <option value="2">Male</option>
                                <option value="0">Other</option>
                              </select>
                            ) : field.type === 'text' ? (
                              <textarea
                                value={editValue}
                                onChange={(e) => setEditValue(e.target.value)}
                                onBlur={() => handleSaveCustomValue(field.key)}
                                autoFocus
                                className="mixer-custom-textarea"
                                onClick={(e) => e.stopPropagation()}
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter' && !e.shiftKey) {
                                    e.preventDefault();
                                    handleSaveCustomValue(field.key);
                                  }
                                  if (e.key === 'Escape') {
                                    setEditingField(null);
                                  }
                                }}
                              />
                            ) : (
                              <input
                                type={field.key === 'height' || field.key === 'waist' || field.key === 'hip' || field.key === 'band_size' ? 'number' : 'text'}
                                value={editValue}
                                onChange={(e) => setEditValue(e.target.value)}
                                onBlur={() => handleSaveCustomValue(field.key)}
                                autoFocus
                                className="mixer-custom-input"
                                onClick={(e) => e.stopPropagation()}
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter') {
                                    handleSaveCustomValue(field.key);
                                  }
                                  if (e.key === 'Escape') {
                                    setEditingField(null);
                                  }
                                }}
                              />
                            )
                          ) : (
                            <>
                              <span className="mixer-cell-value" title={rawVal && typeof rawVal === 'string' ? rawVal : ''}>
                                {rawVal === null || rawVal === undefined || rawVal === '' ? (p.key === 'manual' ? 'Set custom...' : '-') : formatted}
                              </span>
                              {p.key === 'manual' && <Pencil size={12} className="mixer-edit-icon" />}
                              {isSelected && <Check size={14} className="mixer-check-icon" />}
                            </>
                          )}
                        </div>
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
