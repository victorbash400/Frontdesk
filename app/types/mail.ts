export type MailMessage = {
  id: string;
  direction: "inbound" | "outbound";
  sender: string;
  recipients: string;
  body: string;
  sentAt: string;
};

export type MailThread = {
  id: string;
  clientName: string;
  customerEmail: string;
  subject: string;
  preview: string;
  updatedAt: string;
  goalId: string | null;
  goalStatus: "active" | "paused" | "completed" | null;
  clientId: string | null;
  agentStatus: "queued" | "processing" | "completed" | "failed";
  agentAction: "record_only" | "resume_goal" | "create_goal" | "request_attention" | null;
  agentSummary: string | null;
  attentionRequired: boolean;
  agentFailure: string | null;
  activities: EmailAgentActivity[];
  messages: MailMessage[];
};

export type EmailAgentActivity = {
  id: string;
  kind: string;
  summary: string;
  createdAt: string;
};
