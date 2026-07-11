import { useState, useCallback, useEffect } from 'react';
import { CopilotKit } from "@copilotkit/react-core";
import { CopilotChat } from "@copilotkit/react-ui";
import "@copilotkit/react-ui/styles.css";

import ConnectionForm from './components/ConnectionForm';
import Sidebar from './components/Sidebar';
import DataGrid from './components/DataGrid';
import { previewTable } from './api';
import type { ConnectionDetails } from './types';
import { Database, X, LogOut, ChevronRight, Table2, Sparkles } from 'lucide-react';

const STORAGE_KEY = 'pgcopilot_connection';

/** Read saved connection from localStorage */
function loadSavedConnection(): ConnectionDetails | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as ConnectionDetails) : null;
  } catch {
    return null;
  }
}

/** Save connection to localStorage */
function saveConnection(details: ConnectionDetails) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(details));
}

/** Clear saved connection */
function clearConnection() {
  localStorage.removeItem(STORAGE_KEY);
}

export default function App() {
  const [isConnected, setIsConnected] = useState(false);
  const [connectionDetails, setConnectionDetails] = useState<ConnectionDetails | null>(null);
  const [tableData, setTableData] = useState<any[]>([]);
  const [currentTable, setCurrentTable] = useState('');
  const [currentDb, setCurrentDb] = useState('');
  const [chatOpen, setChatOpen] = useState(false);
  const [restoring, setRestoring] = useState(true); // show a loading spinner while we auto-reconnect

  // On mount: instantly restore from localStorage — no network round-trip.
  // If the DB is actually unreachable the table list will show an error naturally.
  useEffect(() => {
    const saved = loadSavedConnection();
    if (saved) {
      setConnectionDetails(saved);
      setIsConnected(true);
    }
    setRestoring(false);
  }, []);

  const handleConnect = useCallback((details: ConnectionDetails) => {
    saveConnection(details);
    setConnectionDetails(details);
    setIsConnected(true);
  }, []);

  const handleDisconnect = useCallback(() => {
    clearConnection();
    setIsConnected(false);
    setConnectionDetails(null);
    setTableData([]);
    setCurrentTable('');
    setChatOpen(false);
  }, []);

  const handleSelectTable = useCallback(async (db: string, table: string) => {
    if (!connectionDetails) return;
    setCurrentDb(db);
    setCurrentTable(table);
    try {
      const response = await previewTable(connectionDetails, table);
      const rows = Array.isArray(response) ? response : response?.data ?? [];
      setTableData(rows);
    } catch (e) {
      console.error(e);
      setTableData([]);
    }
  }, [connectionDetails]);

  // While auto-restoring, show a centered spinner
  if (restoring) {
    return (
      <div className="restore-screen">
        <div className="restore-card">
          <div className="restore-spinner" />
          <span className="restore-text">Reconnecting…</span>
        </div>
      </div>
    );
  }

  if (!isConnected || !connectionDetails) {
    return <ConnectionForm onConnect={handleConnect} />;
  }

  return (
    <CopilotKit url="http://localhost:8000/api/copilotkit">
      <div className="app-shell">

        {/* ── Top Bar ── */}
        <header className="topbar">
          <div className="topbar-left">
            <div className="topbar-logo"><Database size={14} /></div>
            <span className="topbar-title">PG Copilot</span>
            <span className="topbar-badge">AI</span>
          </div>
          <div className="topbar-right">
            <button id="btn-disconnect" className="disconnect-btn" onClick={handleDisconnect} title="Disconnect">
              <LogOut size={12} />
              Disconnect
            </button>
          </div>
        </header>

        {/* ── Body ── */}
        <div className="app-body">
          <Sidebar connection={connectionDetails} onSelectTable={handleSelectTable} />

          <main className="main-content">
            <div className="table-toolbar">
              <div className="table-breadcrumb">
                <Database size={12} />
                <span className="table-breadcrumb-seg">{currentDb || connectionDetails.database}</span>
                {currentTable && (
                  <>
                    <ChevronRight size={12} />
                    <Table2 size={12} />
                    <span className="table-breadcrumb-seg active">{currentTable}</span>
                  </>
                )}
              </div>
              {tableData.length > 0 && <span className="table-meta">{tableData.length} rows</span>}
            </div>

            <DataGrid data={tableData} />

            <div className="statusbar">
              <div className="statusbar-left">
                <span className="statusbar-item">PostgreSQL · {connectionDetails.host}:{connectionDetails.port}</span>
                {currentTable && <span className="statusbar-item">{currentTable}</span>}
              </div>
              <div className="statusbar-right">
                {tableData.length > 0 && <span className="statusbar-item">{tableData.length} rows</span>}
                <span className="statusbar-item">UTF-8</span>
              </div>
            </div>
          </main>
        </div>

        {/* ── Chat Panel (flush to right edge of screen) ── */}
        {chatOpen && (
          <div className="chat-panel" id="chat-panel">
            {/* Custom header */}
            <div className="chat-panel-header">
              <div className="chat-panel-header-left">
                <div className="chat-panel-avatar"><Sparkles size={14} /></div>
                <div>
                  <div className="chat-panel-title">PG Copilot AI</div>
                  <div className="chat-panel-subtitle">SQL expert · always online</div>
                </div>
              </div>
              <button id="btn-close-chat" className="chat-panel-close" onClick={() => setChatOpen(false)} aria-label="Close chat">
                <X size={16} />
              </button>
            </div>

            {/* CopilotChat — inline embeddable component */}
            <div className="chat-panel-body">
              <CopilotChat
                className="ck-chat-inner"
                labels={{
                  title: "PG Copilot",
                  initial: `Connected to **${connectionDetails.database}**.\n\nAsk me anything — I can list tables, describe schemas, and run SQL queries for you.`,
                }}
                instructions="You are a SQL expert assistant. The user has connected to a Postgres Server. Use the available tools to list tables, get schemas, or run queries based on their request."
              />
            </div>
          </div>
        )}

        {/* ── Floating Action Button — only visible when chat is CLOSED ── */}
        {!chatOpen && (
          <button
            id="btn-chat-fab"
            className="chat-fab"
            onClick={() => setChatOpen(true)}
            title="Open AI Assistant"
            aria-label="Open AI Assistant"
          >
            <Sparkles size={20} />
            <span className="chat-fab-ripple" />
          </button>
        )}

      </div>
    </CopilotKit>
  );
}