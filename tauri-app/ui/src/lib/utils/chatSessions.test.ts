import { describe, expect, it } from "vitest";
import {
  ACTIVE_CHAT_SESSION_KEY,
  CHAT_SESSIONS_KEY,
  LEGACY_CHAT_HISTORY_KEY,
  createChatSession,
  deriveChatTitle,
  loadChatSessions,
  loadLocalCommandHistory,
  saveChatSessions,
  summarizeChatSessions,
  redactSensitiveChatText,
} from "./chatSessions";

function storage(): Storage {
  const values = new Map<string, string>();
  return {
    get length() {
      return values.size;
    },
    clear: () => values.clear(),
    getItem: (key) => values.get(key) ?? null,
    key: (index) => [...values.keys()][index] ?? null,
    removeItem: (key) => values.delete(key),
    setItem: (key, value) => values.set(key, value),
  };
}

describe("chat session persistence", () => {
  it("migrates the legacy single-chat history", () => {
    const target = storage();
    target.setItem(
      LEGACY_CHAT_HISTORY_KEY,
      JSON.stringify([{ type: "user", text: "Inspect my system", timestamp: 10 }]),
    );

    const loaded = loadChatSessions(target);

    expect(loaded.sessions).toHaveLength(1);
    expect(loaded.sessions[0].title).toBe("Inspect my system");
    expect(loaded.sessions[0].messages).toHaveLength(1);
  });

  it("persists and restores the active session", () => {
    const target = storage();
    const first = createChatSession(10);
    const second = createChatSession(20);

    saveChatSessions(target, [first, second], second.id);
    const loaded = loadChatSessions(target);

    expect(target.getItem(CHAT_SESSIONS_KEY)).toBeTruthy();
    expect(target.getItem(ACTIVE_CHAT_SESSION_KEY)).toBe(second.id);
    expect(loaded.activeSessionId).toBe(second.id);
  });

  it("persists the resume capability with its owning chat only", () => {
    const target = storage();
    const interrupted = createChatSession(10);
    interrupted.durableTask = {
      taskId: "task-1",
      resumeToken: "local-resume-capability",
    };
    const idle = createChatSession(20);

    saveChatSessions(target, [interrupted, idle], interrupted.id);
    const loaded = loadChatSessions(target);

    expect(loaded.sessions[0].durableTask).toEqual(interrupted.durableTask);
    expect(loaded.sessions[1].durableTask).toBeUndefined();
  });

  it("drops malformed resume capabilities instead of sending partial authority", () => {
    const target = storage();
    target.setItem(
      CHAT_SESSIONS_KEY,
      JSON.stringify([
        {
          ...createChatSession(10),
          durableTask: { taskId: "task-1" },
        },
      ]),
    );

    expect(loadChatSessions(target).sessions[0].durableTask).toBeUndefined();
  });

  it("derives concise titles and sorts summaries by recent activity", () => {
    const older = createChatSession(10);
    older.messages = [{ type: "user", text: "A".repeat(70), timestamp: 10 }];
    older.title = deriveChatTitle(older.messages);
    const newer = createChatSession(20);

    const summaries = summarizeChatSessions([older, newer]);

    expect(summaries[0].id).toBe(newer.id);
    expect(older.title).toHaveLength(56);
    expect(older.title.endsWith("...")).toBe(true);
  });

  it("redacts provider credentials from persisted historical messages", () => {
    const target = storage();
    const leaked = "https://provider.test/generate?key=AIzaSyExampleSecretValue123456789";
    target.setItem(
      CHAT_SESSIONS_KEY,
      JSON.stringify([
        {
          ...createChatSession(10),
          messages: [
            {
              type: "error",
              text: `Planning failed at ${leaked}`,
              timestamp: 10,
              actionResults: [
                {
                  action_type: "system_info",
                  target: "system",
                  success: false,
                  output: "",
                  error: `Bearer private-token at ${leaked}`,
                },
              ],
            },
          ],
        },
      ]),
    );

    const loaded = loadChatSessions(target);
    const serialized = target.getItem(CHAT_SESSIONS_KEY) ?? "";

    expect(loaded.sessions[0].messages[0].text).toContain("?key=[redacted]");
    expect(loaded.sessions[0].messages[0].actionResults?.[0].error).toContain("Bearer [redacted]");
    expect(serialized).not.toContain("AIzaSyExampleSecretValue");
    expect(serialized).not.toContain("private-token");
  });

  it("redacts standalone Google API key shapes", () => {
    expect(redactSensitiveChatText("key: AIzaSyExampleSecretValue123456789")).toBe("key: [redacted]");
  });

  it("does not invent successful execution for a local user message", () => {
    const target = storage();
    const session = createChatSession(10);
    session.messages = [{ type: "user", text: "Hello Heliox", timestamp: 10 }];
    saveChatSessions(target, [session], session.id);

    expect(loadLocalCommandHistory(target)[0]).toMatchObject({
      text: "Hello Heliox",
      status: "unverified",
      explanation: "Local chat record; daemon execution outcome is unavailable.",
    });
  });

  it("derives local execution status only from recorded action evidence", () => {
    const target = storage();
    const session = createChatSession(10);
    session.messages = [
      { type: "user", text: "Open the report", timestamp: 10 },
      {
        type: "result",
        text: "The report opened.",
        timestamp: 11,
        actionResults: [
          { action_type: "open_file", target: "report.pdf", success: true, output: "opened", error: null },
        ],
        verification: { passed: true, details: ["window observed"] },
      },
      { type: "user", text: "Delete the archive", timestamp: 12 },
      { type: "error", text: "The action was denied.", timestamp: 13 },
    ];
    saveChatSessions(target, [session], session.id);

    const history = loadLocalCommandHistory(target);
    expect(history.map((entry) => [entry.text, entry.status])).toEqual([
      ["Delete the archive", "error"],
      ["Open the report", "success"],
    ]);
  });
});
