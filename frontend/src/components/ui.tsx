import type { ReactNode } from 'react';

export function PageHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <header className="page-header">
      <h1>{title}</h1>
      {subtitle && <p>{subtitle}</p>}
    </header>
  );
}

export function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="panel">
      <h2>{title}</h2>
      {children}
    </section>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const className = `badge badge-${status.toLowerCase()}`;
  return <span className={className}>{status.replaceAll('_', ' ')}</span>;
}

export function ErrorMessage({ message }: { message: string | null }) {
  if (!message) return null;
  return <div className="alert alert-error" role="alert">{message}</div>;
}

export function SuccessMessage({ message }: { message: string | null }) {
  if (!message) return null;
  return <div className="alert alert-success" role="status">{message}</div>;
}

export function EmptyState({ text }: { text: string }) {
  return <p className="empty">{text}</p>;
}

export function formatNumber(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—';
  const number = Number(value);
  if (Number.isNaN(number)) return String(value);
  return new Intl.NumberFormat('es-MX', { maximumFractionDigits: 6 }).format(number);
}
