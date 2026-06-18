import { describe, expect, it } from "vitest";
import { parseCsv } from "./parse-csv";

describe("parseCsv", () => {
  it("maps rows to header-keyed objects", () => {
    expect(parseCsv("code,name\nUSD,US Dollar\nEUR,Euro")).toEqual([
      { code: "USD", name: "US Dollar" },
      { code: "EUR", name: "Euro" },
    ]);
  });

  it("handles quoted fields with commas and escaped quotes", () => {
    expect(parseCsv('code,name\nXAF,"Franc, BEAC"\nQ,"a ""b"" c"')).toEqual([
      { code: "XAF", name: "Franc, BEAC" },
      { code: "Q", name: 'a "b" c' },
    ]);
  });

  it("trims, skips blank lines, tolerates CRLF and missing trailing cells", () => {
    expect(parseCsv("code,name\r\n GQ , Eq Guinea \r\n\r\nXX")).toEqual([
      { code: "GQ", name: "Eq Guinea" },
      { code: "XX", name: "" },
    ]);
  });

  it("returns [] for empty input", () => {
    expect(parseCsv("")).toEqual([]);
    expect(parseCsv("   \n  ")).toEqual([]);
  });
});
