"use client";
import { ErrorState } from "@/components/ui/primitives";
export default function ErrorPage({ reset }: { reset: () => void }) { return <ErrorState message="This page could not be loaded. Please retry." retry={reset} />; }
