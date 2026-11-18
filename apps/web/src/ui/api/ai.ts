import { apiRequest } from "./client";
import type { AIChatPayload, AIChatResponse, AIChatSession, AIChatSessionDetail } from "../types";

export function sendAIChatMessage(token: string, payload: AIChatPayload): Promise<AIChatResponse> {
  return apiRequest<AIChatResponse>(
    "/ai/chat",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    token,
  );
}

export function listAISessions(token: string, limit = 50): Promise<AIChatSession[]> {
  return apiRequest<AIChatSession[]>(`/ai/sessions?limit=${limit}`, {}, token);
}

export function getAISession(token: string, sessionId: number): Promise<AIChatSessionDetail> {
  return apiRequest<AIChatSessionDetail>(`/ai/sessions/${sessionId}`, {}, token);
}
