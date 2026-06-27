import { useState, useEffect } from 'react';
import { useSavePersonCustomFieldsMutation } from '@/queries/libraryQueries';
import { usePersonDetailQuery } from '@/queries/metadataQueries';
import { useTranslation } from '@/providers/LanguageContext';
import { useUi } from '@/providers/UiProvider';
import Button from '@/ui/Button';
import Input from '@/ui/Input';
import Dropdown from '@/ui/Dropdown';
import FloatingActionBar from '@/ui/FloatingActionBar';
import { TARGET_LANGUAGE_OPTIONS } from '@/pages/settings/settingsLanguageOptions';

export default function PerformerCustomValuesTab({ personId, person: initialPerson, onDirtyChange, isShaking }) {
  const { t } = useTranslation();
  const { toast } = useUi();
  const { data: fetchedPerson } = usePersonDetailQuery(personId);
  const person = fetchedPerson || initialPerson;
  const saveMutation = useSavePersonCustomFieldsMutation();
  const manualLink = person?.external_links?.find(l => l.provider === 'manual');
  const manualData = manualLink?.source_data || {};

  const genderOptions = [
    { value: '1', label: 'Female' },
    { value: '2', label: 'Male' },
    { value: '0', label: 'Other' },
  ];

  const sameSexOnlyOptions = [
    { value: 'No', label: 'No' },
    { value: 'Yes', label: 'Yes' },
  ];

  const breastTypeOptions = [
    { value: 'NATURAL', label: 'Natural' },
    { value: 'FAKE', label: 'Fake / Implant' },
    { value: 'NA', label: 'N/A' },
  ];

  const cupSizeOptions = ['A', 'B', 'C', 'D', 'DD', 'DDD', 'E', 'F', 'G', 'H', 'I', 'J', 'K'];

  const hairColorOptions = [
    { value: 'BLONDE', label: 'Blonde' },
    { value: 'BRUNETTE', label: 'Brunette' },
    { value: 'BLACK', label: 'Black' },
    { value: 'RED', label: 'Red' },
    { value: 'AUBURN', label: 'Auburn' },
    { value: 'GREY', label: 'Grey' },
    { value: 'BALD', label: 'Bald' },
    { value: 'VARIOUS', label: 'Various' },
    { value: 'WHITE', label: 'White' },
    { value: 'OTHER', label: 'Other' },
  ];

  const eyeColorOptions = [
    { value: 'BLUE', label: 'Blue' },
    { value: 'BROWN', label: 'Brown' },
    { value: 'GREY', label: 'Grey' },
    { value: 'GREEN', label: 'Green' },
    { value: 'HAZEL', label: 'Hazel' },
    { value: 'RED', label: 'Red' },
  ];

  const ethnicityOptions = [
    { value: 'CAUCASIAN', label: 'Caucasian' },
    { value: 'BLACK', label: 'Black' },
    { value: 'ASIAN', label: 'Asian' },
    { value: 'INDIAN', label: 'Indian' },
    { value: 'LATIN', label: 'Latin' },
    { value: 'MIDDLE_EASTERN', label: 'Middle Eastern' },
    { value: 'MIXED', label: 'Mixed' },
    { value: 'OTHER', label: 'Other' },
  ];

  const getDropdownOptions = (standardOptions, currentValue) => {
    if (!currentValue) return standardOptions;
    const upperValue = currentValue.toUpperCase();
    const exists = standardOptions.some(opt => opt.value === upperValue);
    if (exists) return standardOptions;
    const label = currentValue.charAt(0).toUpperCase() + currentValue.slice(1).toLowerCase();
    return [...standardOptions, { value: upperValue, label }];
  };

  const [selectedBioLang, setSelectedBioLang] = useState('en');

  const [form, setForm] = useState({
    biographies: {},
    birthday: '',
    place_of_birth: '',
    gender: '',
    height: '',
    weight: '',
    hair_color: '',
    eye_color: '',
    ethnicity: '',
    measurements: '',
    cup_size: '',
    band_size: '',
    waist: '',
    hip: '',
    tattoos: '',
    piercings: '',
    breast_type: '',
    same_sex_only: '',
  });

  const [initialForm, setInitialForm] = useState(null);

  useEffect(() => {
    if (manualData) {
      const initialized = {
        biographies: manualData.biographies || (manualData.biography ? { en: manualData.biography } : {}),
        birthday: manualData.birthday || '',
        place_of_birth: manualData.place_of_birth || '',
        gender: manualData.gender !== undefined ? String(manualData.gender) : '',
        height: manualData.height !== undefined ? String(manualData.height) : '',
        weight: manualData.weight !== undefined ? String(manualData.weight) : '',
        hair_color: manualData.hair_color ? manualData.hair_color.toUpperCase() : '',
        eye_color: manualData.eye_color ? manualData.eye_color.toUpperCase() : '',
        ethnicity: manualData.ethnicity ? manualData.ethnicity.toUpperCase() : '',
        measurements: manualData.measurements || '',
        cup_size: manualData.cup_size || '',
        band_size: manualData.band_size !== undefined ? String(manualData.band_size) : '',
        waist: manualData.waist !== undefined ? String(manualData.waist) : '',
        hip: manualData.hip !== undefined ? String(manualData.hip) : '',
        tattoos: manualData.tattoos || '',
        piercings: manualData.piercings || '',
        breast_type: manualData.breast_type || '',
        same_sex_only: manualData.same_sex_only || '',
      };
      setForm(initialized);
      setInitialForm(initialized);
    }
  }, [manualLink]);

  const handleChange = (key, val) => {
    setForm(prev => ({ ...prev, [key]: val }));
  };

  const handleReset = () => {
    if (initialForm) {
      setForm(initialForm);
    }
  };

  const errors = (() => {
    const errs = {};
    if (form.height) {
      const h = Number(form.height);
      if (isNaN(h) || h < 50 || h > 300) {
        errs.height = t('performerEdit.validation.height');
      }
    }
    if (form.weight) {
      const w = Number(form.weight);
      if (isNaN(w) || w < 30 || w > 300) {
        errs.weight = t('performerEdit.validation.weight');
      }
    }
    if (form.cup_size) {
      if (!/^[A-Z]{1,3}$/.test(form.cup_size)) {
        errs.cup_size = t('performerEdit.validation.cupSize');
      }
    }
    if (form.band_size) {
      const b = Number(form.band_size);
      if (isNaN(b) || b < 10 || b > 100) {
        errs.band_size = t('performerEdit.validation.bandSize');
      }
    }
    if (form.waist) {
      const w = Number(form.waist);
      if (isNaN(w) || w < 10 || w > 100) {
        errs.waist = t('performerEdit.validation.waist');
      }
    }
    if (form.hip) {
      const h = Number(form.hip);
      if (isNaN(h) || h < 10 || h > 100) {
        errs.hip = t('performerEdit.validation.hip');
      }
    }
    return errs;
  })();

  const handleSave = async (e) => {
    if (e && e.preventDefault) e.preventDefault();
    if (Object.keys(errors).length > 0) {
      toast(t('performerEdit.validation.correctErrors'), 'danger');
      return;
    }
    try {
      const payload = {};
      Object.entries(form).forEach(([k, v]) => {
        if (k === 'biographies') {
          const cleanedBios = {};
          Object.entries(v || {}).forEach(([lang, val]) => {
            if (val && val.trim() !== '') {
              cleanedBios[lang] = val;
            }
          });
          payload['biographies'] = cleanedBios;
        } else if (v === '') {
          payload[k] = null;
        } else if (k === 'gender' || k === 'height' || k === 'weight' || k === 'band_size' || k === 'waist' || k === 'hip') {
          payload[k] = Number(v);
        } else {
          payload[k] = v;
        }
      });
      payload['measurements'] = computedMeasurements || null;

      await saveMutation.mutateAsync({
        personId: person.id,
        fields: payload,
      });
      setInitialForm(form);
      toast('Custom values saved successfully!', 'success');
    } catch (err) {
      toast(err.message || 'Failed to save custom values', 'danger');
    }
  };

  const computedMeasurements = (() => {
    const parts = [];
    if (form.band_size && form.cup_size) {
      parts.push(`${form.band_size}${form.cup_size}`);
    } else if (form.cup_size) {
      parts.push(form.cup_size);
    } else if (form.band_size) {
      parts.push(form.band_size);
    }

    if (form.waist && form.hip) {
      parts.push(`${form.waist}-${form.hip}`);
    } else if (form.waist) {
      parts.push(form.waist);
    } else if (form.hip) {
      parts.push(form.hip);
    }
    return parts.join('-');
  })();

  const isDirty = initialForm && Object.keys(form).some(key => {
    if (key === 'measurements') return false;
    if (key === 'biographies') {
      const current = form[key] || {};
      const initial = initialForm[key] || {};
      const allKeys = new Set([...Object.keys(current), ...Object.keys(initial)]);
      for (const k of allKeys) {
        if ((current[k] || '') !== (initial[k] || '')) return true;
      }
      return false;
    }
    return form[key] !== initialForm[key];
  });

  useEffect(() => {
    if (onDirtyChange) {
      onDirtyChange(Boolean(isDirty));
    }
  }, [isDirty, onDirtyChange]);

  const bioLanguageOptions = TARGET_LANGUAGE_OPTIONS.map(opt => ({
    value: opt.value,
    label: `${opt.label} ${form.biographies?.[opt.value] ? '✓' : ''}`.trim()
  }));

  return (
    <form onSubmit={handleSave} className="custom-values-form settings-tab-content">
      <div className="custom-values-header">
        <h3 className="settings-section-title">Manual Overrides</h3>
        <p className="settings-section-subtitle">Set your own values for performer attributes. These take priority if manual routing is selected.</p>
      </div>

      <div className="custom-values-cards-grid">
        {/* Card 1: Profile & Identity */}
        <div className="custom-values-card">
          <div className="custom-values-card__header">
            <h4 className="custom-values-card__title">Profile & Identity</h4>
          </div>
          <div className="custom-values-card__body">
            <div className="ui-field custom-values-field--full">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <label className="ui-field__label" style={{ margin: 0 }}>Biography</label>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: '320px' }}>
                  <span style={{ fontSize: 'var(--font-size-sm, 12px)', color: 'var(--color-text-secondary)', whiteSpace: 'nowrap' }}>Language:</span>
                  <div style={{ flex: 1 }}>
                    <Dropdown
                      options={bioLanguageOptions}
                      value={selectedBioLang}
                      onChange={e => setSelectedBioLang(e.target.value)}
                      placeholder="Language"
                    />
                  </div>
                </div>
              </div>
              <textarea
                className="ui-input performer-custom-values-bio"
                value={form.biographies?.[selectedBioLang] || ''}
                onChange={e => {
                  const val = e.target.value;
                  setForm(prev => ({
                    ...prev,
                    biographies: {
                      ...prev.biographies,
                      [selectedBioLang]: val
                    }
                  }));
                }}
                placeholder={`Write a custom biography in ${TARGET_LANGUAGE_OPTIONS.find(o => o.value === selectedBioLang)?.label || selectedBioLang}...`}
              />
            </div>
            <div className="custom-values-card__grid-2">
              <Dropdown
                label="Gender"
                options={genderOptions}
                value={form.gender}
                onChange={e => handleChange('gender', e.target.value)}
                placeholder="- Select -"
              />
              <div className="ui-field">
                <label className="ui-field__label">Birthday</label>
                <Input
                  type="date"
                  value={form.birthday}
                  onChange={e => handleChange('birthday', e.target.value)}
                />
              </div>
              <div className="ui-field">
                <label className="ui-field__label">Place of Birth</label>
                <Input
                  type="text"
                  placeholder="e.g. Los Angeles, California"
                  value={form.place_of_birth}
                  onChange={e => handleChange('place_of_birth', e.target.value)}
                />
              </div>
              <Dropdown
                label="Same Sex Only"
                options={sameSexOnlyOptions}
                value={form.same_sex_only}
                onChange={e => handleChange('same_sex_only', e.target.value)}
                placeholder="- Select -"
              />
            </div>
          </div>
        </div>

        {/* Card 2: Features & Appearance */}
        <div className="custom-values-card">
          <div className="custom-values-card__header">
            <h4 className="custom-values-card__title">Features & Appearance</h4>
          </div>
          <div className="custom-values-card__body">
            <div className="custom-values-card__grid-2">
              <div className="ui-field">
                <label className="ui-field__label">Height (cm)</label>
                <Input
                  type="number"
                  placeholder="e.g. 170"
                  value={form.height}
                  onChange={e => handleChange('height', e.target.value)}
                  error={errors.height}
                />
              </div>
              <div className="ui-field">
                <label className="ui-field__label">Weight (kg)</label>
                <Input
                  type="number"
                  placeholder="e.g. 60"
                  value={form.weight}
                  onChange={e => handleChange('weight', e.target.value)}
                  error={errors.weight}
                />
              </div>
              <Dropdown
                label="Hair Color"
                options={getDropdownOptions(hairColorOptions, form.hair_color)}
                value={form.hair_color}
                onChange={e => handleChange('hair_color', e.target.value)}
                placeholder="- Select -"
                searchable
              />
              <Dropdown
                label="Eye Color"
                options={getDropdownOptions(eyeColorOptions, form.eye_color)}
                value={form.eye_color}
                onChange={e => handleChange('eye_color', e.target.value)}
                placeholder="- Select -"
                searchable
              />
              <Dropdown
                label="Ethnicity"
                options={getDropdownOptions(ethnicityOptions, form.ethnicity)}
                value={form.ethnicity}
                onChange={e => handleChange('ethnicity', e.target.value)}
                placeholder="- Select -"
                searchable
              />
            </div>
          </div>
        </div>

        {/* Card 3: Body & Measurements */}
        <div className="custom-values-card">
          <div className="custom-values-card__header">
            <h4 className="custom-values-card__title">Body & Measurements</h4>
          </div>
          <div className="custom-values-card__body">
            <div className="custom-values-card__grid-2">
              <div className="ui-field">
                <label className="ui-field__label">Measurements (Preview)</label>
                <Input
                  type="text"
                  placeholder="e.g. 34B-24-34"
                  value={computedMeasurements}
                  disabled
                />
              </div>
              <Dropdown
                label="Breast Type"
                options={breastTypeOptions}
                value={form.breast_type}
                onChange={e => handleChange('breast_type', e.target.value)}
                placeholder="- Select -"
              />
              <div className="ui-field">
                <label className="ui-field__label">Cup Size</label>
                <Input
                  type="text"
                  placeholder="e.g. B"
                  value={form.cup_size}
                  onChange={e => handleChange('cup_size', e.target.value.toUpperCase().replace(/[^A-Z]/g, ''))}
                  list="cup-size-options"
                  error={errors.cup_size}
                />
                <datalist id="cup-size-options">
                  {cupSizeOptions.map(opt => (
                    <option key={opt} value={opt} />
                  ))}
                </datalist>
              </div>
              <div className="ui-field">
                <label className="ui-field__label">Band Size</label>
                <Input
                  type="number"
                  placeholder="e.g. 34"
                  value={form.band_size}
                  onChange={e => handleChange('band_size', e.target.value.replace(/\D/g, ''))}
                  min={10}
                  max={100}
                  step={1}
                  error={errors.band_size}
                />
              </div>
              <div className="ui-field">
                <label className="ui-field__label">Waist (inches)</label>
                <Input
                  type="number"
                  placeholder="e.g. 24"
                  value={form.waist}
                  onChange={e => handleChange('waist', e.target.value.replace(/\D/g, ''))}
                  min={10}
                  max={100}
                  step={1}
                  error={errors.waist}
                />
              </div>
              <div className="ui-field">
                <label className="ui-field__label">Hip (inches)</label>
                <Input
                  type="number"
                  placeholder="e.g. 34"
                  value={form.hip}
                  onChange={e => handleChange('hip', e.target.value.replace(/\D/g, ''))}
                  min={10}
                  max={100}
                  step={1}
                  error={errors.hip}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Card 4: Modifications */}
        <div className="custom-values-card">
          <div className="custom-values-card__header">
            <h4 className="custom-values-card__title">Modifications</h4>
          </div>
          <div className="custom-values-card__body">
            <div className="custom-values-card__grid-2">
              <div className="ui-field custom-values-field--full-grid">
                <label className="ui-field__label">Tattoos</label>
                <Input
                  type="text"
                  placeholder="e.g. Rose on left shoulder"
                  value={form.tattoos}
                  onChange={e => handleChange('tattoos', e.target.value)}
                />
              </div>
              <div className="ui-field custom-values-field--full-grid">
                <label className="ui-field__label">Piercings</label>
                <Input
                  type="text"
                  placeholder="e.g. Nose ring"
                  value={form.piercings}
                  onChange={e => handleChange('piercings', e.target.value)}
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      <FloatingActionBar
        visible={Boolean(isDirty)}
        className={isShaking ? 'is-shaking' : ''}
        title={t('settingsPage.unsavedChanges.title')}
        actions={[
          {
            key: 'reset',
            label: 'Reset',
            onClick: handleReset,
            disabled: saveMutation.isPending,
          },
          {
            key: 'save',
            label: saveMutation.isPending ? 'Saving...' : 'Save Changes',
            onClick: handleSave,
            disabled: saveMutation.isPending || Object.keys(errors).length > 0,
            variant: 'primary',
          },
        ]}
      />
    </form>
  );
}
