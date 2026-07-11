import { useState, useEffect } from 'react';
import { getTables } from '../api';
import type { ConnectionDetails } from '../types';
import { Table2, Search, Loader2, Database } from 'lucide-react';

interface SidebarProps {
  connection: ConnectionDetails;
  onSelectTable: (db: string, table: string) => void;
}

export default function Sidebar({ connection, onSelectTable }: SidebarProps) {
  const [tables, setTables] = useState<string[]>([]);
  const [selectedTable, setSelectedTable] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  useEffect(() => {
    if (!connection) return;
    setLoading(true);

    getTables(connection)
      .then((data: string[]) => {
        setTables(data);
        if (data[0]) {
          setSelectedTable(data[0]);
          onSelectTable(connection.database, data[0]);
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [connection]);

  const handleSelect = (table: string) => {
    setSelectedTable(table);
    onSelectTable(connection.database, table);
  };

  const filtered = tables.filter(t =>
    t.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <aside className="sidebar">
      {/* Header */}
      <div className="sidebar-section-header">
        <Database size={11} />
        <span>Explorer</span>
      </div>

      {/* DB badge */}
      <div style={{
        padding: '8px 14px',
        fontSize: '12px',
        color: 'var(--text-secondary)',
        borderBottom: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'center',
        gap: '6px'
      }}>
        <span style={{
          width: '8px', height: '8px',
          borderRadius: '50%',
          background: 'var(--success)',
          boxShadow: '0 0 6px rgba(34,197,94,0.5)',
          flexShrink: 0,
          display: 'inline-block'
        }} />
        <span style={{ fontWeight: 500, color: 'var(--text-primary)', fontSize: '12px' }}>
          {connection.database}
        </span>
        <span style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
          @ {connection.host}
        </span>
      </div>

      {/* Search */}
      <div className="sidebar-search">
        <div className="sidebar-search-wrap">
          <Search className="sidebar-search-icon" size={12} />
          <input
            type="text"
            placeholder="Filter tables…"
            className="sidebar-search-input"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
      </div>

      {/* Table count */}
      <div style={{
        padding: '4px 14px 2px',
        fontSize: '10px',
        color: 'var(--text-muted)',
        letterSpacing: '0.3px'
      }}>
        {loading ? '' : `${filtered.length} table${filtered.length !== 1 ? 's' : ''}`}
      </div>

      {/* Tables list */}
      <div className="sidebar-tables">
        {loading ? (
          <div className="sidebar-loading">
            <div className="sidebar-loading-spinner" />
            <span>Loading tables…</span>
          </div>
        ) : filtered.length === 0 ? (
          <div className="sidebar-empty">
            {search ? `No tables matching "${search}"` : 'No tables found'}
          </div>
        ) : (
          filtered.map(table => (
            <div
              key={table}
              id={`table-item-${table}`}
              className={`table-item${selectedTable === table ? ' active' : ''}`}
              onClick={() => handleSelect(table)}
              title={table}
            >
              <Table2 size={13} />
              <span className="table-item-name">{table}</span>
            </div>
          ))
        )}
      </div>

      {/* Footer */}
      <div className="sidebar-footer">
        <span className="sidebar-footer-dot" />
        <span>Connected</span>
        <span style={{ color: 'var(--border-light)', margin: '0 2px' }}>·</span>
        <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '10px' }}>
          {connection.host}:{connection.port}
        </span>
      </div>
    </aside>
  );
}