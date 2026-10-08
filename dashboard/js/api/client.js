// The only place that calls fetch: same-address request with the CSRF token, errors in plain English.
// Screens don't use this directly; they call the named functions in endpoints.js.

const csrfToken = () => document.querySelector('meta[name="csrf-token"]').content;

export async function api(method, path, { json, body, contentType } = {}) {
  const headers = {};
  if (method !== "GET") headers["X-CSRF-Token"] = csrfToken();
  let payload = body;
  if (json !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(json);
  } else if (contentType) {
    headers["Content-Type"] = contentType;
  }
  let response;
  try {
    response = await fetch(path, { method, headers, body: payload, cache: "no-store" });
  } catch {
    throw new Error("Can't reach Budget Buddy. Is it still running in its window?");
  }
  if (response.status === 204) return null;
  let data = null;
  try {
    data = await response.json();
  } catch {
    /* not JSON */
  }
  if (!response.ok) throw new Error(plainError(data, response.status));
  return data;
}

function plainError(data, status) {
  if (data && data.error && data.error.message) return data.error.message;
  if (data && Array.isArray(data.detail) && data.detail.length) {
    return `Please check your entries: ${data.detail[0].msg || "something looks wrong"}.`;
  }
  if (data && typeof data.detail === "string") return data.detail;
  return `Something went wrong (code ${status}).`;
}
