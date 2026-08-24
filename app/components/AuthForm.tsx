"use client";

import { signIn } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { demoAccount } from "../lib/demoAccount";
import styles from "../sign-in/sign-in.module.css";
import { PasswordField } from "./PasswordField";


type Mode = "signin" | "create";

export function AuthForm() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("signin");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string>();
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const submittedName = String(form.get("name") || name);
    const submittedEmail = String(form.get("email") || email);
    const submittedPassword = String(form.get("password") || password);
    setError(undefined);
    setSubmitting(true);
    try {
      if (mode === "create") {
        const response = await fetch("/api/accounts", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: submittedEmail, password: submittedPassword, name: submittedName }),
        });
        const body = await response.json() as { error?: string };
        if (!response.ok) throw new Error(body.error || "Could not create account");
      }
      const result = await signIn("credentials", { email: submittedEmail, password: submittedPassword, redirect: false });
      if (result?.error === "CredentialsSignin") throw new Error("Email or password is incorrect");
      if (result?.error) throw new Error("Front Desk account service is unavailable");
      router.replace("/");
      router.refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Authentication failed");
    } finally {
      setSubmitting(false);
    }
  }

  function chooseMode(nextMode: Mode) {
    setMode(nextMode);
    setError(undefined);
  }

  function useDemoAccount() {
    setMode("signin");
    setEmail(demoAccount.email);
    setPassword(demoAccount.password);
    setName("");
    setError(undefined);
  }

  return (
    <main className={styles.page}>
      <strong className={styles.brand}>Front Desk</strong>
      <section className={styles.shell}>
        <section className={styles.card}>
          <h1>{mode === "signin" ? "Sign in" : "Create account"}</h1>
          <nav aria-label="Account access" className={styles.modes}>
            <button aria-pressed={mode === "signin"} onClick={() => chooseMode("signin")} type="button">Sign in</button>
            <button aria-pressed={mode === "create"} onClick={() => chooseMode("create")} type="button">Create account</button>
          </nav>
          <form id="front-desk-auth-form" onSubmit={submit}>
            <section className={styles.fields}>
              {mode === "create" ? <label>Name<input autoComplete="name" name="name" onChange={(event) => setName(event.target.value)} required value={name} /></label> : null}
              <label>Email<input autoComplete="username" name="email" onChange={(event) => setEmail(event.target.value)} required type="email" value={email} /></label>
              <PasswordField autoComplete={mode === "signin" ? "current-password" : "new-password"} onChange={setPassword} value={password} />
            </section>
            <section className={styles.secondary}>
              {error ? <p role="alert">{error}</p> : mode === "signin" ? <button onClick={useDemoAccount} type="button">Use demo account</button> : null}
            </section>
          </form>
        </section>
        <button className={styles.submit} disabled={submitting} form="front-desk-auth-form" type="submit">{submitting ? "Working" : mode === "signin" ? "Sign in" : "Create account"}</button>
      </section>
    </main>
  );
}
