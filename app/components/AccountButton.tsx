"use client";

import { LogOut, UserRound } from "lucide-react";
import { signOut } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import styles from "./AccountButton.module.css";


type AccountButtonProps = {
  email: string;
  name: string;
};

export function AccountButton({ email, name }: AccountButtonProps) {
  const router = useRouter();
  const [error, setError] = useState<string>();
  const [signingOut, setSigningOut] = useState(false);

  async function handleSignOut() {
    setError(undefined);
    setSigningOut(true);
    try {
      await signOut({ redirect: false });
      router.replace("/sign-in");
      router.refresh();
    } catch {
      setError("Could not sign out");
      setSigningOut(false);
    }
  }

  return (
    <details className={styles.account}>
      <summary aria-label={`Open account menu for ${name}`} title={name}><UserRound aria-hidden="true" /></summary>
      <section>
        <p><span>Signed in as</span><strong>{name}</strong><small>{email}</small></p>
        {error ? <p role="alert">{error}</p> : null}
        <button disabled={signingOut} onClick={handleSignOut} type="button"><LogOut aria-hidden="true" />{signingOut ? "Signing out" : "Sign out"}</button>
      </section>
    </details>
  );
}
