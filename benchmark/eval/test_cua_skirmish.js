const { test } = require('node:test');
const assert = require('node:assert/strict');
const { createSkirmishControls } = require('./cua_skirmish');

function capture(width, height) {
  return Uint8Array.of(0xff, 0xd8, 0xff, 0xc0, 0, 7, 8, height >> 8, height & 255, width >> 8, width & 255);
}

test('the game uses the observed window and one control per screen', async () => {
  const drags = [];
  let frames = 0;
  const game = {
    getScreenshot: async () => {
      frames += 1;
      return [{ id: 'game-window', bytes: capture(2557, 1440) }];
    },
    getAXState: async () => '',
    drag: async (...args) => drags.push(args),
  };
  const controls = createSkirmishControls({ game });
  await controls.gameStep('openSkirmishMenu');
  await controls.gameStep('enterSkirmish');
  assert.equal(frames, 4);
  assert.deepEqual(drags, [
    [[714, 650], [737, 655], { screenshotId: 'game-window' }],
    [[731, 761], [750, 765], { screenshotId: 'game-window' }],
  ]);
});

test('a changed capture size leaves the game untouched', async () => {
  const game = {
    getScreenshot: async () => capture(1920, 1080),
    drag: () => assert.fail('a different display layout must stop the configured sequence'),
  };
  await assert.rejects(createSkirmishControls({ game }).gameStep('startVerifiedLobby'), /Window layout changed/);
});

test('arms a model match only from a ready client and checks that it is waiting', async () => {
  const client = {
    getAXState: async () => '  2461 button (按钮) 进入对局后自动开始 Description: 等待',
    click: async (index) => {
      assert.equal(index, 2461);
      client.getAXState = async () => '提取对局中\n48 button (按钮) 取消等待';
    },
  };
  assert.match(await createSkirmishControls({ client }).armModelFromMatchPage(), /取消等待/);
  client.getAXState = async () => '弈核 AI 正在指挥';
  client.click = () => assert.fail('an active run must not arm a second model');
  await assert.rejects(createSkirmishControls({ client }).armModelFromMatchPage(), /not ready/);
});

test('falls back to an observed client coordinate only on the known AX geometry failure', async () => {
  const client = {
    getAXState: async () => '  2461 button (按钮) 进入对局后自动开始',
    getScreenshot: async () => [{ id: 'client-window', bytes: capture(1363, 931) }],
    click: async (target, options) => {
      if (target === 2461) throw new Error('coordinate input geometry is unavailable');
      assert.deepEqual(target, [487, 369]);
      assert.deepEqual(options, { screenshotId: 'client-window' });
      client.getAXState = async () => '取消等待';
    },
  };
  assert.match(await createSkirmishControls({ client }).armModelFromMatchPage([487, 369]), /取消等待/);
  client.getAXState = async () => '  2461 button (按钮) 进入对局后自动开始';
  client.click = async (index) => {
    assert.equal(index, 2461);
    throw new Error('Input status unknown');
  };
  await assert.rejects(createSkirmishControls({ client }).armModelFromMatchPage([487, 369]), /Input status unknown/);
});

test('leaving the settlement requires result and control confirmation', async () => {
  const drags = [];
  const game = {
    getScreenshot: async () => capture(2557, 1440),
    getAXState: async () => '',
    drag: async (from, to) => drags.push([from, to]),
  };
  const controls = createSkirmishControls({ game });
  assert.throws(() => controls.leaveVerifiedSettlement({ resultConfirmed: true }), /native control state/);
  assert.deepEqual(drags, []);
  await controls.leaveVerifiedSettlement({ resultConfirmed: true, controlReturned: true });
  assert.deepEqual(drags, [[[772, 1347], [786, 1355]]]);
});
