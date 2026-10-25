import { useEffect, useRef, type ReactNode } from "react";
import {
  ArrowUpRight,
  CircleNotch,
  Crosshair,
  Compass,
  ShieldChevron,
  X,
} from "@phosphor-icons/react";
import type { Doctrine } from "../state/settings";
export const doctrineIcons = {
  assault: Crosshair,
  defense: ShieldChevron,
  maneuver: Compass,
};
export function CommanderIcon({
  doctrine,
  size = 28,
}: {
  doctrine: Doctrine;
  size?: number;
}) {
  const Icon = doctrineIcons[doctrine];
  return <Icon size={size} weight="duotone" aria-hidden="true" />;
}
export function Button({
  children,
  kind = "",
  loading = false,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  kind?: string;
  loading?: boolean;
}) {
  return (
    <button
      {...props}
      className={`button ${kind} ${props.className ?? ""}`}
      aria-busy={loading || undefined}
      disabled={props.disabled || loading}
    >
      {loading ? <CircleNotch className="spinner" size={16} /> : null}
      {children}
    </button>
  );
}
export function PanelHeading({
  eyebrow,
  title,
  children,
}: {
  eyebrow: string;
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="panel-heading">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h2>{title}</h2>
      </div>
      {children}
    </div>
  );
}
export function PageHeading({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow: string;
  title: string;
  description: string;
  children?: ReactNode;
}) {
  return (
    <header className="page-heading">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p className="page-description">{description}</p>
      </div>
      {children}
    </header>
  );
}
export function TextAction({
  children,
  onClick,
}: {
  children: ReactNode;
  onClick: () => void;
}) {
  return (
    <button className="text-action" onClick={onClick}>
      {children}
      <ArrowUpRight size={14} />
    </button>
  );
}
export function Modal({
  title,
  children,
  onClose,
  footer,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  footer: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    const previous = document.activeElement as HTMLElement | null;
    d?.showModal();
    return () => {
      d?.close();
      previous?.focus();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      className="modal"
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      aria-labelledby="modal-title"
    >
      <div className="modal-heading">
        <h2 id="modal-title">{title}</h2>
        <button
          className="icon-button"
          aria-label="关闭对话框"
          onClick={onClose}
        >
          <X size={20} />
        </button>
      </div>
      <div className="modal-body">{children}</div>
      <div className="modal-footer">{footer}</div>
    </dialog>
  );
}
