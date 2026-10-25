import test from "node:test";
import assert from "node:assert/strict";
import {
  builtinClips,
  defaultRadioPreferences,
  MAX_CLIP_BYTES,
  sameRadioPreferences,
  validateClip,
  validateLibraryAddition,
  validPreferences,
  type RadioClip,
} from "../src/radio/model.ts";
import {
  advanceRadio,
  createRadioSchedule,
  discardClip,
  enqueueRadio,
} from "../src/radio/scheduler.ts";

const clips = builtinClips("iron");
const clip = (event: RadioClip["event"]) =>
  clips.find((c) => c.event === event)!;
const preferences = { ...defaultRadioPreferences };
test("critical radio interrupts low-priority messages and stale celebration is discarded", () => {
  let state = enqueueRadio(
    createRadioSchedule("match-a"),
    "match-a",
    clip("opening"),
    preferences,
    1000,
  ).state;
  state = enqueueRadio(
    state,
    "match-a",
    clip("rescue"),
    preferences,
    1100,
  ).state;
  assert.equal(state.current?.event, "rescue");
  state = enqueueRadio(
    state,
    "match-a",
    clip("victory"),
    preferences,
    1200,
  ).state;
  assert.equal(state.current?.event, "victory");
  state = enqueueRadio(
    state,
    "match-a",
    clip("crisis"),
    preferences,
    1300,
  ).state;
  assert.equal(state.current?.event, "crisis");
  assert.equal(
    state.queue.some((c) => c.event === "victory" || c.event === "rescue"),
    false,
  );
  state = enqueueRadio(
    state,
    "match-a",
    clip("defeat"),
    preferences,
    1400,
  ).state;
  assert.equal(state.current?.event, "defeat");
  assert.equal(state.queue.length, 0);
});
test("duplicate events merge, cooldown is frequency-specific and audition can bypass it", () => {
  let state = enqueueRadio(
    createRadioSchedule("a"),
    "a",
    clip("loss"),
    preferences,
    10,
  ).state;
  assert.equal(
    enqueueRadio(state, "a", clip("loss"), preferences, 11).accepted,
    false,
  );
  state = advanceRadio(state, 100);
  assert.equal(
    enqueueRadio(state, "a", clip("loss"), preferences, 40_000).accepted,
    false,
  );
  assert.equal(
    enqueueRadio(
      state,
      "a",
      clip("loss"),
      { ...preferences, frequency: "active" },
      40_000,
    ).accepted,
    true,
  );
  assert.equal(
    enqueueRadio(state, "a", clip("loss"), preferences, 1000, "audition")
      .accepted,
    true,
  );
});
test("a cooldown-suppressed crisis still invalidates outdated celebration", () => {
  let state = enqueueRadio(
    createRadioSchedule("a"),
    "a",
    clip("crisis"),
    preferences,
    0,
  ).state;
  state = advanceRadio(state, 100);
  state = enqueueRadio(state, "a", clip("rescue"), preferences, 200).state;
  assert.equal(state.current?.event, "rescue");
  const result = enqueueRadio(state, "a", clip("crisis"), preferences, 300);
  assert.equal(result.accepted, false);
  assert.equal(result.state.current, null);
  assert.equal(result.state.queue.length, 0);
});
test("new preview epochs cannot reuse a stale delivery identity", () => {
  const a = enqueueRadio(
    createRadioSchedule("same"),
    "same",
    clip("opening"),
    preferences,
    0,
  ).state;
  const b = enqueueRadio(
    createRadioSchedule("same"),
    "same",
    clip("opening"),
    preferences,
    0,
  ).state;
  assert.notEqual(a.current?.id, b.current?.id);
});
test("expired playback cannot leave an orphan queue when a new event is suppressed", () => {
  let state = enqueueRadio(
    createRadioSchedule("a"),
    "a",
    clip("crisis"),
    preferences,
    0,
  ).state;
  state = enqueueRadio(state, "a", clip("opening"), preferences, 11_000).state;
  assert.equal(state.queue.length, 1);
  const result = enqueueRadio(state, "a", clip("crisis"), preferences, 15_000);
  assert.equal(result.accepted, false);
  assert.equal(result.state.current, null);
  assert.equal(result.state.queue.length, 0);
});
test("a saved preference snapshot only matches the same current public values", () => {
  const saved = { ...preferences };
  assert.equal(sameRadioPreferences(saved, { ...saved }), true);
  for (const changed of [
    { ...saved, volume: 5 },
    { ...saved, muted: true },
    { ...saved, subtitlesOnly: true },
    { ...saved, frequency: "quiet" as const },
  ])
    assert.equal(sameRadioPreferences(saved, changed), false);
});
test("late events cannot cross a session and expired queued content is never played", () => {
  let state = enqueueRadio(
    createRadioSchedule("new"),
    "new",
    clip("crisis"),
    preferences,
    100,
  ).state;
  const rejected = enqueueRadio(
    state,
    "old",
    clip("opening"),
    preferences,
    110,
  );
  assert.equal(rejected.accepted, false);
  assert.equal(rejected.state, state);
  state = enqueueRadio(state, "new", clip("opening"), preferences, 120).state;
  assert.equal(state.queue.length, 1);
  state = advanceRadio(state, 40_000);
  assert.equal(state.current, null);
  assert.equal(state.queue.length, 0);
  assert.equal(createRadioSchedule("next").current, null);
});
test("quiet mode skips ambience while keeping urgent subtitles even when muted", () => {
  const quiet = {
    ...preferences,
    frequency: "quiet" as const,
    muted: true,
    subtitlesOnly: true,
  };
  const state = createRadioSchedule("a");
  assert.equal(
    enqueueRadio(state, "a", clip("opening"), quiet, 100).accepted,
    false,
  );
  assert.equal(
    enqueueRadio(state, "a", clip("rescue"), quiet, 100).accepted,
    false,
  );
  assert.equal(
    enqueueRadio(state, "a", clip("crisis"), quiet, 100).accepted,
    true,
  );
});
test("deleting the playing clip releases it and removes its queued instances", () => {
  let state = enqueueRadio(
    createRadioSchedule("a"),
    "a",
    clip("crisis"),
    preferences,
    0,
  ).state;
  state = enqueueRadio(state, "a", clip("opening"), preferences, 10).state;
  state = discardClip(state, clip("crisis").id, 20);
  assert.equal(state.current?.event, "opening");
  assert.equal(state.queue.length, 0);
});
test("local assets and preference boundaries reject unsupported, oversized and corrupted values", () => {
  assert.equal(validateClip(clip("opening")), null);
  assert.ok(
    validateClip({
      ...clip("opening"),
      title: undefined,
    } as unknown as RadioClip),
  );
  assert.ok(validateClip({ ...clip("opening"), text: "" }));
  assert.ok(
    validateClip({
      ...clip("opening"),
      mediaType: "video",
      blob: new Blob(["invalid"], { type: "text/html" }),
      durationSeconds: 1,
    }),
  );
  assert.ok(
    validateClip({
      ...clip("opening"),
      mediaType: "audio",
      blob: new Blob([new Uint8Array(MAX_CLIP_BYTES + 1)], {
        type: "audio/wav",
      }),
      durationSeconds: 1,
    }),
  );
  const custom = { ...clip("opening"), id: "custom", builtin: false };
  assert.ok(
    validateLibraryAddition(
      Array.from({ length: 24 }, (_, index) => ({
        ...custom,
        id: `c${index}`,
      })),
      custom,
    ),
  );
  assert.equal(validPreferences(preferences), true);
  assert.equal(validPreferences({ ...preferences, volume: Number.NaN }), false);
  assert.equal(validPreferences({ ...preferences, volume: 101 }), false);
  assert.equal(
    validPreferences({ ...preferences, frequency: "unbounded" }),
    false,
  );
});
