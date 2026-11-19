import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, describeApiError } from '../../api/client';
import type { Catalogs, SlaColor, SlaFilters, SlaRequisition } from '../../api/types';
import { useAuth } from '../../auth/AuthContext';
import { can, PERM } from '../../auth/permissions';
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

const COLOR_OPTIONS: Array<{ value: SlaColor | ''; label: string }> = [
  { value: '', label: 'Todos los colores' },
  { value: 'GREEN', label: 'VERDE · en plazo' },
  { value: 'YELLOW', label: 'AMARILLO · por vencer' },
  { value: 'RED', label: 'ROJO · vencido' },
  { value: 'NONE', label: 'Sin medición' },
];

const STATUS_OPTIONS = [
  ['', 'Todos los estados'],
  ['DRAFT', 'Borrador'],
  ['SUBMITTED', 'Enviada'],
  ['APPROVED', 'Autorizada'],
  ['PARTIALLY_APPROVED', 'Autorizada parcial'],
  ['REJECTED', 'Rechazada'],
  ['CANCELLED', 'Cancelada'],
];

const PRIORITY_OPTIONS = [
  ['', 'Todas las prioridades'],
  ['LOW', 'Baja'],
  ['NORMAL', 'Normal'],
  ['HIGH', 'Alta'],
  ['URGENT', 'Urgente'],
];

function formatDate(value: string | null): string {
  return value ? new Date(value).toLocaleDateString('es-MX') : '—';
}

