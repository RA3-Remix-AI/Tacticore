/** First-run wizard state. Pure, so the step logic is testable without React. */
import type {PlayMode} from './playMode';

export type WizardStepId = 'game' | 'model' | 'mode';

export interface WizardInput {
  gamePrepared: boolean;
  configurationReady: boolean;
  /** null when not known yet (no connection loaded). */
  credentialSaved: boolean | null;
  mode: PlayMode | null;
}

export interface WizardStep {id: WizardStepId; number: number; title: string; done: boolean; hint: string}

export function wizardSteps(input: WizardInput): WizardStep[] {
  return [
    {
      id: 'game', number: 1, title: '游戏与 Mod', done: input.gamePrepared,
      hint: input.gamePrepared ? '游戏和 Mod 已准备好' : '选择 RA3 1.12 和兼容 Mod',
    },
    {
      id: 'model', number: 2, title: '模型与 API Key', done: input.configurationReady,
      hint: !input.configurationReady ? '填写模型服务和 API Key'
        : input.credentialSaved === false ? '已保存；尚未填写 API Key' : '模型设置已保存',
    },
    {
      id: 'mode', number: 3, title: '对局模式', done: input.mode !== null,
      hint: input.mode ? '已选择玩法' : '选择观战、并肩作战或挑战 AI',
    },
  ];
}

export function firstIncompleteStep(input: WizardInput): WizardStepId | null {
  return wizardSteps(input).find(step => !step.done)?.id ?? null;
}

export function canFinishWizard(input: WizardInput): boolean {
  return firstIncompleteStep(input) === null;
}

export function nextStep(current: WizardStepId): WizardStepId | null {
  return current === 'game' ? 'model' : current === 'model' ? 'mode' : null;
}

export function previousStep(current: WizardStepId): WizardStepId | null {
  return current === 'mode' ? 'model' : current === 'model' ? 'game' : null;
}

/**
 * The wizard is a first-run screen only. A run that still holds the game is
 * always shown on the main screen so that Stop stays one click away.
 */
export function showWizard(options: {completed: boolean; runHoldsGame: boolean}): boolean {
  return !options.completed && !options.runHoldsGame;
}
