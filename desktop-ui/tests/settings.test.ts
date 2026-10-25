import test from "node:test";
import assert from "node:assert/strict";
import {
  defaultSettings,
  loadSettings,
  saveSettings,
  storageKey,
  validateConnection,
} from "../src/state/settings.ts";
test("saved demonstration settings exclude credentials and recover across sessions", () => {
  const memory = new Map<string, string>();
  const storage = {
    setItem: (key: string, value: string) => memory.set(key, value),
    getItem: (key: string) => memory.get(key) ?? null,
  };
  const value = structuredClone(defaultSettings);
  value.commanders[0].name = "测试指挥官";
  Object.assign(value.connections[0], {
    key: "sensitive-test-value",
    apiKey: "another-secret",
  });
  saveSettings(storage, value);
  assert.equal(memory.get(storageKey)?.includes("sensitive-test-value"), false);
  assert.equal(memory.get(storageKey)?.includes("another-secret"), false);
  assert.equal(loadSettings(storage).commanders[0].name, "测试指挥官");
});
test("malformed or incompatible saved settings safely restore usable defaults", () => {
  for (const raw of [
    "broken",
    "null",
    '{"schemaVersion":99}',
    JSON.stringify({ ...defaultSettings, activeId: "missing" }),
    JSON.stringify({ ...defaultSettings, connections: [] }),
  ]) {
    assert.equal(loadSettings({ getItem: () => raw }).commanders[0].id, "iron");
  }
  assert.equal(
    loadSettings({
      getItem: () => {
        throw new Error("blocked");
      },
    }).connections.length,
    2,
  );
});
test("connection format blocks embedded credentials and external plain HTTP without making requests", () => {
  const connection = defaultSettings.connections[0];
  for (const endpoint of [
    "http://example.com",
    "https://user:pass@example.com",
    "https://example.com?api_key=value",
    "https://example.com/v1/chat/completions",
    "bad-url",
  ])
    assert.ok(validateConnection({ ...connection, endpoint }));
  for (const endpoint of ["https://example.com/v1", "http://127.0.0.1:8000/v1"])
    assert.equal(validateConnection({ ...connection, endpoint }), null);
});
