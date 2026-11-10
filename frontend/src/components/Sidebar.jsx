import { useRef } from 'react';
import { 
  SparklesIcon, FileIcon, UploadIcon, TrashIcon, FolderIcon, ShieldIcon, AlertTriangleIcon
} from './Icons';
import PasswordInput from './PasswordInput';
import { PROVIDER_MODELS } from '../utils/constants';

export default function Sidebar({
  documents,
  onUpload,
  onDeleteDocument,
  apiKeys,
  onApiKeyChange,
  modelConfig,
  onModelConfigChange,
  isGlobalConfigEnforced,
  uploading,
  currentUser,
  currentUserRole,
  currentUserDepartment,
  adminActiveDepartment,
  setAdminActiveDepartment,
  activeTab,
  setActiveTab,
  onLogout
}) {
  const fileInputRef = useRef(null);

  const providerModels = PROVIDER_MODELS;

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      onUpload(e.target.files[0]);
    }
  };

  const triggerFileInput = () => {
    fileInputRef.current.click();
  };

  const handleProviderChange = (e) => {
    const provider = e.target.value;
    const defaultModel = providerModels[provider][0].id;
    onModelConfigChange({
      ...modelConfig,
      provider,
      model: defaultModel
    });
  };

  const handleConfigValueChange = (key, val) => {
    onModelConfigChange({
      ...modelConfig,
      [key]: val
    });
  };

  return (
    <aside className="sidebar glass-panel">
      <div className="sidebar-header" style={{ marginBottom: currentUserRole === 'Admin' ? '12px' : '20px' }}>
        <div className="logo-icon">
          <SparklesIcon style={{ width: 18, height: 18, color: '#030712' }} />
        </div>
        <h1 className="logo-text">Intradoc AI</h1>
      </div>

      {/* Admin Tab Switcher */}
      {currentUserRole === 'Admin' && (
        <div style={{
          display: 'flex',
          gap: '8px',
          padding: '4px',
          backgroundColor: 'rgba(36, 50, 82, 0.04)',
          borderRadius: '12px',
          margin: '0 16px 16px 16px'
        }}>
          <button
            onClick={() => setActiveTab('workspace')}
            style={{
              flex: 1,
              padding: '8px',
              borderRadius: '8px',
              fontSize: '12px',
              fontWeight: 600,
              border: 'none',
              backgroundColor: activeTab === 'workspace' ? '#FFFFFF' : 'transparent',
              color: activeTab === 'workspace' ? '#1a1c20' : '#8b92a0',
              cursor: 'pointer',
              boxShadow: activeTab === 'workspace' ? '0 2px 4px rgba(36, 50, 82, 0.04)' : 'none',
              transition: 'all 0.2s ease'
            }}
          >
            RAG Workspace
          </button>
          <button
            onClick={() => setActiveTab('admin')}
            style={{
              flex: 1,
              padding: '8px',
              borderRadius: '8px',
              fontSize: '12px',
              fontWeight: 600,
              border: 'none',
              backgroundColor: activeTab === 'admin' ? '#FFFFFF' : 'transparent',
              color: activeTab === 'admin' ? '#1a1c20' : '#8b92a0',
              cursor: 'pointer',
              boxShadow: activeTab === 'admin' ? '0 2px 4px rgba(36, 50, 82, 0.04)' : 'none',
              transition: 'all 0.2s ease'
            }}
          >
            Admin Panel
          </button>
        </div>
      )}

      <div className="sidebar-scroll">
        {/* Document Ingestion Section */}
        <div>
          <div className="sidebar-section-title">
            <span>Documents Manager</span>
            <span>{documents.length} files</span>
          </div>

          <input 
            type="file" 
            ref={fileInputRef} 
            onChange={handleFileChange} 
            style={{ display: 'none' }}
            accept=".pdf,.docx,.txt,.md"
          />

          <div 
            className="upload-zone" 
            onClick={currentUserRole === 'Viewer' ? null : triggerFileInput}
            style={{
              opacity: currentUserRole === 'Viewer' ? 0.6 : 1,
              cursor: currentUserRole === 'Viewer' ? 'not-allowed' : 'pointer',
              backgroundColor: currentUserRole === 'Viewer' ? '#FAF9F5' : 'transparent',
              borderColor: currentUserRole === 'Viewer' ? 'rgba(36, 50, 82, 0.04)' : 'var(--panel-border)',
              pointerEvents: currentUserRole === 'Viewer' ? 'none' : 'auto'
            }}
          >
            <UploadIcon style={{ color: currentUserRole === 'Viewer' ? '#8b92a0' : 'inherit' }} />
            {uploading ? (
              <p>Uploading & indexing...</p>
            ) : currentUserRole === 'Viewer' ? (
              <>
                <p style={{ color: '#8b92a0' }}>Upload Restricted</p>
                <span style={{ fontSize: '10px' }}>Only Editors and Admins can upload</span>
              </>
            ) : (
              <>
                <p>Click or drag file to upload</p>
                <span>Supports PDF, DOCX, TXT, MD</span>
              </>
            )}
          </div>
          
          <div style={{
            marginTop: '12px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '6px 12px',
            backgroundColor: 'rgba(36, 50, 82, 0.03)',
            borderRadius: '8px',
            border: '1px solid rgba(36, 50, 82, 0.05)',
            gap: '6px'
          }}>
            <span style={{ fontSize: '11px', color: '#8b92a0', display: 'flex', alignItems: 'center', gap: 4 }}>
              <FolderIcon style={{ width: 12, height: 12 }} /> Workspace:
            </span>
            {currentUserRole === 'Admin' ? (
              <select 
                value={adminActiveDepartment}
                onChange={(e) => setAdminActiveDepartment(e.target.value)}
                style={{
                  fontSize: '11px',
                  fontWeight: '600',
                  color: '#1a1c20',
                  background: 'transparent',
                  border: 'none',
                  outline: 'none',
                  cursor: 'pointer',
                  maxWidth: '120px',
                  textOverflow: 'ellipsis'
                }}
              >
                <option value="All Departments">All Departments</option>
                <option value="HR">HR</option>
                <option value="Legal">Legal</option>
                <option value="Finance">Finance</option>
                <option value="Technical">Technical</option>
                <option value="General">General</option>
              </select>
            ) : (
              <span style={{ 
                fontSize: '11px', 
                fontWeight: '600', 
                color: '#1a1c20' 
              }}>
                {currentUserDepartment}
              </span>
            )}
          </div>

          <div className="document-list" style={{ marginTop: 12 }}>
            {documents.map((doc) => (
              <div className="document-card" key={doc.id}>
                <div className="doc-info" style={{ minWidth: 0, flex: 1 }}>
                  <FileIcon className="doc-icon" />
                  <div className="doc-details" style={{ minWidth: 0, flex: 1 }}>
                    <span className="doc-name" title={doc.filename}>{doc.filename}</span>
                    <div className="doc-meta">
                      <span>{(doc.file_size / 1024).toFixed(1)} KB</span>
                      <span className={`status-badge ${doc.status}`}>
                        {doc.status}
                      </span>
                    </div>
                    {doc.status === 'indexed' && (
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 6 }}>
                        <span style={{
                          fontSize: '10px',
                          fontWeight: '600',
                          padding: '2px 6px',
                          borderRadius: '6px',
                          backgroundColor: '#F3F2EC',
                          color: '#5b6472',
                          border: '1px solid rgba(36, 50, 82, 0.04)',
                        }}>
                          {doc.classification || 'General'}
                        </span>
                        {doc.risk_status === 'Risk Detected' && (
                          <span 
                            title={doc.risk_details}
                            style={{
                              fontSize: '10px',
                              fontWeight: '600',
                              padding: '2px 6px',
                              borderRadius: '6px',
                              backgroundColor: 'rgba(224, 94, 63, 0.08)',
                              color: '#c8a44d',
                              border: '1px solid rgba(224, 94, 63, 0.15)',
                              cursor: 'help'
                            }}
                          >
<AlertTriangleIcon style={{ width: 10, height: 10, verticalAlign: 'middle', marginRight: 2 }} /> Risk Detected
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
                {currentUserRole !== 'Viewer' && (
                  <button 
                    className="doc-delete-btn" 
                    onClick={() => onDeleteDocument(doc.id)}
                    title="Delete Document"
                  >
                    <TrashIcon />
                  </button>
                )}
              </div>
            ))}
            {documents.length === 0 && (
              <div style={{ textAlign: 'center', padding: '12px 0', fontSize: '11px', color: 'var(--text-muted)' }}>
                No documents uploaded yet.
              </div>
            )}
          </div>
        </div>

        {/* Model Configuration Section */}
        <div>
          <div className="sidebar-section-title">
            <h3 className="section-title" style={{ display: 'flex', alignItems: 'center' }}>
              Settings
              {isGlobalConfigEnforced && (
                <span style={{ 
                  marginLeft: '8px', 
                  fontSize: '9px', 
                  backgroundColor: 'rgba(224, 94, 63, 0.1)', 
                  color: '#c8a44d', 
                  padding: '2px 6px', 
                  borderRadius: '4px', 
                  fontWeight: '700',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 3
                }}>
                  <ShieldIcon style={{ width: 9, height: 9 }} /> ADMIN MANAGED
                </span>
              )}
            </h3>
          </div>

          <div className="settings-group">
            {/* LLM Provider Selection */}
            <div className="settings-field">
              <label>Model Provider</label>
              <select 
                className="settings-select"
                value={modelConfig.provider}
                onChange={handleProviderChange}
                disabled={isGlobalConfigEnforced}
                style={{ opacity: isGlobalConfigEnforced ? 0.6 : 1, cursor: isGlobalConfigEnforced ? 'not-allowed' : 'pointer' }}
              >
                <option value="groq">Groq (Recommended)</option>
                <option value="gemini">Google Gemini</option>
                <option value="openai">OpenAI</option>
                <option value="ollama">Ollama (Offline Local)</option>
              </select>
            </div>

            {/* Dynamic API Key Input */}
            {modelConfig.provider !== 'ollama' && !isGlobalConfigEnforced && (
              <div className="settings-field">
                <label>
                  {modelConfig.provider.toUpperCase()} API Key
                </label>
                <PasswordInput
                  className="settings-input"
                  placeholder={`Enter your ${modelConfig.provider} API key`}
                  value={apiKeys[modelConfig.provider] || ''}
                  onChange={(e) => onApiKeyChange(modelConfig.provider, e.target.value)}
                  inputStyle={{ border: modelConfig.provider === 'groq' && !apiKeys.groq ? '1px solid rgba(192, 132, 252, 0.4)' : '1px solid var(--panel-border)' }}
                />
                {modelConfig.provider === 'groq' && !apiKeys.groq && (
                  <span style={{ fontSize: '10px', color: 'var(--accent)', marginTop: 2, fontWeight: 500 }}>
<AlertTriangleIcon style={{ width: 10, height: 10, verticalAlign: 'middle', marginRight: 2 }} /> Groq API key required to execute chat query.
                  </span>
                )}
              </div>
            )}

            {/* Model Name Select */}
            <div className="settings-field">
              <label>Model Choice</label>
              <select
                className="settings-select"
                value={modelConfig.model}
                onChange={(e) => handleConfigValueChange('model', e.target.value)}
                disabled={isGlobalConfigEnforced}
                style={{ opacity: isGlobalConfigEnforced ? 0.6 : 1, cursor: isGlobalConfigEnforced ? 'not-allowed' : 'pointer' }}
              >
                {providerModels[modelConfig.provider].map((model) => (
                  <option key={model.id} value={model.id}>
                    {model.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Temperature Slider */}
            <div className="settings-field">
              <label style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Temperature</span>
                <span style={{ opacity: 0.6 }}>{modelConfig.temperature.toFixed(1)}</span>
              </label>
              <div className="settings-slider-container">
                <input 
                  type="range"
                  className="settings-slider"
                  min="0"
                  max="1.0"
                  step="0.1"
                  value={modelConfig.temperature}
                  onChange={(e) => handleConfigValueChange('temperature', parseFloat(e.target.value))}
                  disabled={isGlobalConfigEnforced}
                  style={{ opacity: isGlobalConfigEnforced ? 0.6 : 1, cursor: isGlobalConfigEnforced ? 'not-allowed' : 'pointer' }}
                />
              </div>
            </div>

            {/* Retriever K slider */}
            <div className="settings-field">
              <label style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Retrieval Chunks (K)</span>
                <span style={{ opacity: 0.6 }}>{modelConfig.k}</span>
              </label>
              <div className="settings-slider-container">
                <input 
                  type="range"
                  className="settings-slider"
                  min="1"
                  max="8"
                  step="1"
                  value={modelConfig.k}
                  onChange={(e) => handleConfigValueChange('k', parseInt(e.target.value))}
                  disabled={isGlobalConfigEnforced}
                  style={{ opacity: isGlobalConfigEnforced ? 0.6 : 1, cursor: isGlobalConfigEnforced ? 'not-allowed' : 'pointer' }}
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      {currentUser && (
        <div style={{
          padding: '16px 20px',
          borderTop: '1px solid var(--panel-border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: '#FCFBF9'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0, flex: 1 }}>
            <div style={{
              width: 32,
              height: 32,
              borderRadius: 99,
              backgroundColor: 'var(--primary)',
              color: 'var(--bg-primary)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 'bold',
              fontSize: 13,
              flexShrink: 0
            }}>
              {currentUser.charAt(0).toUpperCase()}
            </div>
            <div style={{ minWidth: 0, display: 'flex', flexDirection: 'column' }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>
                {currentUser}
              </span>
              <span style={{
                fontSize: '9px',
                fontWeight: '700',
                padding: '1px 5px',
                borderRadius: '4px',
                backgroundColor: currentUserRole === 'Admin' ? '#1a1c20' : currentUserRole === 'Editor' ? 'rgba(224, 94, 63, 0.08)' : 'rgba(36, 50, 82, 0.05)',
                color: currentUserRole === 'Admin' ? '#FAF9F5' : currentUserRole === 'Editor' ? '#c8a44d' : '#8b92a0',
                alignSelf: 'flex-start',
                marginTop: '3px',
                textTransform: 'uppercase',
                letterSpacing: '0.3px',
                whiteSpace: 'nowrap'
              }}>
                {currentUserRole || 'Viewer'}
              </span>
            </div>
          </div>
          <button 
            onClick={onLogout}
            className="sidebar-logout-btn"
          >
            Sign Out
          </button>
        </div>
      )}
    </aside>
  );
}
