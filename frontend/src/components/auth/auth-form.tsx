"use client";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { ArrowRight, CheckCircle2, FileCheck, LockKeyhole, Quote } from "lucide-react";
import { api, setCsrf } from "@/services/api";
import { Brand } from "@/components/layout/brand";
import { Button, ErrorState } from "@/components/ui/primitives";
import { errorMessage } from "@/lib/utils";

type Mode = "login" | "register" | "forgot" | "reset";
const titles = { login: "Welcome back.", register: "A home for your knowledge.", forgot: "Forgot your password?", reset: "Choose a new password." };
const subtitles = { login: "Pick up where your thinking left off.", register: "Create your private workspace. Start with a document.", forgot: "We’ll email you a link to get back into your workspace.", reset: "Use at least 12 characters to protect your workspace." };
const subscribeLocation = (callback: () => void) => { window.addEventListener("popstate", callback); return () => window.removeEventListener("popstate", callback); };
export function AuthForm({ mode }: { mode: Mode }) {
  const router = useRouter(); const client = useQueryClient(); const [error, setError] = useState(""); const [success, setSuccess] = useState(""); const resetToken = useRef("");
  const expired = useSyncExternalStore(subscribeLocation, () => new URLSearchParams(window.location.search).has("expired"), () => false);
  useEffect(() => { const token = new URLSearchParams(window.location.hash.slice(1)).get("token"); if (token) resetToken.current = token; if (window.location.hash) history.replaceState(null, "", window.location.pathname); }, []);
  const schema = z.object({ email: mode === "reset" ? z.string() : z.email("Enter a valid email address."), password: mode === "forgot" ? z.string() : z.string().min(mode === "login" ? 1 : 12, mode === "login" ? "Enter your password." : "Use at least 12 characters.").max(128), display_name: mode === "register" ? z.string().trim().min(1, "Enter your name.").max(100) : z.string() });
  type Values = z.infer<typeof schema>;
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { email: "", password: "", display_name: "" } });
  async function submit(values: Values) {
    setError("");
    try {
      if (mode === "forgot") { setSuccess((await api.forgot(values.email)).message); return; }
      if (mode === "reset") { if (!resetToken.current) throw new Error("This reset link is incomplete. Request a new password reset email."); await api.reset(resetToken.current, values.password); setSuccess("Your password was updated. You can now sign in."); return; }
      const session = mode === "register" ? await api.register(values) : await api.login(values);
      setCsrf(session.csrf_token); client.clear(); client.setQueryData(["session"], session); router.push("/app/dashboard");
    } catch (err) { setError(errorMessage(err)); }
  }
  return <div className="auth-page"><aside className="auth-aside"><Brand /><div><div className="eyebrow" style={{ color: "#9db8ee", marginBottom: 24 }}>Less searching. More understanding.</div><h2>Your next insight is already in your documents.</h2><p>Bring your knowledge together. Ask a question. Follow the answer all the way back to its source.</p><div className="auth-proof"><FileCheck size={19} />PDF, Word, Markdown & text</div><div className="auth-proof"><Quote size={19} />Grounded answers. Verifiable citations.</div></div><div className="row small" style={{ color: "#b7c4d8" }}><LockKeyhole size={15} />Private by design. Built for focused work.</div></aside><main className="auth-main"><div className="auth-form"><div className="mobile-only" style={{ marginBottom: 40 }}><Brand /></div><h1>{titles[mode]}</h1><p>{subtitles[mode]}</p>{expired && <p role="status" className="small">Your session ended. Sign in to continue.</p>}{success ? <div className="stack"><CheckCircle2 className="accent" size={30} /><p role="status">{success}</p><Link href="/login" className="button button-primary">Back to sign in</Link></div> : <form className="form-stack" onSubmit={event => { void handleSubmit(submit)(event); }} noValidate>{error && <ErrorState message={error} />}{mode === "register" && <div className="field"><label htmlFor="display_name">Full name</label><input id="display_name" autoComplete="name" {...register("display_name")} aria-invalid={!!errors.display_name} aria-describedby="name-error" />{errors.display_name && <span id="name-error" className="field-error" role="alert">{errors.display_name.message}</span>}</div>}{mode !== "reset" && <div className="field"><label htmlFor="email">Email address</label><input id="email" type="email" autoComplete="email" placeholder="you@company.com" {...register("email")} aria-invalid={!!errors.email} aria-describedby="email-error" />{errors.email && <span id="email-error" className="field-error" role="alert">{errors.email.message}</span>}</div>}{mode !== "forgot" && <div className="field"><div className="row between"><label htmlFor="password">Password</label>{mode === "login" && <Link href="/forgot-password" className="text-link small">Forgot password?</Link>}</div><input id="password" type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} placeholder={mode === "login" ? "Enter your password" : "At least 12 characters"} {...register("password")} aria-invalid={!!errors.password} aria-describedby="password-error" />{errors.password && <span id="password-error" className="field-error" role="alert">{errors.password.message}</span>}</div>}<Button type="submit" busy={isSubmitting}>{mode === "login" ? "Sign in" : mode === "register" ? "Create account" : mode === "forgot" ? "Send reset link" : "Update password"}<ArrowRight size={16} /></Button></form>}<div className="auth-footer">{mode === "login" ? <>New to KnowledgePilot? <Link href="/register">Create an account</Link></> : mode === "register" ? <>Already have a workspace? <Link href="/login">Sign in</Link></> : <Link href="/login">Back to sign in</Link>}</div></div></main></div>;
}

