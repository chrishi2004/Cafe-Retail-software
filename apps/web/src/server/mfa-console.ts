import { createInterface } from "node:readline/promises";
import { database, disconnect } from "./db";
import { enrollment } from "./accounts";
import { encrypt, decrypt, digest, verifiedTotpStep } from "./security";
const args = process.argv.slice(2),
  action = args[0],
  email = args[args.indexOf("--email") + 1];
try {
  if (
    !["begin", "confirm"].includes(action) ||
    !args.includes("--email") ||
    !email
  )
    throw new Error(
      "Usage: npm run mfa -- begin|confirm --email owner@example.com",
    );
  const { db } = await database();
  const user = await db
    .collection("users")
    .findOne({ email: email.toLowerCase(), is_active: true });
  if (!user) throw new Error("Account not found. No changes made.");
  if (action === "begin") {
    const data = enrollment(user.email);
    await db.collection("users").updateOne(
      { _id: user._id },
      {
        $set: {
          mfa_pending_encrypted: encrypt(data.secret),
          mfa_pending_recovery_hashes: data.recovery_codes.map(digest),
          mfa_pending_expires_at: new Date(
            Date.now() + 15 * 60000,
          ).toISOString(),
        },
      },
    );
    console.log(
      "Add this new TIME-BASED manual key to your authenticator:",
      data.secret,
    );
    console.log(
      "Save these new recovery codes privately:\n" +
        data.recovery_codes.join("\n"),
    );
    console.log(
      "Then run npm run mfa -- confirm --email " +
        user.email +
        ". Existing MFA remains valid until confirmation.",
    );
  } else {
    if (
      !user.mfa_pending_encrypted ||
      Date.parse(user.mfa_pending_expires_at) <= Date.now()
    )
      throw new Error("No current enrollment. Run begin once.");
    const input = createInterface({
      input: process.stdin,
      output: process.stdout,
    });
    let code;
    try {
      code = await input.question("Current six-digit authenticator code: ");
    } finally {
      input.close();
    }
    const step = verifiedTotpStep(
      decrypt(user.mfa_pending_encrypted),
      code.trim(),
    );
    if (step === null)
      throw new Error(
        "Invalid code. Check the latest setup key and automatic phone time.",
      );
    const updated = await db.collection("users").updateOne(
      { _id: user._id, mfa_pending_encrypted: user.mfa_pending_encrypted },
      {
        $set: {
          mfa_enabled: true,
          mfa_secret_encrypted: user.mfa_pending_encrypted,
          mfa_recovery_hashes: user.mfa_pending_recovery_hashes,
          last_totp_step: step,
        },
        $unset: {
          mfa_pending_encrypted: "",
          mfa_pending_recovery_hashes: "",
          mfa_pending_expires_at: "",
        },
        $inc: { token_version: 1 },
      },
    );
    if (!updated.modifiedCount) throw new Error("Enrollment changed. Retry.");
    console.log(
      "MFA enabled. Previous sessions revoked. Wait for a fresh code before login.",
    );
  }
} catch (error) {
  let message = error instanceof Error ? error.message : "MFA setup failed.";
  for (const [name, value] of Object.entries(process.env))
    if (value && /(PASSWORD|SECRET|MONGODB_URI)/.test(name))
      message = message.split(value).join("[REDACTED]");
  console.error(
    message.replace(/mongodb(?:\+srv)?:\/\/[^\s"'<>]+/gi, "[REDACTED]"),
  );
  process.exitCode = 1;
} finally {
  await disconnect();
}
