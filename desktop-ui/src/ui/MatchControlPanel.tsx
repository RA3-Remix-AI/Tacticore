import {Play, Stop, ArrowClockwise, HourglassMedium, MagnifyingGlass, GearSix} from '@phosphor-icons/react';
import {Button} from '../components/ui';
import type {ControlAction, ControlView} from '../runtime/matchControl';

const actionIcon: Partial<Record<ControlAction, typeof Play>> = {
  start: Play, stop: Stop, refresh: ArrowClockwise, cancel_wait: HourglassMedium, discover: MagnifyingGlass,
  open_setup: GearSix, open_model: GearSix, open_style: GearSix,
};

/** One primary action plus a plain status line. Secondary actions stay small. */
export function MatchControlPanel({control, notice, onAction, secondary, footnote}: {
  control: ControlView; notice: string | null; onAction: (action: ControlAction) => void;
  secondary?: React.ReactNode; footnote?: string | null;
}) {
  const Icon = actionIcon[control.primary.action];
  const kind = control.primary.tone === 'danger' ? 'danger' : control.primary.tone === 'primary' ? 'primary' : '';
  return <section className={`native-panel tc-control is-${control.phase}`} aria-live="polite">
    <div className="tc-control-status">
      <span className={`tc-pill ${control.live ? 'is-live' : ''}`}>{control.status}</span>
    </div>
    <h2>{control.title}</h2>
    <p className="tc-control-detail">{control.detail}</p>
    {notice && <p role="status" className="tc-control-notice">{notice}</p>}
    <div className="tc-control-actions">
      <Button kind={kind} className="tc-primary-action" disabled={control.primary.disabled || control.primary.action === 'none'}
        onClick={() => onAction(control.primary.action)}>
        {Icon && <Icon size={18} weight="bold" aria-hidden="true" />}
        {control.primary.label}
      </Button>
      {secondary}
    </div>
    {footnote && <p className="native-muted">{footnote}</p>}
  </section>;
}
