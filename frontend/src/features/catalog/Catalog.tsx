import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react';
import { api, ApiError } from '../../api/client';
import type {
  Catalogs,
  ItemFamily,
  WmsItem,
  WmsItemDetail,
  WmsLocation,
  WmsSearchFilters,
} from '../../api/types';
import { useAuth } from '../../auth/AuthContext';
import { can, PERM } from '../../auth/permissions';
import { Icon } from '../../components/Icon';
import {
  EmptyState,
  ErrorMessage,
  formatNumber,
  LoadingState,
  PageHeader,
  Panel,
  StatusBadge,
  SuccessMessage,
} from '../../components/ui';

function message(error: unknown): string {
  return error instanceof ApiError ? error.message : 'No se pudo completar la operación.';
}

export function Catalog() {
  const { user } = useAuth();
  const canManage = can(user, ...PERM.MANAGE_CATALOG);

  const [families, setFamilies] = useState<ItemFamily[]>([]);
  const [catalogs, setCatalogs] = useState<Catalogs | null>(null);
  const [allLocations, setAllLocations] = useState<WmsLocation[]>([]);
  const [items, setItems] = useState<WmsItem[]>([]);
  const [detail, setDetail] = useState<WmsItemDetail | null>(null);
  const [query, setQuery] = useState('');
  const [familyId, setFamilyId] = useState('');
  const [warehouseId, setWarehouseId] = useState('');
  const [locationId, setLocationId] = useState('');
  const [equipmentId, setEquipmentId] = useState('');
  const [activeOnly, setActiveOnly] = useState(true);
  const [loading, setLoading] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [newFamilyCode, setNewFamilyCode] = useState('');
  const [newFamilyName, setNewFamilyName] = useState('');
  const [savingFamily, setSavingFamily] = useState(false);

  const runSearch = useCallback(async (filters: WmsSearchFilters) => {
    setLoading(true);
    setError(null);
    try {
      setItems(await api.wmsSearchItems(filters));
    } catch (exc) {
      setError(message(exc));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    Promise.allSettled([api.wmsFamilies(), api.catalogs(), api.wmsLocations()]).then(
      ([familyResult, catalogResult, locationResult]) => {
        if (!active) return;
        if (familyResult.status === 'fulfilled') setFamilies(familyResult.value);
        if (catalogResult.status === 'fulfilled') setCatalogs(catalogResult.value);
        if (locationResult.status === 'fulfilled') setAllLocations(locationResult.value);
      },
    );
    void runSearch({ query: '', active_only: true });
    return () => { active = false; };
  }, [runSearch]);

  const warehouses = useMemo(() => catalogs?.warehouses ?? [], [catalogs]);
  const filteredLocations = useMemo(
    () => allLocations.filter((location) => !warehouseId || location.warehouse_id === warehouseId),
    [allLocations, warehouseId],
  );

  async function handleSearch(event: FormEvent) {
    event.preventDefault();
    await runSearch({
      query: query.trim() || undefined,
      family_id: familyId || undefined,
      warehouse_id: warehouseId || undefined,
      location_id: locationId || undefined,
      equipment_id: equipmentId || undefined,
      active_only: activeOnly,
    });
  }

  async function openItem(id: string) {
    setLoadingDetail(true);
    setError(null);
    try {
      setDetail(await api.wmsItemDetail(id));
    } catch (exc) {
      setError(message(exc));
    } finally {
      setLoadingDetail(false);
    }
  }

  async function handlePhoto(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!detail) return;
    const input = event.currentTarget.elements.namedItem('photo') as HTMLInputElement | null;
    const file = input?.files?.[0];
    if (!file) return;
    setSavingFamily(true);
    setError(null);
    setNotice(null);
    try {
      const photo = await api.uploadItemPhoto(detail.id, file);
      setDetail({ ...detail, image_url: photo.image_url });
      setNotice('Fotografía registrada con SHA-256 en la bitácora.');
      input.value = '';
    } catch (exc) {
      setError(message(exc));
    } finally {
      setSavingFamily(false);
    }
  }

  async function handleFamily(event: FormEvent) {
    event.preventDefault();
    setSavingFamily(true);
    setError(null);
    setNotice(null);
    try {
      await api.createFamily({ code: newFamilyCode.trim(), name: newFamilyName.trim() });
      setFamilies(await api.wmsFamilies());
      setNewFamilyCode('');
      setNewFamilyName('');
      setNotice('Familia creada correctamente.');
    } catch (exc) {
      setError(message(exc));
    } finally {
      setSavingFamily(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Catálogo de materiales"
        subtitle="Búsqueda avanzada, existencias operativas y ficha técnica de artículos"
        actions={<span className="badge badge-active"><Icon name="box" size={13} /> Lote A · WMS</span>}
      />
      <div className="demo-ribbon" role="note">
        <Icon name="demo" size={15} />
        DEMOSTRACIÓN · Datos sintéticos aislados · Inventario operativo, no oficial
      </div>

      <ErrorMessage message={error} />
      <SuccessMessage message={notice} />

      <Panel title="Buscar artículos" icon="search" subtitle="Filtros combinables sobre código, descripción, fabricante y código de barras">
        <form className="search-toolbar" onSubmit={handleSearch}>
          <label>
            Texto, código o código de barras
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Ej. TORNILLO, FF-M8-30"
              aria-label="Buscar por texto, código o código de barras"
            />
          </label>
          <label>
            Familia
            <select value={familyId} onChange={(event) => setFamilyId(event.target.value)} aria-label="Filtrar por familia">
              <option value="">Todas</option>
              {families.map((family) => (
                <option value={family.id} key={family.id}>{family.name}</option>
              ))}
            </select>
          </label>
          <label>
            Almacén
            <select value={warehouseId} onChange={(event) => setWarehouseId(event.target.value)} aria-label="Filtrar por almacén">
              <option value="">Todos</option>
              {warehouses.map((warehouse) => (
                <option value={warehouse.id} key={warehouse.id}>{warehouse.name ?? warehouse.code}</option>
              ))}
            </select>
          </label>
          <label>
            Ubicación física
            <select
              value={locationId}
              onChange={(event) => setLocationId(event.target.value)}
              aria-label="Filtrar por ubicación física"
            >
              <option value="">Todas</option>
              {filteredLocations.map((location) => (
                <option value={location.id} key={location.id}>{location.warehouse_code} · {location.code}</option>
              ))}
            </select>
          </label>
          <label>
            Equipo (GMAO)
            <select value={equipmentId} onChange={(event) => setEquipmentId(event.target.value)} aria-label="Filtrar por equipo">
              <option value="">Todos</option>
              {(catalogs?.equipment ?? []).map((equipment) => (
                <option value={equipment.id} key={equipment.id}>{equipment.name ?? equipment.code ?? ''}</option>
              ))}
            </select>
          </label>
          <label className="checkbox-line">
            <input
              type="checkbox"
              checked={activeOnly}
              onChange={(event) => setActiveOnly(event.target.checked)}
              aria-label="Solo artículos activos"
            />
            Solo activos
          </label>
          <button type="submit" className="button button-primary align-end" disabled={loading}>
            <Icon name="search" size={14} /> Buscar
          </button>
        </form>
      </Panel>

      {canManage && (
        <Panel title="Nueva familia" icon="box" subtitle="Alta controlada de catálogo; queda registrada en la bitácora">
          <form className="filter-bar" onSubmit={handleFamily}>
            <label>
              Código
              <input
                value={newFamilyCode}
                onChange={(event) => setNewFamilyCode(event.target.value)}
                placeholder="EJ. HERRAMIENTAS"
                required
                aria-label="Código de la familia"
              />
            </label>
            <label>
              Nombre
              <input
                value={newFamilyName}
                onChange={(event) => setNewFamilyName(event.target.value)}
                placeholder="Herramientas y equipos"
                required
                aria-label="Nombre de la familia"
              />
            </label>
            <button type="submit" className="button button-secondary align-end" disabled={savingFamily}>
              Crear familia
            </button>
          </form>
        </Panel>
      )}

      <div className="panel-grid">
        <Panel title={`Resultados (${items.length})`} icon="box" subtitle="Seleccione un artículo para ver su ficha completa">
          {loading ? (
            <LoadingState rows={4} />
          ) : items.length === 0 ? (
            <EmptyState text="No hay artículos que coincidan con los filtros." />
          ) : (
            <div className="location-tree">
              {items.map((item) => (
                <button
                  type="button"
                  key={item.id}
                  className={`item-card ${detail?.id === item.id ? 'selected' : ''}`}
                  onClick={() => void openItem(item.id)}
                  aria-label={`Ver ficha de ${item.code}`}
                >
                  <strong>{item.code} · {item.description}</strong>
                  <span className="chip-row">
                    {item.family_name && <span className="chip">{item.family_name}</span>}
                    {item.lot_tracked && <span className="chip">Lote</span>}
                    {item.serial_tracked && <span className="chip">Serie</span>}
                    <StatusBadge status={item.is_active ? 'ACTIVE' : 'INACTIVE'} />
                  </span>
                  <span className="hint">
                    {item.uom_code} · Existencia {formatNumber(item.on_hand_qty)} · Disponible {formatNumber(item.available_qty)} · {item.location_count} ubicación(es)
                  </span>
                </button>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="Ficha de material" icon="requisitions" subtitle="Datos técnicos, ubicaciones, lotes, series y trazabilidad documental">
          {loadingDetail ? (
            <LoadingState rows={5} />
          ) : !detail ? (
            <EmptyState text="Seleccione un artículo de la lista para consultar su ficha." />
          ) : (
            <div className="detail-stack">
              <div className="detail-header">
                {detail.image_url ? (
                  <img className="item-photo" src={detail.image_url} alt={`Fotografía de ${detail.code}`} />
                ) : (
                  <div className="item-photo-placeholder"><Icon name="box" size={28} /> Sin fotografía registrada</div>
                )}
                <div>
                  <h3>{detail.code}</h3>
                  <p>{detail.description}</p>
                  <div className="chip-row">
                    <StatusBadge status={detail.is_active ? 'ACTIVE' : 'INACTIVE'} />
                    {detail.family_name && <span className="chip">{detail.family_name}</span>}
                    <span className="chip">{detail.uom_code}</span>
                    {detail.is_consumable && <span className="chip">Consumible</span>}
                    {detail.is_returnable && <span className="chip">Retornable</span>}
                    {detail.is_tool && <span className="chip">Herramienta</span>}
                  </div>
                </div>
              </div>

              <div className="availability-grid">
                <div><span>Existencia</span><strong>{formatNumber(detail.on_hand_qty)}</strong></div>
                <div><span>Reservado</span><strong>{formatNumber(detail.reserved_qty)}</strong></div>
                <div><span>Disponible</span><strong>{formatNumber(detail.available_qty)}</strong></div>
              </div>

              <div className="detail-grid">
                <div><span>Fabricante</span><strong>{detail.manufacturer ?? '—'}</strong></div>
                <div><span>Parte del fabricante</span><strong>{detail.manufacturer_part_no ?? '—'}</strong></div>
                <div><span>Código de barras</span><strong>{detail.barcode ?? '—'}</strong></div>
                <div><span>Costo estándar</span><strong>{formatNumber(detail.standard_cost)}</strong></div>
                <div><span>Punto de reorder</span><strong>{formatNumber(detail.reorder_point)}</strong></div>
                <div><span>Stock de seguridad</span><strong>{formatNumber(detail.safety_stock)}</strong></div>
                <div><span>Stock máximo</span><strong>{formatNumber(detail.max_stock)}</strong></div>
                <div><span>Peso (kg)</span><strong>{formatNumber(detail.weight_kg)}</strong></div>
                <div><span>Volumen (m³)</span><strong>{formatNumber(detail.volume_m3)}</strong></div>
              </div>

              {canManage && (
                <form className="filter-bar" onSubmit={handlePhoto}>
                  <label>
                    Fotografía (JPG, PNG o WEBP · máx. 2 MB)
                    <input type="file" name="photo" accept="image/jpeg,image/png,image/webp" required aria-label="Fotografía del artículo" />
                  </label>
                  <button type="submit" className="button button-ghost align-end" disabled={savingFamily}>
                    Guardar fotografía
                  </button>
                </form>
              )}

              <h3>Ubicaciones con existencia</h3>
              {detail.locations.length === 0 ? (
                <EmptyState text="Sin saldos asignados a una ubicación física." />
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead><tr><th>Ubicación</th><th>Almacén</th><th>Zona</th><th>Lote</th><th>Existencia</th><th>Disponible</th></tr></thead>
                    <tbody>
                      {detail.locations.map((location) => (
                        <tr key={`${location.location_id}-${location.lot_number ?? ''}`}>
                          <td>{location.location_code}</td>
                          <td>{location.warehouse_code}</td>
                          <td>{[location.zone, location.aisle].filter(Boolean).join('-') || '—'}</td>
                          <td>{location.lot_number ?? '—'}</td>
                          <td>{formatNumber(location.on_hand_qty)}</td>
                          <td>{formatNumber(location.available_qty)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              <h3>Lotes y series</h3>
              <div className="chip-row">
                {detail.lots.map((lot) => <span className="chip" key={lot.id}>{lot.lot_number} · {lot.status}</span>)}
                {detail.serials.map((serial) => <span className="chip" key={serial.id}>{serial.serial_number} · {serial.status}</span>)}
                {detail.lots.length === 0 && detail.serials.length === 0 && <span className="hint">Sin lotes ni series registrados.</span>}
              </div>

              <h3>Proveedores y referencias</h3>
              <div className="chip-row">
                {detail.suppliers.map((supplier) => (
                  <span className="chip" key={supplier.id}>{supplier.supplier_name} · {supplier.currency} {formatNumber(supplier.last_unit_cost)}</span>
                ))}
                {detail.cross_references.map((reference) => (
                  <span className="chip" key={reference.id}>{reference.reference_type}: {reference.reference_code}{reference.authorised ? ' · autorizada' : ''}</span>
                ))}
                {detail.suppliers.length === 0 && detail.cross_references.length === 0 && <span className="hint">Sin proveedores ni referencias registradas.</span>}
              </div>

              <h3>Últimos movimientos</h3>
              {detail.movements.length === 0 ? (
                <EmptyState text="Sin movimientos registrados para este artículo." />
              ) : (
                <ul className="timeline">
                  {detail.movements.map((movement) => (
                    <li key={movement.id}>
                      <strong>{movement.movement_no} · {movement.movement_type} ({movement.direction})</strong>
                      <span>{formatNumber(movement.quantity)} {detail.uom_code} · saldo {formatNumber(movement.balance_after_qty)}</span>
                      <small>{new Date(movement.posted_at).toLocaleString('es-MX')} · {movement.source_document_type}</small>
                    </li>
                  ))}
                </ul>
              )}

              <h3>Documentos relacionados</h3>
              <div className="chip-row">
                {detail.related_documents.map((document, index) => (
                  <span className="chip" key={`${document.document_no}-${index}`}>
                    {document.document_type} {document.document_no} · {document.status}
                  </span>
                ))}
                {detail.related_documents.length === 0 && <span className="hint">Sin documentos relacionados.</span>}
              </div>
            </div>
          )}
        </Panel>
      </div>
    </>
  );
}
