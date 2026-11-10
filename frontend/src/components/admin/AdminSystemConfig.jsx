import styles from './AdminStyles';
import { SettingsIcon } from '../Icons';
import PasswordInput from '../PasswordInput';
import { PROVIDER_MODELS } from '../../utils/constants';

export default function AdminSystemConfig({ 
  llmConfig, 
  setLlmConfig, 
  handleSaveLlmConfig, 
  savingLlm 
}) {
  const providerModels = PROVIDER_MODELS;

  if (!llmConfig) return <div style={styles.loading}>Loading system configuration...</div>;

  return (
    <div className="admin-scrollable">
      <div className="glass-panel" style={styles.card}>
        <h3 style={styles.cardTitle}><SettingsIcon style={{ width: 16, height: 16, verticalAlign: 'middle', marginRight: 6 }} /> Global LLM Configuration</h3>
        <p style={{ fontSize: '13px', color: '#9ca3af', marginBottom: '20px' }}>
          Manage model providers, API keys, and model choices globally.
        </p>
        
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: '32px', backgroundColor: 'rgba(0, 0, 0, 0.03)', padding: '16px', borderRadius: '12px', border: '1px solid rgba(0, 0, 0, 0.12)' }}>
          <input 
            type="checkbox" 
            id="enforceGlobal"
            checked={llmConfig.enforce_globally}
            onChange={(e) => setLlmConfig({...llmConfig, enforce_globally: e.target.checked})}
            style={{ marginRight: '12px', width: '20px', height: '20px', accentColor: '#111111', cursor: 'pointer' }}
          />
          <label htmlFor="enforceGlobal" style={{ fontSize: '14px', fontWeight: '600', color: '#111111', cursor: 'pointer', margin: 0 }}>
            Enforce settings globally (Overrides user preferences)
          </label>
        </div>
        
        <div style={styles.twoColumnGrid}>
          {/* Model Settings */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <h4 style={{ fontSize: '14px', fontWeight: '600', color: '#111111', margin: '0 0 8px 0' }}>Model Preferences</h4>
            
            <div>
              <label style={styles.label}>Provider</label>
              <select 
                value={llmConfig.config.provider}
                onChange={e => {
                  const nextProvider = e.target.value;
                  const defaultModel = providerModels[nextProvider]?.[0]?.id || '';
                  setLlmConfig({
                    ...llmConfig, 
                    config: {
                      ...llmConfig.config, 
                      provider: nextProvider,
                      model: defaultModel
                    }
                  });
                }}
                style={styles.input}
              >
                <option value="groq">Groq (Recommended)</option>
                <option value="gemini">Google Gemini</option>
                <option value="openai">OpenAI</option>
              </select>
            </div>
            
            <div>
              <label style={styles.label}>Model Choice</label>
              <select 
                value={llmConfig.config.model}
                onChange={e => setLlmConfig({...llmConfig, config: {...llmConfig.config, model: e.target.value}})}
                style={styles.input}
              >
                {providerModels[llmConfig.config.provider]?.map(m => (
                  <option key={m.id} value={m.id}>{m.name}</option>
                ))}
              </select>
            </div>
          </div>

          {/* API Keys */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <h4 style={{ fontSize: '14px', fontWeight: '600', color: '#111111', margin: '0 0 8px 0' }}>API Keys</h4>
            
            {llmConfig.config.provider === 'groq' && (
              <div>
                <label style={styles.label}>Groq API Key</label>
                <PasswordInput
                  value={llmConfig.api_keys.groq || ''}
                  onChange={e => setLlmConfig({...llmConfig, api_keys: {...llmConfig.api_keys, groq: e.target.value}})}
                  inputStyle={styles.input}
                  placeholder="gsk_..."
                />
              </div>
            )}

            {llmConfig.config.provider === 'gemini' && (
              <div>
                <label style={styles.label}>Gemini API Key</label>
                <PasswordInput
                  value={llmConfig.api_keys.gemini || ''}
                  onChange={e => setLlmConfig({...llmConfig, api_keys: {...llmConfig.api_keys, gemini: e.target.value}})}
                  inputStyle={styles.input}
                  placeholder="AIza..."
                />
              </div>
            )}

            {llmConfig.config.provider === 'openai' && (
              <div>
                <label style={styles.label}>OpenAI API Key</label>
                <PasswordInput
                  value={llmConfig.api_keys.openai || ''}
                  onChange={e => setLlmConfig({...llmConfig, api_keys: {...llmConfig.api_keys, openai: e.target.value}})}
                  inputStyle={styles.input}
                  placeholder="sk-..."
                />
              </div>
            )}
          </div>
        </div>

        <div style={{ marginTop: '32px', display: 'flex', justifyContent: 'flex-end' }}>
          <button 
            className="action-btn primary" 
            onClick={handleSaveLlmConfig} 
            disabled={savingLlm}
            style={{ padding: '12px 24px', fontSize: '14px' }}
          >
            {savingLlm ? 'Saving...' : 'Save Configuration'}
          </button>
        </div>
      </div>
    </div>
  );
}
