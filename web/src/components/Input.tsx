import type { InputHTMLAttributes } from "react";
import styles from "./Input.module.css";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  errorMessage?: string;
}

export function Input({
  label,
  errorMessage,
  id,
  className,
  ...rest
}: InputProps) {
  const inputId = id ?? `campaia-input-${label.toLowerCase().replace(/\s+/g, "-")}`;
  const errorId = errorMessage ? `${inputId}-error` : undefined;
  const classes = [styles.input, errorMessage ? styles.inputError : null, className]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={styles.field}>
      <label className={styles.label} htmlFor={inputId}>
        {label}
      </label>
      <input
        id={inputId}
        className={classes}
        aria-invalid={errorMessage ? true : undefined}
        aria-describedby={errorId}
        {...rest}
      />
      {errorMessage ? (
        <p id={errorId} className={styles.errorMessage} role="alert">
          {errorMessage}
        </p>
      ) : null}
    </div>
  );
}
