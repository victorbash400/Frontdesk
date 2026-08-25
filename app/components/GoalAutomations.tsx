"use client";

import { Clock3, Plus } from "lucide-react";
import { useState } from "react";

import type { GoalAutomation } from "../types/goal";
import styles from "./GoalAutomations.module.css";

type GoalAutomationsProps = {
  automations: GoalAutomation[];
  onCreate: (instruction: string, intervalSeconds: number, timezone: string) => Promise<void>;
};

export function GoalAutomations({ automations, onCreate }: GoalAutomationsProps) {
  const [adding, setAdding] = useState(false);
  const [instruction, setInstruction] = useState("Tell me the current time using the client message tool.");
  const [minutes, setMinutes] = useState(5);
  const [error, setError] = useState<string>();

  async function create() {
    try {
      await onCreate(instruction, minutes * 60, Intl.DateTimeFormat().resolvedOptions().timeZone || "Africa/Nairobi");
      setAdding(false);
      setError(undefined);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not create automation.");
    }
  }

  return <section className={styles.automations}><header><span><strong>Automations</strong><small>Scheduled supervisor wake-ups</small></span><button onClick={() => setAdding((value) => !value)} type="button"><Plus aria-hidden="true" />Add</button></header>{adding ? <section className={styles.form}><input aria-label="Automation instruction" onChange={(event) => setInstruction(event.target.value)} value={instruction} /><label>Every<input aria-label="Automation interval in minutes" min={5} onChange={(event) => setMinutes(event.target.valueAsNumber)} type="number" value={minutes} />minutes</label><button disabled={!instruction.trim() || minutes < 5} onClick={() => void create()} type="button">Schedule</button>{error ? <small role="alert">{error}</small> : null}</section> : null}{automations.length ? <ul>{automations.map((automation) => <li key={automation.id}><Clock3 aria-hidden="true" /><span><strong>{automation.instruction}</strong><small>Every {automation.intervalSeconds / 60} minutes · next {formatTime(automation.nextRunAt)}</small></span></li>)}</ul> : <p>No scheduled wake-ups</p>}</section>;
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}
