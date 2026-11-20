import { useEffect, useState } from 'react';
import { api, describeApiError } from '../../api/client';
import type { Catalogs, RenderRecord, Requisition, Voucher } from '../../api/types';
import { can, PERM } from '../../auth/permissions';
import { useAuth } from '../../auth/AuthContext';
import {
  EmptyState,
  ErrorMessage,
  LoadingState,
  PageHeader,
  Panel,
  StatusBadge,
  SuccessMessage,
} from '../../components/ui';

function localDate(): string {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60_000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}

/** La clave debe ser estable por intención: un reintento no crea otro vale. */
function idempotencyKey(prefix: string, requisitionId: string, issueDate: string): string {
  return `${prefix}:${requisitionId}:${issueDate}`;
}

function formatDate(value: string | null): string {
  return value ? new Date(value).toLocaleString('es-MX') : '—';
}

export function Vouchers() {
  const { user } = useAuth();
  const canCreate = can(user, ...PERM.CREATE_VOUCHERS);
  const canIssue = can(user, ...PERM.ISSUE_VOUCHERS);
  const [catalogs, setCatalogs] = useState<Catalogs | null>(null);
  const [requisitions, setRequisitions] = useState<Requisition[]>([]);
  const [vouchers, setVouchers] = useState<Voucher[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [requisitionId, setRequisitionId] = useState('');
  const [departmentId, setDepartmentId] = useState('');
  const [issueDate, setIssueDate] = useState(localDate());
  const [costCenterCode, setCostCenterCode] = useState('');
  const [area, setArea] = useState('');
  const [usageEquipment, setUsageEquipment] = useState('');

  const [selectedVoucher, setSelectedVoucher] = useState<string | null>(null);
  const [receivedName, setReceivedName] = useState('');
  const [authorizedName, setAuthorizedName] = useState('');
  const [dispatchedName, setDispatchedName] = useState('');
  const [historyFor, setHistoryFor] = useState<string | null>(null);
  const [renders, setRenders] = useState<RenderRecord[]>([]);

  async function reload(): Promise<void> {
    try {
      const [catalogData, approved, partial, voucherData] = await Promise.all([
        api.catalogs(),
        api.requisitions({ status: 'APPROVED' }),
        api.requisitions({ status: 'PARTIALLY_APPROVED' }),
        api.vouchers(),
      ]);
      setCatalogs(catalogData);
      // Una requisición puede aparecer en más de un estado durante la carga;
      // el selector debe mostrarla una sola vez.
      setRequisitions(
        Array.from(new Map([...approved, ...partial].map((item) => [item.id, item])).values()),
      );
      setVouchers(voucherData);
      setDepartmentId((current) => current || catalogData.departments[0]?.id || '');
      setCostCenterCode((current) => current || catalogData.cost_centers[0]?.code || '');
    } catch (cause) {
      setError(describeApiError(cause, 'No fue posible cargar los vales.'));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void reload();
  }, []);

  const selectedRequisition = requisitions.find((item) => item.id === requisitionId) ?? null;
  const detail = vouchers.find((item) => item.id === selectedVoucher) ?? null;

  async function createVoucher(): Promise<void> {
    if (!requisitionId) {
      setError('Seleccione una requisición autorizada.');
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const hasDelivery = selectedRequisition?.lines.some(
        (line) => Number(line.delivered_qty ?? 0) > 0,
      );
      const created = await api.createVoucher({
        department_id: selectedRequisition?.department_id ?? departmentId,
        warehouse_id: selectedRequisition?.warehouse_id ?? catalogs?.warehouses[0]?.id ?? null,
        requisition_id: requisitionId,
        mode: hasDelivery ? 'DELIVERY' : 'DRAFT',
        cost_center_code: costCenterCode || null,
        area: area || null,
        usage_equipment: usageEquipment || null,
        issue_date: issueDate,
        idempotency_key: idempotencyKey('vale', requisitionId, issueDate),
      });
      setNotice(`Vale ${created.document_no} generado. No se crearon movimientos de inventario.`);
      setRequisitionId('');
      await reload();
    } catch (cause) {
      setError(describeApiError(cause, 'No fue posible generar el vale.'));
    } finally {
      setBusy(false);
    }
  }

  async function issue(voucher: Voucher): Promise<void> {
    setBusy(true);
    setError(null);
    try {
      const updated = await api.issueVoucher(voucher.id);
      setNotice(`Vale ${updated.document_no} emitido.`);
      await reload();
    } catch (cause) {
      setError(describeApiError(cause, 'No fue posible emitir el vale.'));
    } finally {
      setBusy(false);
    }
  }

  async function saveSignatures(): Promise<void> {
    if (!selectedVoucher) return;
    setBusy(true);
    setError(null);
    try {
      await api.signVoucher(selectedVoucher, {
        received_by_name: receivedName || null,
        authorized_by_name: authorizedName || null,
        dispatched_by_name: dispatchedName || null,
      });
      setNotice('Nombres de recepción, autorización y despacho registrados. No se generó ninguna firma gráfica.');
      await reload();
    } catch (cause) {
      setError(describeApiError(cause, 'No fue posible registrar los nombres.'));
    } finally {
      setBusy(false);
    }
  }

  async function showHistory(voucher: Voucher): Promise<void> {
    setBusy(true);
    setError(null);
    try {
      const data = await api.documentRenders('vouchers', voucher.id);
      setRenders(data);
      setHistoryFor(voucher.id);
    } catch (cause) {
      setError(describeApiError(cause, 'No fue posible consultar el historial de impresiones.'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Vales de almacén"
        subtitle="Folios consecutivos desde VA-000166 · PDF y Excel de 10 partidas · reimpresión sin duplicar movimientos"
      />
      <ErrorMessage message={error} />
      <SuccessMessage message={notice} />
      {loading && <LoadingState />}

      <Panel
        title="Generar vale desde requisición autorizada"
        subtitle="Las cantidades despachadas se derivan de las entregas confirmadas"
        icon="warehouse"
      >
        <div className="form-grid">
          <label>
            Requisición
            <select
              value={requisitionId}
              onChange={(event) => setRequisitionId(event.target.value)}
              data-testid="voucher-requisition"
            >
              <option value="">Seleccione…</option>
              {requisitions.map((item) => (
                <option key={item.id} value={item.id}>{item.document_no} · {item.status}</option>
              ))}
            </select>
          </label>
          <label>
            Departamento
            <select value={departmentId} onChange={(event) => setDepartmentId(event.target.value)}>
              <option value="">Seleccione…</option>
              {(catalogs?.departments ?? []).map((item) => (
                <option key={item.id} value={item.id}>{item.name ?? item.code}</option>
              ))}
            </select>
          </label>
          <label>
            Fecha de expedición
            <input type="date" value={issueDate} onChange={(event) => setIssueDate(event.target.value)} />
          </label>
          <label>
            CECO
            <input value={costCenterCode} onChange={(event) => setCostCenterCode(event.target.value)} />
          </label>
          <label>
            Área
            <input value={area} onChange={(event) => setArea(event.target.value)} />
          </label>
          <label>
            Uso / equipo
            <input value={usageEquipment} onChange={(event) => setUsageEquipment(event.target.value)} />
          </label>
        </div>
        <button
          className="button button-primary"
          type="button"
          disabled={busy || !canCreate || !requisitionId}
          onClick={() => void createVoucher()}
          data-testid="voucher-create"
        >
          Generar vale
        </button>
        {!canCreate && <p className="hint">Su perfil no tiene permiso para generar vales.</p>}
      </Panel>

      <Panel title="Historial de vales" subtitle="Consulta, emisión, descargas y reimpresión" icon="history">
        {vouchers.length === 0 ? (
          <EmptyState text="Todavía no hay vales registrados." />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Folio</th>
                  <th>Fecha</th>
                  <th>Requisición</th>
                  <th>Estado</th>
                  <th>Partidas</th>
                  <th>Descargas</th>
                  <th>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {vouchers.map((voucher) => (
                  <tr key={voucher.id} data-testid={`voucher-row-${voucher.document_no}`}>
                    <td>{voucher.document_no}</td>
                    <td>{voucher.issue_date}</td>
                    <td>{voucher.source_requisition_id ? 'Vinculada' : 'Independiente'}</td>
                    <td><StatusBadge status={voucher.status} /></td>
                    <td>{voucher.lines.length}</td>
                    <td className="action-cell">
                      <a
                        className="button button-small button-ghost"
                        href={api.documentUrl('vouchers', voucher.id, 'PDF')}
                        target="_blank"
                        rel="noreferrer"
                        data-testid={`voucher-pdf-${voucher.document_no}`}
                      >
                        PDF
                      </a>
                      <a
                        className="button button-small button-ghost"
                        href={api.documentUrl('vouchers', voucher.id, 'XLSX')}
                        rel="noreferrer"
                        data-testid={`voucher-xlsx-${voucher.document_no}`}
                      >
                        Excel
                      </a>
                      <a
                        className="button button-small button-ghost"
                        href={api.documentUrl('vouchers', voucher.id, 'PDF', true)}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Reimprimir
                      </a>
                    </td>
                    <td className="action-cell">
                      {voucher.status === 'DRAFT' && (
                        <button
                          className="button button-small button-ghost"
                          type="button"
                          disabled={busy || !canIssue}
                          onClick={() => void issue(voucher)}
                          data-testid={`voucher-issue-${voucher.document_no}`}
                        >
                          Emitir
                        </button>
                      )}
                      <button
                        className="button button-small button-ghost"
                        type="button"
                        disabled={busy || !canIssue}
                        onClick={() => {
                          setSelectedVoucher(voucher.id);
                          setReceivedName(voucher.received_by_name ?? '');
                          setAuthorizedName(voucher.authorized_by_name ?? '');
                          setDispatchedName(voucher.dispatched_by_name ?? '');
                        }}
                        data-testid={`voucher-sign-${voucher.document_no}`}
                      >
                        Firmas
                      </button>
                      <button
                        className="button button-small button-ghost"
                        type="button"
                        disabled={busy}
                        onClick={() => void showHistory(voucher)}
                        data-testid={`voucher-history-${voucher.document_no}`}
                      >
                        Historial
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {detail && (
        <Panel title={`Constancias de ${detail.document_no}`} subtitle="Solo nombres declarados; sin firma gráfica" icon="approve">
          <div className="form-grid">
            <label>
              Recibido por
              <input value={receivedName} onChange={(event) => setReceivedName(event.target.value)} data-testid="sign-received" />
            </label>
            <label>
              Autorizado por
              <input value={authorizedName} onChange={(event) => setAuthorizedName(event.target.value)} data-testid="sign-authorized" />
            </label>
            <label>
              Despachado por almacén
              <input value={dispatchedName} onChange={(event) => setDispatchedName(event.target.value)} data-testid="sign-dispatched" />
            </label>
          </div>
          <button
            className="button button-primary"
            type="button"
            disabled={busy || !canIssue}
            onClick={() => void saveSignatures()}
            data-testid="voucher-sign-save"
          >
            Registrar nombres
          </button>
          <p className="hint">
            Registrado: {formatDate(detail.signatures_recorded_at)}. La reimpresión conserva el archivo original;
            descargue sin reimprimir para incluir los nombres capturados.
          </p>
        </Panel>
      )}

      {historyFor && (
        <Panel title="Historial de impresión" subtitle="Hash SHA-256 de cada archivo generado" icon="history">
          {renders.length === 0 ? (
            <EmptyState text="Sin impresiones registradas." />
          ) : (
            <ul className="attachment-list">
              {renders.map((render) => (
                <li key={render.id} data-testid={`render-${render.document_format}-${render.is_reprint}`}>
                  {render.document_format} · {render.is_reprint ? 'Reimpresión' : 'Original'} ·{' '}
                  {formatDate(render.rendered_at)} · <code>{render.sha256.slice(0, 16)}…</code>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      )}
    </>
  );
}
