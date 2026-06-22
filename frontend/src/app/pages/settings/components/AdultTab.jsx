import Stack from '@/ui/Stack';
import { useSettingsField, useSettingsViewContext, useSettingsFormContext } from '../SettingsFormContext.jsx';
import SettingsSectionRenderer from './SettingsSectionRenderer.jsx';
import {
  createAdultGeneralSection,
  createAdultStashdbSection,
  createAdultFansdbSection,
  createAdultTheporndbSection,
} from '../settingsSectionConfigs.jsx';

export default function AdultTab({ form, setForm }) {
  const { adultGenderPreferenceOptions, t } = useSettingsViewContext();
  const { renderContext } = useSettingsFormContext();
  const includeAdultField = useSettingsField('include_adult');
  const context = { include_adult: includeAdultField.checked };

  return (
    <Stack gap="xl">
      <SettingsSectionRenderer
        section={createAdultGeneralSection(t, adultGenderPreferenceOptions)}
        context={context}
      />
      {includeAdultField.checked && (
        <>
          <SettingsSectionRenderer
            section={createAdultStashdbSection(t)}
            context={context}
          />
          <SettingsSectionRenderer
            section={createAdultFansdbSection(t)}
            context={context}
          />
          <SettingsSectionRenderer
            section={createAdultTheporndbSection(t)}
            context={context}
          />
        </>
      )}
    </Stack>
  );
}
