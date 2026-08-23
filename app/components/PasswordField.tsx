"use client";

import { Eye, EyeOff } from "lucide-react";
import { useState } from "react";

import styles from "../sign-in/sign-in.module.css";


type PasswordFieldProps = {
  autoComplete: "current-password" | "new-password";
  value: string;
  onChange: (value: string) => void;
};

export function PasswordField({ autoComplete, value, onChange }: PasswordFieldProps) {
  const [visible, setVisible] = useState(false);
  return (
    <label>Password<span className={styles.password}><input autoComplete={autoComplete} name="password" onChange={(event) => onChange(event.target.value)} required type={visible ? "text" : "password"} value={value} /><button aria-label={visible ? "Hide password" : "Show password"} onClick={() => setVisible((current) => !current)} type="button">{visible ? <EyeOff aria-hidden="true" /> : <Eye aria-hidden="true" />}</button></span></label>
  );
}
