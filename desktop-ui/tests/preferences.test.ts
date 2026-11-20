import test from "node:test";
import assert from "node:assert/strict";
import {
  commanderPreview,
  commanderStyleName,
  preferenceAxes,
  preferencePresets,
  preferenceSummary,
  profilePreferences,
  validatePreferences,
  type StyleSubject,
} from "../src/state/preferences.ts";

test("four product presets are valid and cover the three backend personalities", () => {
  assert.equal(preferencePresets.length, 4);
  for (const preset of preferencePresets) {
    const subject: StyleSubject = { doctrine: preset.doctrine, preferences: { ...preset.values } };
    assert.equal(validatePreferences(subject.preferences), null);
    assert.equal(commanderStyleName(subject), preset.label);
  }
  assert.deepEqual(
    [...new Set(preferencePresets.map((preset) => preset.doctrine))].sort(),
    ["assault", "defense", "maneuver"],
  );
});

test("profiles without preferences derive deterministic defaults without mutation", () => {
  for (const doctrine of ["assault", "defense", "maneuver"] as const) {
    const subject: StyleSubject = { doctrine };
    const before = JSON.stringify(subject);
    const derived = profilePreferences(subject);
    assert.equal(validatePreferences(derived), null);
    derived.attack = 5;
    assert.equal(JSON.stringify(subject), before);
    const preset = preferencePresets.find((row) => row.doctrine === doctrine)!;
    assert.equal(profilePreferences(subject).attack, preset.values.attack);
  }
});

test("custom edits change summaries and previews", () => {
  const subject: StyleSubject = { doctrine: "defense", preferences: { ...preferencePresets[1].values } };
  const before = commanderPreview(subject);
  subject.preferences = { preset: "custom", attack: 5, risk: 1, economy: 5, scouting: 5, pursuit: 1 };
  assert.equal(validatePreferences(subject.preferences), null);
  assert.equal(commanderStyleName(subject), "自定义风格");
  assert.notDeepEqual(commanderPreview(subject), before);
  assert.equal(commanderPreview(subject).length, 3);
  for (const axis of preferenceAxes) {
    assert.ok(preferenceSummary(subject).includes(axis.descriptions[subject.preferences[axis.key] - 1]));
  }
});

test("invalid, fractional and forged preset preferences are rejected", () => {
  for (const invalid of [0, 6, 1.5, NaN, Infinity, "3", null]) {
    assert.ok(validatePreferences({ ...preferencePresets[2].values, attack: invalid as never }));
    const subject: StyleSubject = {
      doctrine: "assault",
      preferences: { ...preferencePresets[2].values, attack: invalid as never },
    };
    // A malformed saved draft falls back to the doctrine preset.
    assert.equal(validatePreferences(profilePreferences(subject)), null);
    assert.equal(profilePreferences(subject).attack, 4);
  }
  assert.ok(validatePreferences({ ...preferencePresets[0].values, attack: 5 }));
  assert.ok(validatePreferences({ ...preferencePresets[0].values, preset: ["steady"] }));
});

test("public preferences drop unexpected nested fields", () => {
  const preferences = Object.assign({ ...preferencePresets[3].values }, {
    apiKey: "must-not-be-kept",
    nested: { key: "another-secret" },
  });
  const derived = profilePreferences({ doctrine: "maneuver", preferences });
  assert.ok(!JSON.stringify(derived).includes("must-not-be-kept"));
  assert.deepEqual(derived, preferencePresets[3].values);
});
