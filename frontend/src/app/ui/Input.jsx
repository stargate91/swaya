import { useId, useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import { useTranslation } from '../providers/LanguageContext';
import './Input.css';

export default function Input({ label, hint, error, type, className = '', inputRef, rightElement, ...props }) {
  const [showPassword, setShowPassword] = useState(false);
  const hintId = useId();
  const errorId = useId();

  const isPassword = type === 'password';
  const inputType = isPassword ? (showPassword ? 'text' : 'password') : type;
  const hasRightElement = isPassword || rightElement;

  const { t } = useTranslation();

  return (
    <label className={`ui-field ui-input-field ${className}`.trim()}>
      {label ? <span className="ui-field__label">{label}</span> : null}
      {hint ? <span className="ui-field__hint">{hint}</span> : null}
      <div className="ui-input__wrapper">
        <input
          ref={inputRef}
          className={`ui-input${hasRightElement ? ' ui-input--has-right-element' : ''}${error ? ' ui-input--error' : ''}`}
          type={inputType}
          aria-invalid={error ? 'true' : undefined}
          aria-describedby={[
            hint ? hintId : null,
            error ? errorId : null,
          ].filter(Boolean).join(' ') || undefined}
          {...props}
        />
        {isPassword && (
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            className="ui-input__toggle"
            tabIndex={-1}
            aria-label={showPassword ? t('input.hidePassword') : t('input.showPassword')}
          >
            {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
          </button>
        )}
        {!isPassword && rightElement && (
          <div className="ui-input__right-element">
            {rightElement}
          </div>
        )}
      </div>
      {hint ? <span id={hintId} className="ui-field__sr-only">{hint}</span> : null}
      {error ? <span id={errorId} className="ui-field__error">{error}</span> : null}
    </label>
  );
}
