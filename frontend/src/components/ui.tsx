import { useState, type ReactNode } from 'react';
import type { Requisition } from '../api/types';
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
  icon?: 'box' | 'chart' | 'truck' | 'location' | 'requisitions' | 'warehouse' | 'history' | 'trend' | 'approve' | 'search' | 'alert' | 'audit';
}) {
  return (
    <section className="panel">
      <h2>{icon && <Icon name={icon} size={17} />}{title}</h2>
      {subtitle && <p className="panel-subtitle">{subtitle}</p>}
      {children}
    </section>
  );
}

export const STATUS_LABELS: Record<string, string> = {
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

export const PRIORITY_LABELS: Record<string, string> = {
  LOW: 'Baja',
  NORMAL: 'Normal',
  HIGH: 'Alta',
  URGENT: 'Crítica',
};

export function PriorityBadge({ priority }: { priority: string }) {
  return (
    <span className={`badge priority-${priority.toLowerCase()}`}>
      {PRIORITY_LABELS[priority] ?? priority.replaceAll('_', ' ')}
    </span>
  );
}

export function InlineFieldError({ message }: { message: string | null | undefined }) {
  if (!message) return null;
  return <small className="field-error" role="alert">{message}</small>;
}

/**
 * Confirmación accesible para acciones sensibles. El motivo solo se solicita
 * cuando la operación lo requiere (por ejemplo, cancelar una requisición).
 */
export function ConfirmDialog({
  title,
  message,
  confirmLabel = 'Confirmar',
  needsReason = false,
  reasonLabel = 'Motivo',
  minReasonLength = 4,
  onConfirm,
  onCancel,
}: {
  title: string;
  message: string;
  confirmLabel?: string;
  needsReason?: boolean;
  reasonLabel?: string;
  minReasonLength?: number;
  onConfirm: (reason: string) => void;
  onCancel: () => void;
}) {
  const [reason, setReason] = useState('');
  const invalidReason = needsReason && reason.trim().length < minReasonLength;
  return (
    <div className="modal-backdrop" role="presentation">
      <div className="modal-card" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
        <h3 id="confirm-title">{title}</h3>
        <p>{message}</p>
        {needsReason && (
          <label>
            {reasonLabel}
            <textarea
              value={reason}
              minLength={minReasonLength}
              onChange={(event) => setReason(event.target.value)}
            />
            <InlineFieldError
              message={invalidReason && reason.length > 0 ? `Indique al menos ${minReasonLength} caracteres.` : null}
            />
          </label>
        )}
        <div className="form-actions">
          <button className="button button-secondary" type="button" onClick={onCancel}>
            Cancelar
          </button>
          <button
            className="button button-primary"
            type="button"
            disabled={invalidReason}
            onClick={() => onConfirm(reason.trim())}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

/** Control de cantidades derivado del backend; nunca se captura manualmente. */
export function LineQuantitiesTable({ requisitions }: { requisitions: Requisition[] }) {
  const lines = requisitions.flatMap((req) => req.lines.map((line) => ({ req, line })));
  if (lines.length === 0) return <EmptyState text="No hay partidas para mostrar." />;
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Requisición</th>
            <th>Partida</th>
            <th>Estado</th>
            <th>Solicitada</th>
            <th>Autorizada</th>
            <th>Entregada</th>
            <th>Pendiente</th>
            <th>Surtido</th>
          </tr>
        </thead>
        <tbody>
          {lines.map(({ req, line }) => {
            const authorised = Number(line.authorised_qty) || 0;
            const delivered = Number(line.delivered_qty) || 0;
            return (
              <tr key={`${req.id}-${line.id}`}>
                <td>{req.document_no}</td>
                <td>{line.line_no}</td>
                <td><StatusBadge status={line.status} /></td>
                <td>{formatNumber(line.requested_qty)}</td>
                <td>{formatNumber(line.authorised_qty)}</td>
                <td>{formatNumber(line.delivered_qty)}</td>
                <td>{formatNumber(line.pending_qty)}</td>
                <td className="progress-cell">
                  <ProgressBar
                    value={delivered}
                    max={authorised}
                    tone={delivered >= authorised && authorised > 0 ? 'success' : 'default'}
                  />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
