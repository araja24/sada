/* Recording step (PRD §4 steps 5-6): mic capture with a live timer and a
   visible 3:00 cap, playback + re-record, then submit.

   The state machine is a pure reducer so it can be tested without a DOM or a
   MediaRecorder. useRecorder wires it to the real browser APIs and owns
   teardown of the stream, interval and object URL. */
import { useCallback, useEffect, useReducer, useRef } from "react";

export const CAP_SECONDS = 180; // PRD: hard 3:00 cap

export type RecorderStatus = "idle" | "recording" | "recorded" | "submitting";

export interface RecorderState {
  status: RecorderStatus;
  elapsedSeconds: number;
  blob: Blob | null;
  objectUrl: string | null;
}

export type RecorderAction =
  | { type: "start" }
  | { type: "tick"; seconds: number }
  | { type: "stop"; blob: Blob; objectUrl: string }
  | { type: "reset" }
  | { type: "submit" }
  | { type: "submitFailed" };

export const initialRecorderState: RecorderState = {
  status: "idle",
  elapsedSeconds: 0,
  blob: null,
  objectUrl: null,
};

export function recorderReducer(state: RecorderState, action: RecorderAction): RecorderState {
  switch (action.type) {
    case "start":
      return { ...initialRecorderState, status: "recording" };
    case "tick":
      return state.status === "recording"
        ? { ...state, elapsedSeconds: action.seconds }
        : state;
    case "stop":
      return {
        ...state,
        status: "recorded",
        blob: action.blob,
        objectUrl: action.objectUrl,
      };
    case "reset":
      return initialRecorderState;
    case "submit":
      return { ...state, status: "submitting" };
    case "submitFailed":
      return { ...state, status: "recorded" };
    default:
      return state;
  }
}

export function formatDuration(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export function useRecorder(onError: (message: string) => void) {
  const [state, dispatch] = useReducer(recorderReducer, initialRecorderState);
  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const intervalRef = useRef<number | null>(null);
  const startedAtRef = useRef(0);
  const objectUrlRef = useRef<string | null>(null);

  const releaseAll = useCallback(() => {
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = null;
    }
  }, []);

  // Release the mic, timer and object URL even if the user navigates away
  // mid-recording.
  useEffect(() => releaseAll, [releaseAll]);

  const stop = useCallback(() => {
    if (recorderRef.current && recorderRef.current.state !== "inactive") {
      recorderRef.current.stop();
    }
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const start = useCallback(async () => {
    if (!navigator.mediaDevices || !window.MediaRecorder) {
      onError("This browser can't record audio. Try a recent Chrome, Firefox, or Safari.");
      return;
    }
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      onError("We need microphone access to record. Enable it in your browser settings and try again.");
      return;
    }
    streamRef.current = stream;
    chunksRef.current = [];
    const recorder = new MediaRecorder(stream);
    recorderRef.current = recorder;

    recorder.addEventListener("dataavailable", (e) => {
      if (e.data && e.data.size) chunksRef.current.push(e.data);
    });
    recorder.addEventListener("stop", () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
      }
      const type = recorder.mimeType || "audio/webm";
      const blob = new Blob(chunksRef.current, { type });
      if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
      const url = URL.createObjectURL(blob);
      objectUrlRef.current = url;
      dispatch({ type: "stop", blob, objectUrl: url });
    });

    recorder.start();
    startedAtRef.current = Date.now();
    dispatch({ type: "start" });
    intervalRef.current = window.setInterval(() => {
      const secs = (Date.now() - startedAtRef.current) / 1000;
      dispatch({ type: "tick", seconds: secs });
      if (secs >= CAP_SECONDS) stop();
    }, 200);
  }, [onError, stop]);

  const reset = useCallback(() => {
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = null;
    }
    chunksRef.current = [];
    dispatch({ type: "reset" });
  }, []);

  return {
    state,
    start,
    stop,
    reset,
    markSubmitting: () => dispatch({ type: "submit" }),
    markSubmitFailed: () => dispatch({ type: "submitFailed" }),
  };
}
