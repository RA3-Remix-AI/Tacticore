function screenshotSize(bytes) {
  if (bytes[0] !== 0xff || bytes[1] !== 0xd8) throw new Error('Expected a JPEG capture');
  for (let offset = 2; offset + 8 < bytes.length;) {
    const marker = bytes[offset + 1];
    const length = bytes[offset + 2] * 256 + bytes[offset + 3];
    if (bytes[offset] !== 0xff || length < 2) break;
    if (marker === 0xc0 || marker === 0xc2) {
      return [bytes[offset + 7] * 256 + bytes[offset + 8], bytes[offset + 5] * 256 + bytes[offset + 6]];
    }
    offset += length + 2;
  }
  throw new Error('Could not read the capture dimensions');
}

function checkedImage(capture, expectedSize) {
  const images = Array.isArray(capture) ? capture : [{ bytes: capture }];
  if (images.length !== 1) throw new Error('Inspect the additional window before continuing');
  const image = images[0];
  const [width, height] = screenshotSize(image.bytes);
  if (width !== expectedSize[0] || height !== expectedSize[1]) {
    throw new Error("Window layout changed: captured " + width + "x" + height + ", expected " + expectedSize.join("x"));
  }
  return image;
}

// Each game operation starts from the named screen. Verify the returned
// picture before doing the next one because RA3 exposes only a window in AX.
function createSkirmishControls({ game, client }) {
  const gameSize = [2557, 1440];
  const clientSize = [1363, 931];
  const lobbyControls = {
    openSkirmishMenu: [[714, 650], [737, 655]],
    enterSkirmish: [[731, 761], [750, 765]],
    startVerifiedLobby: [[1651, 1349], [1680, 1354]],
    leaveLobby: [[772, 1347], [786, 1355]],
    selectInfinityIsle: [[531, 560], [550, 563]],
    openFourthSeatMenu: [[967, 1086], [974, 1091]],
    closeFourthSeat: [[409, 1137], [422, 1140]],
    assignRightSpawn: [[1293, 517], [1296, 519]],
    assignLeftSpawn: [[1125, 570], [1128, 572]],
    exitFromMainMenu: [[948, 1030], [971, 1034]],
  };

  async function gameDrag([from, to]) {
    const image = checkedImage(await game.getScreenshot(), gameSize);
    await game.drag(from, to, image.id ? { screenshotId: image.id } : undefined);
    await game.getAXState({ emit: false });
    return game.getScreenshot();
  }

  async function clickClient(point) {
    const image = checkedImage(await client.getScreenshot(), clientSize);
    await client.click(point, image.id ? { screenshotId: image.id } : undefined);
    return client.getAXState({ emit: false });
  }

  return {
    launchFromGameSettings() {
      return clickClient([1242, 478]);
    },

    openMatchPage() {
      return clickClient([79, 203]);
    },

    async armModelFromMatchPage(fallbackPoint) {
      const observation = await client.getAXState({ disableDiffing: true, emit: false });
      const matches = [...observation.matchAll(/^\s*(\d+) button \(按钮\) 进入对局后自动开始(?: |$)/gm)];
      if (matches.length !== 1 || /取消等待|弈核 AI 正在指挥/.test(observation)) {
        throw new Error('The match page is not ready to arm a new model run');
      }
      try {
        await client.click(Number(matches[0][1]));
      } catch (error) {
        if (!String(error).includes('coordinate input geometry is unavailable') || !fallbackPoint) throw error;
        // The client reported no usable geometry, so it sent no click. Use the
        // observed button coordinate when the AX node cannot receive input.
        await clickClient(fallbackPoint);
      }
      const armed = await client.getAXState({ disableDiffing: true, emit: false });
      if (!armed.includes('取消等待')) throw new Error('The client did not enter the opening wait state');
      return armed;
    },

    gameStep(screen) {
      if (!Object.hasOwn(lobbyControls, screen)) throw new Error("Unknown game screen: " + screen);
      return gameDrag(lobbyControls[screen]);
    },

    leaveVerifiedSettlement({ resultConfirmed, controlReturned }) {
      if (resultConfirmed !== true || controlReturned !== true) {
        throw new Error('Confirm the settlement and native control state before leaving');
      }
      return gameDrag(lobbyControls.leaveLobby);
    },
  };
}

if (typeof module !== 'undefined') module.exports = { createSkirmishControls, screenshotSize };
