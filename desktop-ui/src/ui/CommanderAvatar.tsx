/** A commander's portrait, or the first character of the name when there is no portrait (custom or unknown). */
export function CommanderAvatar({commander, size = 32}: {commander: {name: string; portrait: string | null}; size?: number}) {
  return commander.portrait
    ? <img className="tc-avatar" src={commander.portrait} alt={commander.name} width={size} height={size} />
    : <span className="tc-avatar is-empty" style={{width: size, height: size}} aria-hidden="true">{commander.name.slice(0, 1)}</span>;
}
