import { useEffect, useState, type FormEvent } from 'react';
import { api } from '../api/client';
import type { WmsItem } from '../api/types';
import { Icon } from './Icon';
import { ErrorMessage, formatNumber, InlineFieldError } from './ui';

/**
 * Buscador de artículos reutilizable. El backend WMS ya indexa código,
 * descripción, fabricante, número de parte y código de barras en `query`.
 * La selección no muta el catálogo: solo entrega el artículo elegido al
 * formulario que lo consume.
 */
export function ItemPicker({
  selectedId,
  warehouseId,
  onSelect,
  disabled = false,
}: {
  selectedId?: string | null;
  warehouseId?: string | null;
  onSelect: (item: WmsItem) => void;
  disabled?: boolean;
}) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<WmsItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function search(event?: FormEvent): Promise<void> {
    event?.preventDefault();
    setLoading(true);
    setError(null);
    setSearched(true);
    try {
      setResults(
        await api.wmsSearchItems({
          query: query.trim() || undefined,
          warehouse_id: warehouseId || undefined,
          active_only: true,
          limit: 30,
        }),
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No fue posible buscar artículos.');
      setResults([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void search();
    // La búsqueda inicial se hace una vez; los cambios de almacén se aplican
    // al presionar "Buscar" para no generar peticiones involuntarias.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="item-picker">
      <form className="search-toolbar" onSubmit={(event) => void search(event)}>
        <label>
          <Icon name="search" size={15} /> Buscar artículo
          <input
            value={query}
            disabled={disabled}
            placeholder="Código, descripción o número de parte"
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <button className="button button-secondary" type="submit" disabled={disabled || loading}>
          {loading ? 'Buscando…' : 'Buscar'}
        </button>
      </form>
      <ErrorMessage message={error} />
      <InlineFieldError message={searched && results.length === 0 && !loading ? 'Sin coincidencias con esos criterios.' : null} />
      {!loading && results.length > 0 && (
        <div className="picker-results" role="list">
          {results.map((item) => (
            <button
              key={item.id}
              type="button"
              role="listitem"
              className={`picker-result${item.id === selectedId ? ' picker-result-active' : ''}`}
              disabled={disabled}
              onClick={() => onSelect(item)}
            >
              <strong>{item.code} · {item.description}</strong>
              <small>
                {item.manufacturer_part_no ? `Parte ${item.manufacturer_part_no} · ` : ''}
                {item.uom_code} · Disponible {formatNumber(item.available_qty)}
              </small>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
