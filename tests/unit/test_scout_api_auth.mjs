import test from "node:test";
import assert from "node:assert/strict";

import {
  extractBearerToken,
  isAuthorizedRequest,
} from "../../apps/console/lib/api-auth-core.ts";

test("extractBearerToken parses bearer header", () => {
  const req = new Request("http://localhost", {
    headers: { Authorization: "Bearer secret-token" },
  });
  assert.equal(extractBearerToken(req), "secret-token");
});

test("isAuthorizedRequest accepts valid token when configured", () => {
  process.env.SCOUT_API_TOKEN = "secret-token";
  const req = new Request("http://localhost", {
    headers: { Authorization: "Bearer secret-token" },
  });
  assert.equal(isAuthorizedRequest(req), true);
  delete process.env.SCOUT_API_TOKEN;
});

test("isAuthorizedRequest rejects invalid token", () => {
  process.env.SCOUT_API_TOKEN = "secret-token";
  const req = new Request("http://localhost", {
    headers: { Authorization: "Bearer wrong" },
  });
  assert.equal(isAuthorizedRequest(req), false);
  delete process.env.SCOUT_API_TOKEN;
});

test("isAuthorizedRequest rejects missing token when configured", () => {
  process.env.SCOUT_API_TOKEN = "secret-token";
  const req = new Request("http://localhost");
  assert.equal(isAuthorizedRequest(req), false);
  delete process.env.SCOUT_API_TOKEN;
});

test("isAuthorizedRequest allows all when SCOUT_API_TOKEN unset", () => {
  delete process.env.SCOUT_API_TOKEN;
  const req = new Request("http://localhost");
  assert.equal(isAuthorizedRequest(req), true);
});
