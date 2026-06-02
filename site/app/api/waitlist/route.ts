import { NextResponse } from "next/server";
import { isValidEduEmail, normalizeEmail } from "@/lib/validate-email";

type WaitlistPayload = {
  email?: string;
  source?: string;
};

export async function POST(request: Request) {
  let payload: WaitlistPayload;

  try {
    payload = (await request.json()) as WaitlistPayload;
  } catch {
    return NextResponse.json({ error: "Invalid request body." }, { status: 400 });
  }

  const email = normalizeEmail(payload.email ?? "");
  const source: "hero" | "footer" = payload.source === "footer" ? "footer" : "hero";

  if (!isValidEduEmail(email)) {
    return NextResponse.json(
      { error: "Use a .edu email address to join the waitlist." },
      { status: 400 },
    );
  }

  const webhookUrl = process.env.GOOGLE_SHEETS_WEBHOOK_URL;
  if (!webhookUrl) {
    console.error("GOOGLE_SHEETS_WEBHOOK_URL is not configured");
    return NextResponse.json(
      { error: "Waitlist is temporarily unavailable." },
      { status: 502 },
    );
  }

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  const secret = process.env.WAITLIST_WEBHOOK_SECRET;
  if (secret) {
    headers["X-Waitlist-Secret"] = secret;
  }

  const signup = {
    email,
    source,
    timestamp: new Date().toISOString(),
  };

  try {
    const response = await fetch(webhookUrl, {
      method: "POST",
      headers,
      body: JSON.stringify({
        ...signup,
        secret: secret ?? undefined,
      }),
    });

    if (!response.ok) {
      console.error("Google Sheets webhook failed:", response.status);
      return NextResponse.json(
        { error: "Something went wrong. Please try again." },
        { status: 502 },
      );
    }
  } catch (error) {
    console.error("Google Sheets webhook error:", error);
    return NextResponse.json(
      { error: "Something went wrong. Please try again." },
      { status: 502 },
    );
  }

  return NextResponse.json({ ok: true });
}
