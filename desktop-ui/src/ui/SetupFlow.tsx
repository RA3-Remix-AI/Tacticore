import type {ReactNode} from 'react';
import {ArrowLeft, ArrowRight, Check} from '@phosphor-icons/react';
import {Button} from '../components/ui';
import {canFinishWizard, nextStep, previousStep, wizardSteps, type WizardInput, type WizardStepId} from '../runtime/wizard';

export type SetupTab = WizardStepId | 'style';

/**
 * Hosts the three setup panels. The panels are always mounted (only hidden),
 * because they report game and configuration state the main screen depends on.
 */
export function SetupFlow({variant, tab, onTab, input, onFinish, game, model, mode, style}: {
  variant: 'wizard' | 'settings'; tab: SetupTab; onTab: (tab: SetupTab) => void; input: WizardInput;
  onFinish: () => void; game: ReactNode; model: ReactNode; mode: ReactNode; style: ReactNode;
}) {
  const steps = wizardSteps(input);
  const current = steps.find(step => step.id === tab);
  const next = tab === 'style' ? null : nextStep(tab);
  const previous = tab === 'style' ? null : previousStep(tab);
  return <div className={`tc-setup tc-setup-${variant}`}>
    <nav className="tc-stepper" aria-label={variant === 'wizard' ? '设置步骤' : '设置'}>
      {steps.map(step => <button type="button" key={step.id} aria-current={tab === step.id ? 'step' : undefined}
        className={`tc-stepper-item ${step.done ? 'is-done' : ''}`} onClick={() => onTab(step.id)}>
        <span className="tc-stepper-number">{step.done ? <Check size={14} weight="bold" aria-hidden="true" /> : step.number}</span>
        <span><strong>{step.title}</strong><small>{step.hint}</small></span>
      </button>)}
      {variant === 'settings' && <button type="button" aria-current={tab === 'style' ? 'step' : undefined}
        className="tc-stepper-item" onClick={() => onTab('style')}>
        <span className="tc-stepper-number">+</span>
        <span><strong>指挥官</strong><small>人物与性格</small></span>
      </button>}
    </nav>
    <div hidden={tab !== 'game'}>{game}</div>
    <div hidden={tab !== 'model'}>{model}</div>
    <div hidden={tab !== 'mode'}>{mode}</div>
    <div hidden={tab !== 'style'}>{style}</div>
    {variant === 'wizard' && <div className="tc-wizard-nav">
      {previous ? <Button onClick={() => onTab(previous)}><ArrowLeft size={16} /> 上一步</Button> : <span />}
      {next
        ? <Button kind="primary" disabled={!current?.done} onClick={() => onTab(next)}>下一步 <ArrowRight size={16} /></Button>
        : <Button kind="primary" disabled={!canFinishWizard(input)} onClick={onFinish}>完成，进入对局 <ArrowRight size={16} /></Button>}
    </div>}
  </div>;
}
