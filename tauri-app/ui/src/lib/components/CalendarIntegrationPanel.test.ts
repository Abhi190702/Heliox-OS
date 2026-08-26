import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CalendarIntegrationPanel from "./CalendarIntegrationPanel.svelte";

const daemonMocks = vi.hoisted(() => ({ call: vi.fn() }));
const settingsMocks = vi.hoisted(() => {
  let value: any;
  const subscribers = new Set<(next: any) => void>();
  return {
    updateSection: vi.fn(),
    store: {
      subscribe(run: (next: any) => void) {
        subscribers.add(run);
        run(value);
        return () => subscribers.delete(run);
      },
    },
    set(next: any) {
      value = next;
      subscribers.forEach((run) => run(value));
    },
  };
});

vi.mock("../api/daemon", () => ({ call: daemonMocks.call }));
vi.mock("../stores/settings", () => ({
  settings: {
    subscribe: settingsMocks.store.subscribe,
    updateSection: settingsMocks.updateSection,
  },
}));

describe("CalendarIntegrationPanel", () => {
  beforeEach(() => {
    daemonMocks.call.mockReset();
    daemonMocks.call.mockResolvedValue({ providers: [] });
    settingsMocks.updateSection.mockReset();
    settingsMocks.updateSection.mockResolvedValue(true);
    settingsMocks.set({
      calendar: {
        enabled: false,
        caldav_url: "",
        caldav_username: "",
        caldav_password_provider: "caldav",
        ics_files: [],
      },
    });
  });

  it("saves normalized local calendar paths while CalDAV is disabled", async () => {
    render(CalendarIntegrationPanel);

    await fireEvent.input(screen.getByLabelText(/Local \.ics files/), {
      target: { value: " C:\\Calendars\\work.ics \n\nD:\\shared\\team.ics " },
    });
    await fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(settingsMocks.updateSection).toHaveBeenCalledWith(
        "calendar",
        expect.objectContaining({
          enabled: false,
          ics_files: ["C:\\Calendars\\work.ics", "D:\\shared\\team.ics"],
        }),
        { requireDaemon: true },
      ),
    );
    expect(screen.getByText(/Saved 2 local calendar sources/)).toBeTruthy();
  });

  it("preserves configured local sources when saving CalDAV", async () => {
    settingsMocks.set({
      calendar: {
        enabled: false,
        caldav_url: "",
        caldav_username: "",
        caldav_password_provider: "caldav",
        ics_files: ["C:\\Calendars\\personal.ics"],
      },
    });
    render(CalendarIntegrationPanel);

    expect((screen.getByLabelText(/Local \.ics files/) as HTMLTextAreaElement).value).toBe(
      "C:\\Calendars\\personal.ics",
    );
  });
});
