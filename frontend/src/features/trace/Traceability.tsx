import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api, describeApiError } from '../../api/client';
import type { RequisitionTrace } from '../../api/types';
import {
  EmptyState,
  ErrorMessage,
  formatNumber,
  LoadingState,
  PageHeader,
  Panel,
  SlaBadge,
  StatusBadge,
} from '../../components/ui';

function formatDate(value: unknown): string {
  if (typeof value !== 'string' || !value) return '—';
  return new Date(value).toLocaleString('es-MX');
}

function cellText(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

export function Traceability() {
  const { requisitionId } = useParams<{ requisitionId: string }>();
  const [trace, setTrace] = useState<RequisitionTrace | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!requisitionId) {
      setError('Falta el identificador de la requisición.');
      setLoading(false);
      return;
    }
    let active = true;
    api
      .requisitionTrace(requisitionId)
      .then((data) => {
        if (active) {
          setTrace(data);
          setError(null);
        }
      })
      .catch((cause: unknown) => {
        if (active) setError(describeApiError(cause, 'No fue posible consultar la trazabilidad.'));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [requisitionId]);

  return (
    <>
      <PageHeader
        title="Trazabilidad documental"
        subtitle="Requisición → Autorización → Reserva → Entrega → Vale → Seguimiento · consulta de solo lectura"
        actions={
          trace ? (
            <div className="page-header-actions">
              <a
                className="button button-ghost"
                href={api.documentUrl('requisitions', trace.requisition_id, 'PDF')}
                target="_blank"
                rel="noreferrer"
              >
                PDF de requisición
              </a>
              <a
                className="button button-ghost"
                href={api.documentUrl('requisitions', trace.requisition_id, 'XLSX')}
                rel="noreferrer"
              >
                Excel de requisición
              </a>
              <Link className="button button-ghost" to="/semaforo">Volver al semáforo</Link>
            </div>
          ) : undefined
        }
      />
      <ErrorMessage message={error} />
      {loading && <LoadingState rows={6} />}
      {!loading && !trace && <EmptyState text="No hay información de trazabilidad para mostrar." />}

      {trace && (
        <>
          <Panel
            title={`Cadena de ${trace.document_no}`}
            subtitle={`Generada ${formatDate(trace.generated_at)} · estado ${trace.administrative_status}`}
            icon="history"
          >
            <ol className="trace-steps" data-testid="trace-steps">
              {trace.stages.map((stage) => (
                <li
                  key={stage.stage}
                  className={stage.completed ? 'trace-step done' : 'trace-step'}
                  data-testid={`trace-stage-${stage.stage}`}
                >
                  <strong>{stage.label}</strong>
                  <span>{stage.completed ? 'Completado' : 'Pendiente'}</span>
                  {stage.document_no && <small>{stage.document_no}</small>}
                  <small>{formatDate(stage.occurred_at)}</small>
                  {stage.detail && <small>{stage.detail}</small>}
                </li>
              ))}
            </ol>
          </Panel>

          <Panel title="Seguimiento SLA y surtido" icon="chart">
            <div className="card-grid">
              <div className="metric-card">
                <span>Semáforo</span>
                <strong><SlaBadge sla={trace.tracking.sla} /></strong>
              </div>
              <div className="metric-card">
                <span>Estado administrativo</span>
                <strong><StatusBadge status={trace.administrative_status} /></strong>
              </div>
              <div className="metric-card">
                <span>Fecha requerida</span>
                <strong>{formatDate(trace.tracking.needed_at)}</strong>
              </div>
              <div className="metric-card">
                <span>Días pendientes</span>
                <strong>{formatNumber(trace.tracking.pending_days)}</strong>
              </div>
              <div className="metric-card">
                <span>% surtido</span>
                <strong data-testid="trace-fulfillment">{formatNumber(trace.tracking.fulfillment_percent)} %</strong>
              </div>
            </div>
          </Panel>

          <div className="panel-grid">
            <Panel title="Autorizaciones" subtitle={`${trace.approvals.length} decisión(es)`} icon="approve">
              {trace.approvals.length === 0 ? (
                <EmptyState text="Sin decisiones registradas." />
              ) : (
                <ul className="attachment-list">
                  {trace.approvals.map((item, index) => (
                    <li key={cellText(item.id ?? index)}>
                      {cellText(item.decision)} · {cellText(item.decided_by)} · {formatDate(item.decided_at)}
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="Reservas" subtitle={`${trace.reservations.length} reserva(s)`} icon="warehouse">
              {trace.reservations.length === 0 ? (
                <EmptyState text="Sin reservas registradas." />
              ) : (
                <ul className="attachment-list">
                  {trace.reservations.map((item, index) => (
                    <li key={cellText(item.id ?? index)}>
                      {cellText(item.reservation_no)} · {formatNumber(item.quantity)} · {cellText(item.status)}
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="Entregas" subtitle={`${trace.deliveries.length} movimiento(s) de salida`} icon="truck">
              {trace.deliveries.length === 0 ? (
                <EmptyState text="Sin entregas registradas." />
              ) : (
                <ul className="attachment-list">
                  {trace.deliveries.map((item, index) => (
                    <li key={cellText(item.id ?? index)}>
                      {cellText(item.movement_no)} · {formatNumber(item.quantity)} · {formatDate(item.posted_at)}
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="Vales de almacén" subtitle={`${trace.vouchers.length} vale(s)`} icon="requisitions">
              {trace.vouchers.length === 0 ? (
                <EmptyState text="Sin vales vinculados." />
              ) : (
                <ul className="attachment-list">
                  {trace.vouchers.map((voucher, index) => (
                    <li key={cellText(voucher.id ?? index)} data-testid={`trace-voucher-${cellText(voucher.document_no)}`}>
                      <strong>{cellText(voucher.document_no)}</strong> · <StatusBadge status={cellText(voucher.status)} />
                      <div className="action-cell">
                        <a
                          className="button button-small button-ghost"
                          href={api.documentUrl('vouchers', cellText(voucher.id), 'PDF')}
                          target="_blank"
                          rel="noreferrer"
                        >
                          PDF
                        </a>
                        <a
                          className="button button-small button-ghost"
                          href={api.documentUrl('vouchers', cellText(voucher.id), 'XLSX')}
                          rel="noreferrer"
                        >
                          Excel
                        </a>
                      </div>
                      <small>
                        Recibió {cellText(voucher.received_by_name)} · Autorizó {cellText(voucher.authorized_by_name)} ·
                        Despachó {cellText(voucher.dispatched_by_name)}
                      </small>
                      <small>
                        Impresiones: {(voucher.renders as Array<Record<string, unknown>> | undefined)?.length ?? 0}
                      </small>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          </div>

          <div className="panel-grid">
            <Panel title="Eventos documentales" icon="history">
              {trace.document_events.length === 0 ? (
                <EmptyState text="Sin eventos documentales." />
              ) : (
                <ul className="attachment-list">
                  {trace.document_events.map((event, index) => (
                    <li key={cellText(event.event_type ?? index)}>
                      {cellText(event.event_type)} · {cellText(event.from_status)} → {cellText(event.to_status)} · {formatDate(event.occurred_at)}
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="Bitácora de auditoría" icon="audit">
              {trace.audit_events.length === 0 ? (
                <EmptyState text="Sin eventos de auditoría." />
              ) : (
                <ul className="attachment-list">
                  {trace.audit_events.map((event, index) => (
                    <li key={`${cellText(event.action)}-${index}`} data-testid={`trace-audit-${cellText(event.action)}`}>
                      {cellText(event.action)} · {cellText(event.entity_type)} · {cellText(event.actor_username)} · {formatDate(event.occurred_at)}
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          </div>
        </>
      )}
    </>
  );
}
