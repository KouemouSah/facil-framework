import { describe, it, expect } from "vitest";
import { ApiError } from "./api";

describe("ApiError.fieldErrors (422 → field map)", () => {
  it("maps a FastAPI validation array onto the last loc segment", () => {
    const err = new ApiError(422, "Validation failed", {
      detail: [
        { loc: ["body", "currency_id"], msg: "does not reference an existing currency" },
        { loc: ["body", "legal_name"], msg: "field required" },
      ],
    });
    expect(err.fieldErrors()).toEqual({
      currency_id: "does not reference an existing currency",
      legal_name: "field required",
    });
  });

  it("accepts a bare array as the detail too", () => {
    const err = new ApiError(422, "x", [{ loc: ["body", "code"], msg: "bad" }]);
    expect(err.fieldErrors()).toEqual({ code: "bad" });
  });

  it("ignores a non-validation body and keeps first error per field", () => {
    expect(new ApiError(409, "conflict", { detail: "duplicate" }).fieldErrors()).toEqual({});
    const dup = new ApiError(422, "x", {
      detail: [
        { loc: ["body", "code"], msg: "first" },
        { loc: ["body", "code"], msg: "second" },
      ],
    });
    expect(dup.fieldErrors()).toEqual({ code: "first" });
  });

  it("drops entries whose last loc is 'body' (whole-body errors)", () => {
    const err = new ApiError(422, "x", { detail: [{ loc: ["body"], msg: "invalid" }] });
    expect(err.fieldErrors()).toEqual({});
  });
});
