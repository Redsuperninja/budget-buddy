// expo-router parses every deep-link query with query-string, which needs
// decode-uri-component to load as a plain function (see issue #21).
// eslint-disable-next-line @typescript-eslint/no-require-imports
const queryString = require("query-string");

describe("query-string (used by expo-router for links)", () => {
  it("parses a query, even with broken percent-encoding", () => {
    expect(queryString.parse("?a=%E0%A4%A&b=1").b).toBe("1");
    expect(queryString.parse("?a=hello%20there")).toEqual({ a: "hello there" });
  });
});
