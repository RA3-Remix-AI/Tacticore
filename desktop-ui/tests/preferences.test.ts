import test from "node:test";
import assert from "node:assert/strict";
import {
  defaultSettings,
  loadSettings,
  publicSettings,
  saveSettings,
} from "../src/state/settings.ts";
import {
  commanderPlan,
  commanderPreview,
  commanderStyleName,
  preferenceAxes,
  preferencePresets,
  preferenceSummary,
  profilePreferences,
  validatePreferences,
} from "../src/state/preferences.ts";

test("four product presets map to the existing three personalities without creating a fourth", () => {
  assert.equal(preferencePresets.length, 4);
  const personalities = new Set<number>();
  for (const preset of preferencePresets) {
    const profile = {
      ...defaultSettings.commanders[0],
      doctrine: preset.doctrine,
      preferences: { ...preset.values },
    };
    assert.equal(validatePreferences(profile.preferences), null);
    assert.equal(commanderStyleName(profile), preset.label);
    const plan = commanderPlan(profile);
    personalities.add(plan.personality);
    assert.ok([0, 1, 2].includes(plan.personality));
    assert.equal(plan.appliedToHost, false);
    assert.equal(plan.scope, "local_preference_draft");
    assert.equal(plan.customTraits, profile.traits);
  }
  assert.deepEqual([...personalities].sort(), [0, 1, 2]);
});

test("existing three-doctrine profiles gain deterministic preferences without mutation", () => {
  for (const profile of defaultSettings.commanders) {
    const before = JSON.stringify(profile);
    const derived = profilePreferences(profile);
    assert.equal(validatePreferences(derived), null);
    derived.attack = 5;
    assert.equal(JSON.stringify(profile), before);
    assert.notEqual(profilePreferences(profile).attack, 5);
  }
});

test("five-step edits change summaries and scenario previews while preserving custom text", () => {
  const profile = {
    ...defaultSettings.commanders[0],
    preferences: { ...preferencePresets[1].values },
  };
  const before = commanderPreview(profile);
  profile.preferences = {
    preset: "custom",
    attack: 5,
    risk: 1,
    economy: 5,
    scouting: 5,
    pursuit: 1,
  };
  assert.equal(validatePreferences(profile.preferences), null);
  assert.equal(commanderStyleName(profile), "自定义风格");
  assert.notDeepEqual(commanderPreview(profile), before);
  assert.equal(commanderPreview(profile).length, 3);
  for (const axis of preferenceAxes) {
    assert.ok(
      preferenceSummary(profile).includes(
        axis.descriptions[profile.preferences[axis.key] - 1],
      ),
    );
  }
  assert.equal(
    commanderPlan(profile).customTraits,
    defaultSettings.commanders[0].traits,
  );
});

test("invalid, fractional and forged preset preferences cannot be saved or accepted as a loaded draft", () => {
  for (const invalid of [0, 6, 1.5, NaN, Infinity, "3", null]) {
    const settings = structuredClone(defaultSettings);
    settings.commanders[0].preferences = {
      ...preferencePresets[2].values,
      attack: invalid as never,
    };
    assert.ok(validatePreferences(settings.commanders[0].preferences));
    let written = false;
    assert.throws(() =>
      saveSettings(
        {
          setItem: () => {
            written = true;
          },
        },
        settings,
      ),
    );
    assert.equal(written, false);
    const restored = loadSettings({ getItem: () => JSON.stringify(settings) });
    assert.equal(
      validatePreferences(profilePreferences(restored.commanders[0])),
      null,
    );
    assert.equal(profilePreferences(restored.commanders[0]).attack, 4);
  }
  assert.ok(validatePreferences({ ...preferencePresets[0].values, attack: 5 }));
  assert.ok(
    validatePreferences({ ...preferencePresets[0].values, preset: ["steady"] }),
  );
});

test("structured preferences persist through settings whitelist without accidental nested secrets", () => {
  const settings = structuredClone(defaultSettings);
  settings.commanders[0].preferences = { ...preferencePresets[3].values };
  settings.commanders[0].doctrine = "maneuver";
  Object.assign(settings.commanders[0].preferences, {
    apiKey: "must-not-be-persisted",
    nested: { key: "another-secret" },
  });
  const serialized = JSON.stringify(publicSettings(settings));
  assert.ok(!serialized.includes("must-not-be-persisted"));
  assert.ok(!serialized.includes("another-secret"));
  const restored = loadSettings({ getItem: () => serialized });
  assert.deepEqual(
    restored.commanders[0].preferences,
    preferencePresets[3].values,
  );
  assert.equal(commanderPlan(restored.commanders[0]).personalityName, "raider");
});

test("named presets cannot be persisted with a different backend personality", () => {
  const settings = structuredClone(defaultSettings);
  settings.commanders[0].preferences = { ...preferencePresets[0].values };
  assert.equal(settings.commanders[0].doctrine, "assault");
  let written = false;
  assert.throws(
    () =>
      saveSettings(
        {
          setItem: () => {
            written = true;
          },
        },
        settings,
      ),
    /人格与打法预设不一致/,
  );
  assert.equal(written, false);
  const recovered = loadSettings({ getItem: () => JSON.stringify(settings) });
  assert.equal(profilePreferences(recovered.commanders[0]).preset, "pressure");
  settings.commanders[0].preferences.preset = "custom";
  assert.doesNotThrow(() => saveSettings({ setItem: () => {} }, settings));
});
