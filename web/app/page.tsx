"use client";

import { useEffect, useState } from "react";

type Status =
  | "idle"
  | "unsupported"
  | "checking"
  | "subscribing"
  | "subscribed"
  | "denied"
  | "error";

function urlBase64ToUint8Array(base64String: string) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");

  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; i++) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

export default function Home() {
  const [status, setStatus] = useState<Status>("idle");
  const [errorMessage, setErrorMessage] = useState<string>("");

  useEffect(() => {
    if (
      typeof window === "undefined" ||
      !("serviceWorker" in navigator) ||
      !("PushManager" in window)
    ) {
      setStatus("unsupported");
      return;
    }

    setStatus("checking");
    navigator.serviceWorker
      .register("/sw.js")
      .then(async (registration) => {
        const existingSubscription =
          await registration.pushManager.getSubscription();
        setStatus(existingSubscription ? "subscribed" : "idle");
      })
      .catch(() => setStatus("idle"));
  }, []);

  async function enableNotifications() {
    setStatus("subscribing");
    setErrorMessage("");

    try {
      const permission = await Notification.requestPermission();
      if (permission !== "granted") {
        setStatus("denied");
        return;
      }

      const registration = await navigator.serviceWorker.ready;
      const vapidPublicKey = process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY;

      if (!vapidPublicKey) {
        throw new Error("Missing NEXT_PUBLIC_VAPID_PUBLIC_KEY");
      }

      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(vapidPublicKey),
      });

      const response = await fetch("/api/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(subscription),
      });

      if (!response.ok) {
        throw new Error("Failed to save subscription");
      }

      setStatus("subscribed");
    } catch (err) {
      console.error(err);
      setErrorMessage(err instanceof Error ? err.message : "Unknown error");
      setStatus("error");
    }
  }

  return (
    // Changed to min-h-screen and removed justify-center here
    <main className="flex min-h-screen flex-col">
      {/* Wrapped top content in a flex-grow container to center it and push the footer down */}
      <div className="flex flex-grow flex-col items-center justify-center gap-6 px-6 py-16 text-center">
        <div className="flex flex-col gap-2">
          <h1 className="text-3xl font-bold tracking-tight">
            TnP Notification System
          </h1>
          <p className="text-sm text-neutral-500 max-w-sm">
            Get an instant push notification when a new job is posted on the
            college TnP portal. Checks are run every 3 hours.
            <br />
            <br />
            Brave Browser blocks push notifications. Prefer google chrome or
            firefox.
          </p>
        </div>

        <StatusButton
          status={status}
          onClick={enableNotifications}
          errorMessage={errorMessage}
        />
      </div>

      {/* Footer is now locked to the bottom with w-full and py-6 */}
      <div className="w-full border-t border-gray-800 py-6 text-center">
        <div className="flex justify-center space-x-6 text-sm font-medium text-gray-400">
          <a
            href="mailto:ash.alvin.1954@gmail.com"
            className="hover:text-white transition-colors duration-200"
          >
            Email
          </a>
          <a
            href="https://github.com/Zenith-here"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-white transition-colors duration-200"
          >
            GitHub
          </a>
          <a
            href="https://www.linkedin.com/in/ashish-kumar-gupta-997039217/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-white transition-colors duration-200"
          >
            Linkedin
          </a>
        </div>
      </div>
    </main>
  );
}

function StatusButton({
  status,
  onClick,
  errorMessage,
}: {
  status: Status;
  onClick: () => void;
  errorMessage: string;
}) {
  if (status === "unsupported") {
    return (
      <p className="text-sm text-red-500">
        Push notifications aren&apos;t supported in this browser.
      </p>
    );
  }

  if (status === "subscribed") {
    return (
      <div className="flex flex-col items-center gap-1">
        <span className="rounded-full bg-green-100 text-green-800 px-4 py-2 text-sm font-medium dark:bg-green-900/40 dark:text-green-300">
          ✓ Notifications enabled
        </span>
        <p className="text-xs text-neutral-500">
          You&apos;ll be notified here as soon as a new listing appears.
        </p>
      </div>
    );
  }

  if (status === "denied") {
    return (
      <p className="text-sm text-red-500 max-w-xs">
        Notification permission was denied. Enable it in your browser settings
        and reload the page.
      </p>
    );
  }

  return (
    <div className="flex flex-col items-center gap-2">
      <button
        onClick={onClick}
        disabled={status === "subscribing" || status === "checking"}
        className="rounded-full bg-foreground text-background px-6 py-3 text-sm font-semibold transition hover:opacity-90 disabled:opacity-50"
      >
        {status === "subscribing" ? "Enabling…" : "Enable Notifications"}
      </button>
      {status === "error" && (
        <p className="text-xs text-red-500 max-w-xs">
          Something went wrong{errorMessage ? `: ${errorMessage}` : ""}. Please
          try again.
        </p>
      )}
    </div>
  );
}
