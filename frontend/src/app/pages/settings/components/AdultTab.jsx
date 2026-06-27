import Stack from '@/ui/Stack';
import { useSettingsField, useSettingsViewContext } from '../SettingsFormContext.jsx';
import SettingsSectionRenderer from './SettingsSectionRenderer.jsx';
import {
  createAdultGeneralSection,
  createAdultStashdbSection,
  createAdultFansdbSection,
  createAdultTheporndbSection,
} from '../settingsSectionConfigs.jsx';

export default function AdultTab() {
  const { adultGenderPreferenceOptions, t } = useSettingsViewContext();
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
