import { NextRequest, NextResponse } from "next/server";
import webpush from "web-push";
import { getSupabaseAdmin } from "@/lib/supabase";

type NotifyPayload = {
  type?: "job" | "news";
  company?: string;
  title?: string;
  url: string;
};

function configureWebPush() {
  const publicKey = process.env.VAPID_PUBLIC_KEY;
  const privateKey = process.env.VAPID_PRIVATE_KEY;
  const subject = process.env.VAPID_SUBJECT || "mailto:admin@example.com";

  if (!publicKey || !privateKey) {
    throw new Error("Missing VAPID_PUBLIC_KEY or VAPID_PRIVATE_KEY");
  }

  webpush.setVapidDetails(subject, publicKey, privateKey);
}

export async function POST(request: NextRequest) {
  const secret = request.headers.get("x-notifier-secret");
  if (!secret || secret !== process.env.NOTIFIER_SECRET_KEY) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  let body: NotifyPayload;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const { company, url, title, type } = body;

  if (!url) {
    return NextResponse.json(
      { error: "Missing required field: url" },
      { status: 400 },
    );
  }

  try {
    configureWebPush();
  } catch (err) {
    console.error(err);
    return NextResponse.json(
      { error: "Push notifications are not configured on the server" },
      { status: 500 },
    );
  }

  const supabase = getSupabaseAdmin();
  const { data: subscribers, error } = await supabase
    .from("subscribers")
    .select("id, endpoint, p256dh, auth");

  if (error) {
    console.error("Failed to fetch subscribers:", error);
    return NextResponse.json(
      { error: "Failed to fetch subscribers" },
      { status: 500 },
    );
  }

  if (!subscribers || subscribers.length === 0) {
    return NextResponse.json({ success: true, sent: 0, failed: 0 });
  }

  let bodyText = "Click to view details on the TnP Portal.";
  if (type === "job") {
    bodyText = `${company} just posted a new listing. Tap to view & apply.`;
  } else if (type === "news") {
    bodyText = "Tap to view the new announcement on the portal.";
  }

  const payload = JSON.stringify({
    title: title || "TnP Portal Update",
    body: bodyText,
    url,
    tag: url,
  });

  let sent = 0;
  let failed = 0;
  const deadSubscriberIds: string[] = [];

  await Promise.all(
    subscribers.map(async (sub) => {
      try {
        await webpush.sendNotification(
          {
            endpoint: sub.endpoint,
            keys: { p256dh: sub.p256dh, auth: sub.auth },
          },
          payload,

          { urgency: "high", TTL: 86400 },
        );
        sent += 1;
      } catch (err) {
        failed += 1;
        const statusCode = (err as { statusCode?: number })?.statusCode;

        if (statusCode === 404 || statusCode === 410) {
          deadSubscriberIds.push(sub.id);
        } else {
          console.error(`Failed to notify subscriber ${sub.id}:`, err);
        }
      }
    }),
  );

  if (deadSubscriberIds.length > 0) {
    await supabase.from("subscribers").delete().in("id", deadSubscriberIds);
  }

  return NextResponse.json({ success: true, sent, failed });
}
