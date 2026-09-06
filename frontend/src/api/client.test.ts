import { describe, expect, it } from "vitest";
import { messageFromBody } from "./client";

describe("messageFromBody", () => {
  it("prefers a string detail from the API", () => {
    expect(messageFromBody({ detail: "That email is already registered." }, 400))
      .toBe("That email is already registered.");
  });

  it("unwraps FastAPI validation arrays", () => {
    const body = { detail: [{ msg: "Enter a valid email address." }] };
    expect(messageFromBody(body, 422)).toBe("Enter a valid email address.");
  });

  it("explains an oversized upload", () => {
    expect(messageFromBody(null, 413)).toBe("That recording is too large. Try a shorter take.");
  });

  it("uses a calm message for server errors", () => {
    expect(messageFromBody(null, 500))
      .toBe("Something went wrong on our end. Please try again in a moment.");
  });

  it("falls back for anything else", () => {
    expect(messageFromBody(null, 418)).toBe("That didn't work. Please try again.");
  });
});
