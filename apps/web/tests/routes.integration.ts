import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { MongoMemoryReplSet } from "mongodb-memory-server";
import { bootstrap } from "../src/server/bootstrap";
import { disconnect } from "../src/server/db";
import { handle } from "../src/server/handler";

test(
  "162 operational operations dispatch natively; obsolete Local Hub retry is explicitly retired",
  { timeout: 180000 },
  async () => {
    const server = await MongoMemoryReplSet.create({
      instanceOpts: [{ args: ["--nounixsocket"] }],
      replSet: { count: 1, storageEngine: "wiredTiger" },
    });
    Object.assign(process.env, {
      MONGODB_URI: server.getUri(),
      MONGODB_DB: "kalpvriksh_web_routes",
      AUTH_SECRET: "test-only-32-character-auth-secret-value",
      BOOTSTRAP_OWNER_EMAIL: "owner@test.example",
      BOOTSTRAP_OWNER_PASSWORD: "Owner-123-password",
      BOOTSTRAP_CAFE_CASHIER_EMAIL: "cafe@test.example",
      BOOTSTRAP_CAFE_CASHIER_PASSWORD: "Cafe-123-password",
      BOOTSTRAP_RETAIL_CASHIER_EMAIL: "retail@test.example",
      BOOTSTRAP_RETAIL_CASHIER_PASSWORD: "Retail-123-password",
    });
    try {
      const setup = await bootstrap();
      const login = await handle(
        new Request("http://localhost/api/auth/login", {
          method: "POST",
          body: JSON.stringify({
            email: "owner@test.example",
            password: "Owner-123-password",
            recovery_code: setup.recoveryCodes[0],
          }),
        }),
        ["auth", "login"],
      );
      assert.equal(login.status, 200);
      const token = (await login.json()).access_token;
      const spec = JSON.parse(
        readFileSync(
          new URL(
            "../../../docs/nextjs/operational-openapi.json",
            import.meta.url,
          ),
          "utf8",
        ),
      );
      let count = 0;
      for (const [template, methods] of Object.entries(spec.paths) as [
        string,
        Record<string, unknown>,
      ][]) {
        for (const method of Object.keys(methods)) {
          if (!["get", "post", "put", "patch", "delete"].includes(method))
            continue;
          count++;
          if (template === "/api/auth/logout") continue;
          const path = template.replaceAll(/\{[^}]+\}/g, "999999999");
          const response = await handle(
            new Request("http://localhost" + path, {
              method: method.toUpperCase(),
              headers: {
                Authorization: `Bearer ${token}`,
                "X-Venture-Id": "1",
              },
              body: ["get", "delete"].includes(method) ? undefined : "{}",
            }),
            path.slice(5).split("/"),
          );
          const data = response.headers
            .get("content-type")
            ?.includes("application/json")
            ? await response.json()
            : { text: await response.text() };
          assert.notEqual(
            data.error?.code,
            "migration_pending",
            `${method} ${template}`,
          );
          assert.notEqual(
            response.status,
            503,
            `${method} ${template}: ${JSON.stringify(data)}`,
          );
          assert(
            !/^API .* is not defined/.test(data.error?.message ?? ""),
            `${method} ${template} has no native handler`,
          );
          if (template.includes("/sync/dead-letters/") && method === "post")
            assert.equal(response.status, 410);
          else
            assert.notEqual(
              response.status,
              410,
              `${method} ${template} unexpectedly retired`,
            );
        }
      }
      assert.equal(count, 163);
      const logout = await handle(
        new Request("http://localhost/api/auth/logout", {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: "{}",
        }),
        ["auth", "logout"],
      );
      assert.equal(logout.status, 200);
    } finally {
      await disconnect();
      await server.stop();
    }
  },
);
