export interface AppConfig {
  pageTitle: string;
  pageDescription: string;
  companyName: string;
  startButtonText: string;
  agentName?: string;
  sandboxId?: string;
}

export const APP_CONFIG_DEFAULTS: AppConfig = {
  companyName: 'Field Companion',
  pageTitle: 'Field Companion',
  pageDescription: 'Voice-first agentic assistant for UK pharma sales reps',
  startButtonText: 'Start call',
  agentName: process.env.NEXT_PUBLIC_AGENT_NAME ?? 'my-agent',
};
