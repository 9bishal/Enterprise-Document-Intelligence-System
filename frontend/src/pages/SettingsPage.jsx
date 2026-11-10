import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { SettingsIcon, ShieldIcon, LockIcon, BarChartIcon, ZapIcon, CopyIcon, CheckIcon } from '../components/Icons';
import PasswordInput from '../components/PasswordInput';
import { PROVIDER_MODELS } from '../utils/constants';

export default function SettingsPage({
  apiKeys,
  handleApiKeyChange,
  modelConfig,
  setModelConfig,
  isGlobalConfigEnforced,
  userRole
}) {
  const navigate = useNavigate();
  const [copyFeedback, setCopyFeedback] = useState({});
  
  // Only Admins can see and configure API keys
  const isAdmin = userRole === 'Admin';

  const providerModels = PROVIDER_MODELS;

  const handleProviderChange = (e) => {
    const provider = e.target.value;
    const defaultModel = providerModels[provider][0].id;
    setModelConfig({
      ...modelConfig,
      provider,
      model: defaultModel
    });
  };

  const handleConfigValueChange = (key, val) => {
    setModelConfig({
      ...modelConfig,
      [key]: val
    });
  };

  const handleCopyToClipboard = (text, key) => {
    navigator.clipboard.writeText(text);
    setCopyFeedback({ ...copyFeedback, [key]: true });
    setTimeout(() => {
      setCopyFeedback({ ...copyFeedback, [key]: false });
    }, 2000);
  };

  return (
    <div className="settings-page">
      {/* Header */}
      <div className="settings-header">
        <div className="header-content">
          <SettingsIcon style={{ width: 28, height: 28, color: '#111111' }} />
          <div>
            <h1>System Configuration</h1>
            <p className="subtitle">Configure LLM providers, API keys, and model parameters</p>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {isAdmin && (
            <button onClick={() => navigate('/admin')} className="admin-console-btn" title="Open Admin Console">
              <ShieldIcon style={{ width: 16, height: 16, verticalAlign: 'middle', marginRight: 6 }} />
              Admin Console
            </button>
          )}
          <button onClick={() => navigate('/query')} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}><h1>Back to Workspace</h1></button>
        </div>
      </div>

      {/* Global Config Warning */}
      {isGlobalConfigEnforced && (
        <div className="info-banner">
<ShieldIcon style={{ width: 16, height: 16, verticalAlign: 'middle' }} />
          <p>Global configuration is enforced by your administrator. Local settings are read-only.</p>
        </div>
      )}

      <div className="settings-container">
        {/* API Keys Section - Only visible to Admins */}
        {isAdmin ? (
        <section className="settings-section">
          <h2 className="section-title">API Keys & Credentials</h2>
          <p className="section-description">
            Provide API keys for the LLM providers you want to use. Keys are stored locally in your browser.
          </p>

          <div className="settings-grid">
            {/* Groq */}
            <div className="settings-card">
              <div className="card-header">
                <h3>Groq</h3>
                <span className="badge free">Free</span>
              </div>
              <p className="provider-desc">Fast inference API with Llama and Mixtral models</p>
              <div className="input-group">
                <label>API Key</label>
                <div className="input-with-action">
                  <PasswordInput
                    wrapperStyle={{ flex: 1 }}
                    placeholder="gsk_..."
                    value={apiKeys.groq || ''}
                    onChange={(e) => handleApiKeyChange('groq', e.target.value)}
                    disabled={isGlobalConfigEnforced}
                  />
                  {apiKeys.groq && (
                    <button
                      className="action-btn"
                      onClick={() => handleCopyToClipboard(apiKeys.groq, 'groq')}
                      title="Copy to clipboard"
                    >
                      {copyFeedback.groq ? <CheckIcon style={{ width: 14, height: 14, color: '#15803d' }} /> : <CopyIcon style={{ width: 14, height: 14 }} />}
                    </button>
                  )}
                </div>
                <a href="https://console.groq.com" target="_blank" rel="noopener noreferrer" className="link">
                  Get free API key →
                </a>
              </div>
            </div>

            {/* Gemini */}
            <div className="settings-card">
              <div className="card-header">
                <h3>Google Gemini</h3>
                <span className="badge free">Free Tier</span>
              </div>
              <p className="provider-desc">Advanced reasoning with Google's latest models</p>
              <div className="input-group">
                <label>API Key</label>
                <div className="input-with-action">
                  <PasswordInput
                    wrapperStyle={{ flex: 1 }}
                    placeholder="AIza..."
                    value={apiKeys.gemini || ''}
                    onChange={(e) => handleApiKeyChange('gemini', e.target.value)}
                    disabled={isGlobalConfigEnforced}
                  />
                  {apiKeys.gemini && (
                    <button
                      className="action-btn"
                      onClick={() => handleCopyToClipboard(apiKeys.gemini, 'gemini')}
                      title="Copy to clipboard"
                    >
                      {copyFeedback.gemini ? <CheckIcon style={{ width: 14, height: 14, color: '#15803d' }} /> : <CopyIcon style={{ width: 14, height: 14 }} />}
                    </button>
                  )}
                </div>
                <a href="https://makersuite.google.com" target="_blank" rel="noopener noreferrer" className="link">
                  Get free API key →
                </a>
              </div>
            </div>

            {/* OpenAI */}
            <div className="settings-card">
              <div className="card-header">
                <h3>OpenAI</h3>
                <span className="badge paid">Paid</span>
              </div>
              <p className="provider-desc">GPT-4o and other advanced models</p>
              <div className="input-group">
                <label>API Key</label>
                <div className="input-with-action">
                  <PasswordInput
                    wrapperStyle={{ flex: 1 }}
                    placeholder="sk-..."
                    value={apiKeys.openai || ''}
                    onChange={(e) => handleApiKeyChange('openai', e.target.value)}
                    disabled={isGlobalConfigEnforced}
                  />
                  {apiKeys.openai && (
                    <button
                      className="action-btn"
                      onClick={() => handleCopyToClipboard(apiKeys.openai, 'openai')}
                      title="Copy to clipboard"
                    >
                      {copyFeedback.openai ? <CheckIcon style={{ width: 14, height: 14, color: '#15803d' }} /> : <CopyIcon style={{ width: 14, height: 14 }} />}
                    </button>
                  )}
                </div>
                <a href="https://platform.openai.com" target="_blank" rel="noopener noreferrer" className="link">
                  Get API key →
                </a>
              </div>
            </div>
          </div>
        </section>
        ) : (
          <section className="settings-section" style={{ border: '1px solid var(--border)', borderRadius: '8px', padding: '24px', backgroundColor: 'rgba(0, 0, 0, 0.02)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', color: 'var(--text-muted)' }}>
              <LockIcon style={{ width: 20, height: 20 }} />
              <div>
                <h3 style={{ margin: '0 0 4px 0', color: '#111111' }}>API Keys & Credentials</h3>
                <p style={{ margin: '0', fontSize: '13px' }}>API key management is restricted to administrators only. Contact your admin to configure API keys.</p>
              </div>
            </div>
          </section>
        )}

        {/* Model Configuration Section */}
        <section className="settings-section">
          <h2 className="section-title">Model Configuration</h2>
          <p className="section-description">
            Choose your preferred LLM provider and configure model parameters
          </p>

          <div className="config-grid">
            {/* Provider Selection */}
            <div className="config-card">
              <label className="config-label">LLM Provider</label>
              <select
                value={modelConfig.provider || 'groq'}
                onChange={handleProviderChange}
                disabled={isGlobalConfigEnforced}
                className="config-select"
              >
                <option value="groq">Groq (Free, Fast)</option>
                <option value="gemini">Google Gemini</option>
                <option value="openai">OpenAI</option>
                <option value="ollama">Ollama (Local)</option>
              </select>
              <p className="config-help">
                Select the LLM provider to use for query responses
              </p>
            </div>

            {/* Model Selection */}
            <div className="config-card">
              <label className="config-label">Model</label>
              <select
                value={modelConfig.model || ''}
                onChange={(e) => handleConfigValueChange('model', e.target.value)}
                disabled={isGlobalConfigEnforced}
                className="config-select"
              >
                {(providerModels[modelConfig.provider] || []).map(m => (
                  <option key={m.id} value={m.id}>{m.name}</option>
                ))}
              </select>
              <p className="config-help">
                Choose the specific model variant
              </p>
            </div>

            {/* Temperature */}
            <div className="config-card">
              <label className="config-label">
                Temperature: {modelConfig.temperature || 0.3}
              </label>
              <input
                type="range"
                min="0"
                max="2"
                step="0.1"
                value={modelConfig.temperature || 0.3}
                onChange={(e) => handleConfigValueChange('temperature', parseFloat(e.target.value))}
                disabled={isGlobalConfigEnforced}
                className="config-slider"
              />
              <div className="slider-labels">
                <span>Precise</span>
                <span>Balanced</span>
                <span>Creative</span>
              </div>
              <p className="config-help">
                Lower = more precise, Higher = more creative
              </p>
            </div>

            {/* Top K */}
            <div className="config-card">
              <label className="config-label">
                Top K (Retrieval): {modelConfig.k || 4}
              </label>
              <input
                type="range"
                min="1"
                max="10"
                step="1"
                value={modelConfig.k || 4}
                onChange={(e) => handleConfigValueChange('k', parseInt(e.target.value))}
                disabled={isGlobalConfigEnforced}
                className="config-slider"
              />
              <p className="config-help">
                Number of documents to retrieve for context
              </p>
            </div>
          </div>
        </section>

        {/* Information Section */}
        <section className="settings-section">
          <h2 className="section-title">Information & Help</h2>

          <div className="info-grid">
            <div className="info-card">
              <h4><LockIcon style={{ width: 16, height: 16, verticalAlign: 'middle', marginRight: 6 }} /> Security & Privacy</h4>
              <p>Your API keys are stored locally in your browser. They are never sent to our servers and are only used for direct API calls to the providers.</p>
            </div>

            <div className="info-card">
              <h4><SettingsIcon style={{ width: 16, height: 16, verticalAlign: 'middle', marginRight: 6 }} /> Configuration Impact</h4>
              <p>Model configuration affects how the system retrieves documents and generates responses. Adjust these settings based on your use case and provider capabilities.</p>
            </div>

            <div className="info-card">
              <h4><BarChartIcon style={{ width: 16, height: 16, verticalAlign: 'middle', marginRight: 6 }} /> Provider Comparison</h4>
              <p>
                <strong>Groq:</strong> Fast, free, great for RAG. 
                <strong>Gemini:</strong> Advanced reasoning. 
                <strong>OpenAI:</strong> Most capable, paid.
              </p>
            </div>

            <div className="info-card">
              <h4><ZapIcon style={{ width: 16, height: 16, verticalAlign: 'middle', marginRight: 6 }} /> Tips</h4>
              <p>Start with Groq for free tier. Adjust temperature based on use case. Use higher K for comprehensive retrieval.</p>
            </div>
          </div>
        </section>
      </div>

      <style jsx>{`
        .settings-page {
          display: flex;
          flex-direction: column;
          gap: 24px;
          width: 100%;
          max-width: 1200px;
          margin: 0 auto;
        }

        .settings-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
        }

        .header-content {
          display: flex;
          align-items: center;
          gap: 16px;
        }

        .settings-header h1 {
          margin: 0;
          font-size: 28px;
          font-weight: 700;
          color: #111111;
        }

        .subtitle {
          margin: 8px 0 0 0;
          font-size: 14px;
          color: #9ca3af;
        }

        .admin-console-btn {
          padding: 10px 16px;
          background: #111111;
          color: #ffffff;
          border: 1px solid #111111;
          border-radius: 8px;
          font-size: 13px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
          white-space: nowrap;
        }

        .admin-console-btn:hover {
          background: #333333;
          border-color: #333333;
          transform: translateY(-1px);
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
        }

        .info-banner {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 12px 16px;
          background: rgba(0, 0, 0, 0.04);
          border: 1px solid rgba(0, 0, 0, 0.12);
          border-radius: 8px;
          color: #525252;
          font-size: 13px;
        }

        .info-banner p {
          margin: 0;
        }

        .settings-container {
          display: flex;
          flex-direction: column;
          gap: 32px;
        }

        .settings-section {
          display: flex;
          flex-direction: column;
          gap: 16px;
        }

        .section-title {
          margin: 0;
          font-size: 20px;
          font-weight: 700;
          color: #111111;
        }

        .section-description {
          margin: 0;
          font-size: 14px;
          color: #9ca3af;
        }

        .settings-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
          gap: 16px;
        }

        .settings-card {
          background: white;
          border: 1px solid rgba(0, 0, 0, 0.08);
          border-radius: 12px;
          padding: 20px;
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .card-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 8px;
        }

        .card-header h3 {
          margin: 0;
          font-size: 16px;
          font-weight: 700;
          color: #111111;
        }

        .badge {
          display: inline-flex;
          align-items: center;
          padding: 4px 8px;
          border-radius: 4px;
          font-size: 10px;
          font-weight: 700;
          text-transform: uppercase;
        }

        .badge.free {
          background: rgba(21, 128, 61, 0.12);
          color: #15803d;
        }

        .badge.paid {
          background: rgba(180, 83, 9, 0.12);
          color: #b45309;
        }

        .provider-desc {
          margin: 0;
          font-size: 13px;
          color: #9ca3af;
        }

        .input-group {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .input-group label {
          font-size: 12px;
          font-weight: 600;
          color: #111111;
        }

        .input-with-action {
          display: flex;
          gap: 6px;
          align-items: center;
        }

        .input-group input {
          flex: 1;
          padding: 8px 12px;
          border: 1px solid rgba(0, 0, 0, 0.15);
          border-radius: 6px;
          font-size: 13px;
          color: #111111;
          font-family: monospace;
        }

        .input-group input:focus {
          outline: none;
          border-color: #111111;
          box-shadow: 0 0 0 3px rgba(0, 0, 0, 0.08);
        }

        .input-group input:disabled {
          background: rgba(0, 0, 0, 0.04);
          color: #9ca3af;
        }

        .action-btn {
          padding: 6px 10px;
          background: rgba(0, 0, 0, 0.06);
          border: 1px solid rgba(0, 0, 0, 0.15);
          border-radius: 4px;
          cursor: pointer;
          font-size: 13px;
          color: #111111;
          transition: all 0.2s;
          white-space: nowrap;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .action-btn:hover {
          background: rgba(0, 0, 0, 0.12);
          border-color: rgba(0, 0, 0, 0.3);
        }

        .link {
          font-size: 11px;
          color: #525252;
          text-decoration: none;
          transition: color 0.2s;
        }

        .link:hover {
          color: #111111;
          text-decoration: underline;
        }

        .config-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
          gap: 16px;
        }

        .config-card {
          background: white;
          border: 1px solid rgba(0, 0, 0, 0.08);
          border-radius: 12px;
          padding: 16px;
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .config-label {
          font-size: 13px;
          font-weight: 600;
          color: #111111;
        }

        .config-select,
        .config-slider {
          padding: 8px 12px;
          border: 1px solid rgba(0, 0, 0, 0.15);
          border-radius: 6px;
          font-size: 13px;
          color: #111111;
          background: white;
          transition: all 0.2s;
        }

        .config-select:focus {
          outline: none;
          border-color: #111111;
          box-shadow: 0 0 0 3px rgba(0, 0, 0, 0.08);
        }

        .config-select:disabled,
        .config-slider:disabled {
          background: rgba(0, 0, 0, 0.04);
          color: #9ca3af;
          cursor: not-allowed;
        }

        .config-slider {
          height: 6px;
          padding: 0;
          cursor: pointer;
          accent-color: #111111;
        }

        .slider-labels {
          display: flex;
          justify-content: space-between;
          font-size: 11px;
          color: #9ca3af;
          margin: 0 2px;
        }

        .config-help {
          margin: 0;
          font-size: 11px;
          color: #9ca3af;
        }

        .info-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
          gap: 16px;
        }

        .info-card {
          background: rgba(0, 0, 0, 0.03);
          border: 1px solid rgba(0, 0, 0, 0.08);
          border-radius: 8px;
          padding: 16px;
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .info-card h4 {
          margin: 0;
          font-size: 13px;
          font-weight: 700;
          color: #111111;
        }

        .info-card p {
          margin: 0;
          font-size: 12px;
          color: #9ca3af;
          line-height: 1.5;
        }

        @media (max-width: 768px) {
          .settings-page {
            gap: 16px;
          }

          .settings-grid,
          .config-grid,
          .info-grid {
            grid-template-columns: 1fr;
          }

          .settings-header {
            flex-direction: column;
            align-items: flex-start;
          }
        }
      `}</style>
    </div>
  );
}
