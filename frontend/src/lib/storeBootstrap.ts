import { getRagMode, listSessions, listSkills, loadFile, type SkillMeta, type SessionSummary } from "@/lib/api";

export type InitialAppState = {
  sessions: SessionSummary[];
  ragMode: boolean;
  skills: SkillMeta[];
  inspectorFile: {
    path: string;
    content: string;
  };
};

export async function loadInitialAppState(): Promise<InitialAppState> {
  const [sessions, rag, skills, inspectorFile] = await Promise.all([
    listSessions(),
    getRagMode(),
    listSkills(),
    loadFile("memory/MEMORY.md")
  ]);

  return {
    sessions,
    ragMode: rag.enabled,
    skills,
    inspectorFile
  };
}
