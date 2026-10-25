import test from "node:test";
import assert from "node:assert/strict";
import {
  defaultPreparation,
  exportPreparation,
  loadPreparation,
  preparationStorageKey,
  savePreparation,
  validatePreparation,
} from "../src/state/preparation.ts";

test("preparation distinguishes game funds from independent host production and reserve limits", () => {
  for (const [startingFunds, productionLimit, reserveFloor] of [
    [0, 220, 10000],
    [1000000, 10000, 500],
    [5000, 10000, 10000],
  ]) {
    assert.equal(
      validatePreparation({
        ...defaultPreparation,
        startingFunds,
        productionLimit,
        reserveFloor,
      }),
      null,
    );
  }
  for (const patch of [
    { startingFunds: -1 },
    { startingFunds: 1000001 },
    { startingFunds: 1.5 },
    { productionLimit: 219 },
    { productionLimit: 10001 },
    { productionLimit: Number.NaN },
    { reserveFloor: 499 },
    { reserveFloor: 10001 },
    { playerSlot: 16 },
    { playerSlot: -1 },
    { playerSlot: true },
    { map: " " },
    { map: "x".repeat(61) },
    { revision: 0 },
    { relationship: "secret" },
    { faction: "invalid" },
  ])
    assert.ok(
      validatePreparation({ ...defaultPreparation, ...patch } as never),
    );
});

test("saved local preparation restores after reload and excludes unknown sensitive fields", () => {
  const memory = new Map<string, string>();
  const storage = {
    getItem: (key: string) => memory.get(key) ?? null,
    setItem: (key: string, value: string) => {
      memory.set(key, value);
    },
  };
  const plan = {
    ...defaultPreparation,
    map: "  自定义地图  ",
    startingFunds: 20000,
    revision: 4,
    apiKey: "do-not-save",
    endpoint: "https://private.example",
  };
  const saved = savePreparation(
    storage,
    plan,
    new Date("2026-10-25T09:00:00Z"),
  );
  assert.equal(saved.plan.map, "自定义地图");
  assert.deepEqual(loadPreparation(storage), saved);
  assert.equal(
    memory.get(preparationStorageKey)?.includes("do-not-save"),
    false,
  );
  assert.equal(
    memory.get(preparationStorageKey)?.includes("private.example"),
    false,
  );
  assert.equal(loadPreparation(storage).plan.startingFunds, 20000);
});

test("invalid or unavailable preparation storage falls back to an unsaved default", () => {
  for (const raw of [
    "broken",
    "null",
    JSON.stringify({
      plan: { ...defaultPreparation, schemaVersion: 99 },
      savedAt: new Date().toISOString(),
    }),
    JSON.stringify({
      plan: { ...defaultPreparation, productionLimit: false },
      savedAt: new Date().toISOString(),
    }),
    JSON.stringify({ plan: defaultPreparation, savedAt: "not-a-date" }),
  ]) {
    assert.deepEqual(loadPreparation({ getItem: () => raw }), {
      plan: defaultPreparation,
      savedAt: null,
    });
  }
  assert.equal(
    loadPreparation({
      getItem: () => {
        throw Error("denied");
      },
    }).savedAt,
    null,
  );
  assert.throws(
    () =>
      savePreparation(
        {
          setItem: () => {
            throw Error("quota");
          },
        },
        defaultPreparation,
      ),
    /quota/,
  );
  assert.throws(() =>
    savePreparation(
      { setItem: () => {} },
      { ...defaultPreparation, reserveFloor: 0 },
    ),
  );
});

test("exported preparation is a non-executable plan with no credential or host command fields", () => {
  const document = exportPreparation(
    { ...defaultPreparation, apiKey: "secret-value" } as never,
    { id: "local-iron", name: "铁锤", key: "commander-secret" } as never,
  );
  assert.equal(document.scope, "prepared_plan_only");
  assert.equal(document.executionAuthorized, false);
  assert.equal(document.gameValuesVerified, false);
  assert.deepEqual(document.commander, {
    localProfileId: "local-iron",
    name: "铁锤",
  });
  const raw = JSON.stringify(document);
  assert.equal(raw.includes("secret-value"), false);
  assert.equal(raw.includes("commander-secret"), false);
  assert.equal(raw.includes("--execute"), false);
  assert.throws(() =>
    exportPreparation(
      { ...defaultPreparation, startingFunds: Number.POSITIVE_INFINITY },
      { id: "local-iron", name: "铁锤" },
    ),
  );
});
