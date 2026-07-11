import React, { useState } from 'react';
import { Database, Server, User, Key, Globe, Loader2, ShieldCheck, AlertCircle } from 'lucide-react';
import { connectToDb } from '../api';
import type { ConnectionDetails } from '../types';

export default function ConnectionForm({ onConnect }: { onConnect: (details: ConnectionDetails) => void }) {
  const [formData, setFormData] = useState<ConnectionDetails>({
    host: 'localhost',
    port: '5432',
    user: 'postgres',
    password: 'sanju140908',
    database: 'hackathon',
    ssl: false
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      await connectToDb(formData);
      onConnect(formData);
    } catch (err: any) {
      setError(err.message || 'Connection failed. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  const set = (field: keyof ConnectionDetails) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setFormData(prev => ({ ...prev, [field]: e.target.value }));

  return (
    <div className="conn-page">
      <div className="conn-card animate-fade-in-up">
        {/* Header */}
        <div className="conn-logo">
          <div className="conn-logo-icon">
            <Database size={20} />
          </div>
          <div>
            <div className="conn-title">PG Copilot</div>
          </div>
        </div>
        <p className="conn-subtitle">Connect to your PostgreSQL server to get started</p>

        <form onSubmit={handleSubmit} className="conn-form">
          {/* Host */}
          <div className="field-wrap">
            <Server className="field-icon" size={15} />
            <input
              id="field-host"
              type="text"
              placeholder="Host"
              className="field-input"
              value={formData.host}
              onChange={set('host')}
              autoComplete="off"
              autoCorrect="off"
              spellCheck={false}
            />
          </div>

          {/* Port + Database */}
          <div className="form-row">
            <div className="field-wrap">
              <Globe className="field-icon" size={15} />
              <input
                id="field-port"
                type="text"
                placeholder="Port"
                className="field-input"
                value={formData.port}
                onChange={set('port')}
                autoComplete="off"
              />
            </div>
            <div className="field-wrap">
              <Database className="field-icon" size={15} />
              <input
                id="field-database"
                type="text"
                placeholder="Database"
                className="field-input"
                value={formData.database}
                onChange={set('database')}
                autoComplete="off"
              />
            </div>
          </div>

          {/* Username */}
          <div className="field-wrap">
            <User className="field-icon" size={15} />
            <input
              id="field-user"
              type="text"
              placeholder="Username"
              className="field-input"
              value={formData.user}
              onChange={set('user')}
              autoComplete="username"
            />
          </div>

          {/* Password */}
          <div className="field-wrap">
            <Key className="field-icon" size={15} />
            <input
              id="field-password"
              type="password"
              placeholder="Password"
              className="field-input"
              value={formData.password}
              onChange={set('password')}
              autoComplete="current-password"
            />
          </div>

          {/* SSL */}
          <label className="ssl-toggle" htmlFor="field-ssl">
            <input
              id="field-ssl"
              type="checkbox"
              className="ssl-checkbox"
              checked={formData.ssl}
              onChange={e => setFormData(prev => ({ ...prev, ssl: e.target.checked }))}
            />
            <ShieldCheck size={14} style={{ color: formData.ssl ? 'var(--accent-light)' : 'var(--text-muted)', flexShrink: 0 }} />
            <span className="ssl-label">Enable SSL / TLS encryption</span>
          </label>

          {/* Error */}
          {error && (
            <div className="error-msg">
              <AlertCircle size={14} style={{ flexShrink: 0 }} />
              <span>{error}</span>
            </div>
          )}

          {/* Submit */}
          <button
            id="btn-connect"
            type="submit"
            disabled={loading}
            className="btn-connect"
          >
            {loading ? (
              <>
                <span className="btn-spinner" />
                Connecting…
              </>
            ) : (
              <>
                <Database size={15} />
                Connect to PostgreSQL
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
}