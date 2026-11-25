// One place for every call to the backend: adds the CSRF header, parses JSON errors,
// sends the user to /login when the session has expired.
import { notify } from "./toast.js";

export class ApiError extends Error {
  constructor(message, status = 0, code = "") {
    super(message);
    this.status = status;
    this.code = code;
  }
}

const csrfToken = () => document.querySelector('meta[name="csrf-token"]')?.content ?? "";

export async function api(method, url, body) {
  const headers = { Accept: "application/json" };
  const options = { method, headers, credentials: "same-origin" };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  if (method !== "GET") headers["X-CSRF-Token"] = csrfToken();

  let response;
  try {
    response = await fetch(url, options);
  } catch {
    throw new ApiError("Cannot reach the server. Check your connection and try again.");
  }

  let data = null;
  try {
    data = await response.json();
  } catch {
    /* empty or non-JSON body */
  }

  const onAuthCall = url.startsWith("/auth/");
  if (response.status === 401 && !onAuthCall) {
    window.location.href = "/login";
    throw new ApiError("Your session expired. Please sign in again.", 401);
  }
  if (!response.ok) {
    throw new ApiError(data?.error ?? `Request failed (${response.status}).`, response.status, data?.code);
  }
  return data;
}

export const get = (url) => api("GET", url);
export const post = (url, body = {}) => api("POST", url, body);
export const patch = (url, body = {}) => api("PATCH", url, body);
export const del = (url) => api("DELETE", url);

/** Run an action: toast the success message, or toast the error. Returns the result or undefined. */
export async function run(action, successMessage) {
  try {
    const result = await action();
    if (successMessage) notify.success(successMessage);
    return result;
  } catch (error) {
    notify.error(error.message);
    return undefined;
  }
}