export function SlaBoard() {
  const { user } = useAuth();
  const canTrace = can(user, ...PERM.VIEW_TRACE);
  const [catalogs, setCatalogs] = useState<Catalogs | null>(null);
  const [rows, setRows] = useState<SlaRequisition[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [color, setColor] = useState<SlaColor | ''>('');
  const [status, setStatus] = useState('');
  const [priority, setPriority] = useState('');
  const [departmentId, setDepartmentId] = useState('');
  const [equipmentId, setEquipmentId] = useState('');
  const [requesterId, setRequesterId] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  const filters = useMemo<SlaFilters>(
    () => ({
      sla_color: color || undefined,
      status: status || undefined,
      priority: priority || undefined,
      department_id: departmentId || undefined,
      equipment_id: equipmentId || undefined,
      requester_id: requesterId || undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
    }),
    [color, status, priority, departmentId, equipmentId, requesterId, dateFrom, dateTo],
  );

  useEffect(() => {
    let active = true;
    Promise.all([api.catalogs(), api.slaRequisitions(filters)])
      .then(([catalogData, data]) => {
        if (!active) return;
        setCatalogs(catalogData);
        setRows(data);
        setError(null);
      })
      .catch((cause: unknown) => {
        if (active) setError(describeApiError(cause, 'No fue posible cargar el semáforo.'));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [filters]);

  const totals = useMemo(() => {
    const result = { GREEN: 0, YELLOW: 0, RED: 0, NONE: 0 };
    rows.forEach((row) => {
      result[row.sla.color] += 1;
    });
    return result;
  }, [rows]);

  function clearFilters(): void {
    setColor('');
    setStatus('');
    setPriority('');
    setDepartmentId('');
    setEquipmentId('');
    setRequesterId('');
    setDateFrom('');
    setDateTo('');
  }

  return (
    <>
      <PageHeader
        title="Semáforo de requisiciones"
        subtitle="Indicador calculado a partir de políticas aprobadas · no sustituye el estado administrativo ni publica movimientos"
      />
      <ErrorMessage message={error} />

      <div className="card-grid" data-testid="sla-summary">
        <div className="metric-card sla-green">
          <span>VERDE · en plazo</span>
          <strong data-testid="sla-total-green">{totals.GREEN}</strong>
        </div>
        <div className="metric-card sla-yellow">
          <span>AMARILLO · por vencer</span>
          <strong data-testid="sla-total-yellow">{totals.YELLOW}</strong>
        </div>
        <div className="metric-card sla-red">
          <span>ROJO · vencido</span>
          <strong data-testid="sla-total-red">{totals.RED}</strong>
        </div>
        <div className="metric-card">
          <span>Sin medición</span>
          <strong data-testid="sla-total-none">{totals.NONE}</strong>
        </div>
      </div>

      <Panel title="Filtros del tablero" icon="search">
        <div className="form-grid">
          <label>
            Semáforo
            <select
              value={color}
              onChange={(event) => setColor(event.target.value as SlaColor | '')}
              data-testid="sla-filter-color"
            >
              {COLOR_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </label>
          <label>
            Estado administrativo
            <select value={status} onChange={(event) => setStatus(event.target.value)} data-testid="sla-filter-status">
              {STATUS_OPTIONS.map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </label>
          <label>
            Prioridad
            <select value={priority} onChange={(event) => setPriority(event.target.value)} data-testid="sla-filter-priority">
              {PRIORITY_OPTIONS.map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </label>
          <label>
            Departamento
            <select value={departmentId} onChange={(event) => setDepartmentId(event.target.value)} data-testid="sla-filter-department">
              <option value="">Todos los departamentos</option>
              {(catalogs?.departments ?? []).map((item) => (
                <option key={item.id} value={item.id}>{item.name ?? item.code}</option>
              ))}
            </select>
          </label>
          <label>
            Equipo
            <select value={equipmentId} onChange={(event) => setEquipmentId(event.target.value)} data-testid="sla-filter-equipment">
              <option value="">Todos los equipos</option>
              {(catalogs?.equipment ?? []).map((item) => (
                <option key={item.id} value={item.id}>{item.name ?? item.code}</option>
              ))}
            </select>
          </label>
          <label>
            Responsable
            <select value={requesterId} onChange={(event) => setRequesterId(event.target.value)} data-testid="sla-filter-requester">
              <option value="">Todos los responsables</option>
              {Array.from(
                new Map(
                  rows
                    .filter((row) => row.requester_id && row.responsible)
                    .map((row) => [row.requester_id as string, row.responsible as string]),
                ).entries(),
              ).map(([id, name]) => (
                <option key={id} value={id}>{name}</option>
              ))}
            </select>
          </label>
          <label>
            Creada desde
            <input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} data-testid="sla-filter-date-from" />
          </label>
          <label>
            Creada hasta
            <input type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} data-testid="sla-filter-date-to" />
          </label>
        </div>
        <button className="button button-ghost" type="button" onClick={clearFilters} data-testid="sla-clear-filters">
          Limpiar filtros
        </button>
      </Panel>

      <Panel title="Requisiciones" subtitle={`${rows.length} resultado(s)`} icon="chart">
        {loading && <LoadingState rows={5} />}
        {!loading && rows.length === 0 && <EmptyState text="No hay requisiciones con estos filtros." />}
        {!loading && rows.length > 0 && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Folio</th>
                  <th>Departamento</th>
                  <th>Equipo</th>
                  <th>Responsable</th>
                  <th>Estado administrativo</th>
                  <th>Semáforo</th>
                  <th>Fecha requerida</th>
                  <th>Días pendientes</th>
                  <th>% surtido</th>
                  <th>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id} data-testid={`sla-row-${row.document_no}`}>
                    <td>{row.document_no}</td>
                    <td>{row.department_name ?? row.department_code ?? '—'}</td>
                    <td>{row.equipment ?? '—'}</td>
                    <td>{row.responsible ?? '—'}</td>
                    <td><StatusBadge status={row.administrative_status} /></td>
                    <td><SlaBadge sla={row.sla} /></td>
                    <td>{formatDate(row.needed_at)}</td>
                    <td>{row.pending_days === null ? '—' : formatNumber(row.pending_days)}</td>
                    <td>{formatNumber(row.fulfillment_percent)} %</td>
                    <td className="action-cell">
                      {canTrace && (
                        <Link
                          className="button button-small button-ghost"
                          to={`/trazabilidad/${row.id}`}
                          data-testid={`sla-trace-${row.document_no}`}
                        >
                          Trazabilidad
                        </Link>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </>
  );
}
