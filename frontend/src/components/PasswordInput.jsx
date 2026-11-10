import { useState } from 'react';
import { EyeIcon, EyeOffIcon } from './Icons';
import './PasswordInput.css';

export default function PasswordInput({
  id,
  name,
  value,
  onChange,
  placeholder,
  disabled = false,
  required = false,
  autoComplete,
  className = '',
  inputStyle,
  wrapperStyle,
  onKeyDown,
  ariaLabel,
}) {
  const [visible, setVisible] = useState(false);

  return (
    <div className="password-input-wrap" style={wrapperStyle}>
      <input
        id={id}
        name={name}
        type={visible ? 'text' : 'password'}
        className={className}
        style={inputStyle}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        disabled={disabled}
        required={required}
        autoComplete={autoComplete}
        onKeyDown={onKeyDown}
        aria-label={ariaLabel}
      />
      <button
        type="button"
        className="password-toggle-btn"
        onClick={() => setVisible((current) => !current)}
        disabled={disabled}
        aria-label={visible ? 'Hide password' : 'Show password'}
        aria-pressed={visible}
        title={visible ? 'Hide password' : 'Show password'}
      >
        {visible ? <EyeOffIcon width={16} height={16} /> : <EyeIcon width={16} height={16} />}
      </button>
    </div>
  );
}
