import { describe, expect, it } from "vitest";
import {
  CAP_SECONDS,
  formatDuration,
  initialRecorderState,
  recorderReducer,
} from "./useRecorder";

describe("formatDuration", () => {
  it("pads seconds", () => {
    expect(formatDuration(0)).toBe("0:00");
    expect(formatDuration(9)).toBe("0:09");
    expect(formatDuration(65)).toBe("1:05");
    expect(formatDuration(180)).toBe("3:00");
  });

  it("never goes negative", () => {
    expect(formatDuration(-5)).toBe("0:00");
  });
});

describe("recorderReducer", () => {
  it("starts from idle", () => {
    expect(initialRecorderState.status).toBe("idle");
    const s = recorderReducer(initialRecorderState, { type: "start" });
    expect(s.status).toBe("recording");
    expect(s.elapsedSeconds).toBe(0);
  });

  it("accumulates elapsed time while recording", () => {
    let s = recorderReducer(initialRecorderState, { type: "start" });
    s = recorderReducer(s, { type: "tick", seconds: 12.4 });
    expect(s.elapsedSeconds).toBeCloseTo(12.4);
  });

  it("ignores ticks when not recording", () => {
    const s = recorderReducer(initialRecorderState, { type: "tick", seconds: 5 });
    expect(s.elapsedSeconds).toBe(0);
  });

  it("moves to recorded and keeps the blob", () => {
    const blob = new Blob(["x"], { type: "audio/webm" });
    let s = recorderReducer(initialRecorderState, { type: "start" });
    s = recorderReducer(s, { type: "stop", blob, objectUrl: "blob:1" });
    expect(s.status).toBe("recorded");
    expect(s.blob).toBe(blob);
    expect(s.objectUrl).toBe("blob:1");
  });

  it("reset clears the take and returns to idle", () => {
    const blob = new Blob(["x"]);
    let s = recorderReducer(initialRecorderState, { type: "start" });
    s = recorderReducer(s, { type: "stop", blob, objectUrl: "blob:1" });
    s = recorderReducer(s, { type: "reset" });
    expect(s).toEqual(initialRecorderState);
  });

  it("submit keeps the take so a failure can recover it", () => {
    const blob = new Blob(["x"]);
    let s = recorderReducer(initialRecorderState, { type: "start" });
    s = recorderReducer(s, { type: "stop", blob, objectUrl: "blob:1" });
    s = recorderReducer(s, { type: "submit" });
    expect(s.status).toBe("submitting");
    expect(s.blob).toBe(blob);
    s = recorderReducer(s, { type: "submitFailed" });
    expect(s.status).toBe("recorded");
    expect(s.blob).toBe(blob);
  });

  it("caps at three minutes", () => {
    expect(CAP_SECONDS).toBe(180);
  });
});
