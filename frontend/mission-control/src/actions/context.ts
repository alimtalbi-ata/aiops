export type Mode = "DEMO" | "OPERATIONAL";
export type View = "incident" | "ci" | "run" | "scenario" | "analysis" | "critic" | "policy" | "hitl" | "execution" | "evidence";
export type Selection = { view: View; id: string; runId?: string };
export type Command = "inspect" | "rag" | "start" | "advance" | "pause" | "reset" | "replay" | "execute" | "approve" | "reject";
export type Reply = { state: "SIMULATED" | "OBSERVED" | "BLOCKED" | "UNKNOWN"; detail: unknown; http?: number };
export interface ActionProvider {
  readonly mode: Mode;
  invoke(selection: Selection, command: Command, signal: AbortSignal): Promise<Reply>;
}
export const commands: Record<View, readonly Command[]> = {
  incident: ["inspect"], ci: ["inspect","rag"], run: ["inspect"],
  scenario: ["inspect","start","advance","pause","reset","replay"],
  analysis: ["inspect"], critic: ["inspect"], policy: ["inspect"],
  hitl: ["inspect","approve","reject"], execution: ["inspect","execute"], evidence: ["inspect"],
};
export const labels: Record<Command,string> = {
  inspect:"Inspecter", rag:"Références RAG", start:"Démarrer", advance:"Avancer",
  pause:"Pause", reset:"Réinitialiser", replay:"Rejouer", execute:"Exécuter", approve:"Approuver", reject:"Refuser"
};
