import type { ReactNode } from 'react';
import { Icon } from './Icon';

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {actions && <div className="page-header-actions">{actions}</div>}
    </header>
  );
}

export function Panel({
  title,
  children,
  subtitle,
  icon,
}: {
  title: string;
  children: ReactNode;
  subtitle?: string;
  icon?: 'box' | 'chart' | 'truck' | 'location' | 'requisitions' | 'warehouse' | 'history' | 'trend' | 'approve' | 'search';
}) {
  return (
    <section className="panel">
      <h2>{icon && <Icon name={icon} size={17} />}{title}</h2>
      {subtitle && <p className="panel-subtitle">{subtitle}</p>}
      {children}
    </section>
  );
}

const STATUS_LABELS: Record<string, string> = {
  DRAFT: 'Borrador',
  SUBMITTED: 'Enviada',
  APPROVED: 'Autorizada',
  PARTIALLY_APPROVED: 'Autorizada parcial',
  AUTHORISED: 'Autorizada',
  REJECTED: 'Rechazada',
  CANCELLED: 'Cancelada',
  OPEN: 'Abierta',
  PARTIAL: 'Parcial',
  SENT: 'Enviada',
  CONFIRMED: 'Confirmada',
  RECEIVED: 'Recibida',
  PARTIALLY_RECEIVED: 'Recibida parcial',
  POSTED: 'Contabilizada',
  IN_PROGRESS: 'En curso',
  ACTIVE: 'Activa',
  INACTIVE: 'Inactiva',
  BLOCKED: 'Bloqueada',
  QUARANTINE: 'Cuarentena',
  EXPIRED: 'Vencida',
  AVAILABLE: 'Disponible',
  TEMPORARY: 'Temporal',
  WARNING: 'Advertencia',
  PENDING: 'Pendiente',
  COMPLETED: 'Completada',
  DAMAGED: 'Dañada',
  LOST: 'Extraviada',
  RETURNED: 'Devuelta',
};

export function StatusBadge({ status }: { status: string }) {
  const className = `badge badge-${status.toLowerCase()}`;
  const label = STATUS_LABELS[status] ?? status.replaceAll('_', ' ');
  return <span className={className}>{label}</span>;
}

export function ErrorMessage({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div className="alert alert-error" role="alert">
      <Icon name="alert" size={16} />
      <span>{message}</span>
    </div>
  );
}

export function SuccessMessage({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div className="alert alert-success" role="status">
      <Icon name="check" size={16} />
      <span>{message}</span>
    </div>
  );
}

export function WarningMessage({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div className="alert alert-warning" role="status">
      <Icon name="alert" size={16} />
      <span>{message}</span>
    </div>
  );
}

export function EmptyState({ text }: { text: string }) {
  return <p className="empty">{text}</p>;
}

export function LoadingState({ rows = 4, label = 'Cargando información…' }: { rows?: number; label?: string }) {
  return (
    <div className="loading-state" role="status" aria-live="polite">
      <span className="hint">{label}</span>
      {Array.from({ length: rows }, (_, index) => (
        <span key={index} className="skeleton" style={{ width: `${100 - index * 9}%` }} />
      ))}
    </div>
  );
}

export function DemoRibbon({ text = 'DEMOSTRACIÓN · Datos sintéticos aislados' }: { text?: string }) {
  return (
    <div className="demo-ribbon" role="note">
      <Icon name="demo" size={15} />
      {text}
    </div>
  );
}

export function ProgressBar({
  value,
  max = 100,
  tone = 'default',
  label,
}: {
  value: number;
  max?: number;
  tone?: 'default' | 'success' | 'warning';
  label?: string;
}) {
  const pct = max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0;
  return (
    <div>
      {label && (
        <div className="progress-label">
          <span>{label}</span>
          <strong>{Math.round(pct)}%</strong>
        </div>
      )}
      <div className={`progress ${tone === 'default' ? '' : tone}`}>
        <span style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export function formatNumber(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—';
  const number = Number(value);
  if (Number.isNaN(number)) return String(value);
  return new Intl.NumberFormat('es-MX', { maximumFractionDigits: 6 }).format(number);
}
