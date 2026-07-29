import { describe, expect, it } from "vitest";
import {
  ACTIVE_CHAT_SESSION_KEY,
  CHAT_SESSIONS_KEY,
  LEGACY_CHAT_HISTORY_KEY,
  createChatSession,
  deriveChatTitle,
  loadChatSessions,
  saveChatSessions,
  summarizeChatSessions,
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
});
