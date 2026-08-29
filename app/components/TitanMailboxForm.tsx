"use client";

import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import styles from "./TitanMailboxForm.module.css";

export function TitanMailboxForm({ onConnect }: { onConnect: (email: string, password: string) => Promise<void> }) {
  const [email, setEmail] = useState("support@aqualabs.tech");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string>();
  const [working, setWorking] = useState(false);
  return <form className={styles.form} onSubmit={(event) => { event.preventDefault(); setWorking(true); setError(undefined); void onConnect(email, password).catch((reason) => setError(reason instanceof Error ? reason.message : "Titan could not be connected.")).finally(() => setWorking(false)); }}>
    <label>Email address<input autoComplete="username" onChange={(event) => setEmail(event.target.value)} type="email" value={email} /></label>
    <label>Mailbox password<span className={styles.password}><input autoComplete="current-password" onChange={(event) => setPassword(event.target.value)} type={showPassword ? "text" : "password"} value={password} /><button aria-label={showPassword ? "Hide password" : "Show password"} onClick={() => setShowPassword((current) => !current)} title={showPassword ? "Hide password" : "Show password"} type="button">{showPassword ? <EyeOff aria-hidden="true" /> : <Eye aria-hidden="true" />}</button></span></label>
    <p>Front Desk uses Titan’s encrypted IMAP and SMTP connections. The first connection starts from new mail only.</p>
    {error ? <p className={styles.error} role="alert">{error}</p> : null}
    <button disabled={working || !email || !password} type="submit">{working ? "Connecting" : "Connect Titan"}</button>
  </form>;
}
