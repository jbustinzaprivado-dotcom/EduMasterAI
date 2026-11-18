import { describe, expect, it } from "vitest";
import { parseSSE } from "./live";

describe("parseSSE", () => {
  it("separa eventos, ignora latidos y conserva el resto incompleto", () => {
    const raw = 'event: ready\ndata: {"user":"u"}\n\n: latido\n\nid: 7\nevent: notification\ndata: {"id":"7"}\n\nid: 8\nevent: notif';
    const { events, rest } = parseSSE(raw);
    expect(events).toEqual([
      { id: undefined, event: "ready", data: '{"user":"u"}' },
      { id: "7", event: "notification", data: '{"id":"7"}' },
    ]);
    expect(rest).toBe("id: 8\nevent: notif");
  });

  it("respeta los dos puntos dentro de los datos", () => {
    const { events } = parseSSE('data: {"t":"10:30"}\n\n');
    expect(events[0]?.data).toBe('{"t":"10:30"}');
  });
});
