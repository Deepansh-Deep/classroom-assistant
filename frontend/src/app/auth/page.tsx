"use client";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { token } from "../../lib/api";

// Google OAuth lands here with the session token in the URL fragment (never sent to any server).
export default function AuthCallback() {
  const router = useRouter();
  useEffect(() => {
    const t = new URLSearchParams(window.location.hash.slice(1)).get("token");
    if (t) token.set(t);
    history.replaceState(null, "", "/auth/");
    router.replace(t ? "/dashboard/" : "/");
  }, [router]);
  return <p className="p-10 text-center text-ink-300">Signing you in…</p>;
}
