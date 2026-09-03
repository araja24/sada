/* Thin fetch wrappers around the Sada API (PRD §6). Every call goes through
   request() so error handling and the friendly-message extraction live in
   one place. */
(function (global) {
  "use strict";

  async function request(path, options) {
    let resp;
    try {
      resp = await fetch(path, Object.assign({ credentials: "same-origin" }, options));
    } catch (networkErr) {
      throw new ApiError("We couldn't reach the server. Check your connection and try again.", 0);
    }
    const isJson = (resp.headers.get("content-type") || "").includes("application/json");
    const body = isJson ? await resp.json().catch(function () { return null; }) : null;
    if (!resp.ok) {
      throw new ApiError(messageFromBody(body, resp.status), resp.status, body);
    }
    return body;
  }

  function messageFromBody(body, status) {
    if (body && typeof body.detail === "string") return body.detail;
    if (body && Array.isArray(body.detail) && body.detail[0] && body.detail[0].msg) {
      return body.detail[0].msg;
    }
    if (status === 413) return "That recording is too large. Try a shorter take.";
    if (status >= 500) return "Something went wrong on our end. Please try again in a moment.";
    return "That didn't work. Please try again.";
  }

  function ApiError(message, status, body) {
    this.name = "ApiError";
    this.message = message;
    this.status = status;
    this.body = body || null;
  }
  ApiError.prototype = Object.create(Error.prototype);

  const api = {
    ApiError: ApiError,

    reciters: function () {
      return request("/api/reciters");
    },
    passage: function (reciterId) {
      return request("/api/passages/fatiha?reciter_id=" + encodeURIComponent(reciterId));
    },
    submitAttempt: function (form) {
      return request("/api/attempts", { method: "POST", body: form });
    },
    attempt: function (id) {
      return request("/api/attempts/" + encodeURIComponent(id));
    },
    recentAttempts: function () {
      return request("/api/attempts");
    },
    me: function () {
      return request("/api/auth/me");
    },
    signup: function (email, password) {
      return request("/api/auth/signup", jsonBody({ email: email, password: password }));
    },
    login: function (email, password) {
      return request("/api/auth/login", jsonBody({ email: email, password: password }));
    },
    logout: function () {
      return request("/api/auth/logout", { method: "POST" });
    },
  };

  function jsonBody(obj) {
    return {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(obj),
    };
  }

  global.SadaApi = api;
})(window);
