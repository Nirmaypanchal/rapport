"use client";
/* In-app confirm and prompt dialogs. Browser `confirm()`/`prompt()` are no-ops inside the desktop WebView,
   so every destructive or text-input action goes through here. */
import { createContext, useCallback, useContext, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";

type ConfirmOpts = { title: string; description?: React.ReactNode; confirmLabel?: string; cancelLabel?: string; destructive?: boolean };
type PromptOpts = { title: string; description?: React.ReactNode; placeholder?: string; defaultValue?: string; confirmLabel?: string };
type Ctx = { confirm: (o: ConfirmOpts) => Promise<boolean>; promptText: (o: PromptOpts) => Promise<string | null> };

const ConfirmContext = createContext<Ctx | null>(null);

export function ConfirmProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<({ kind: "confirm" } & ConfirmOpts) | ({ kind: "prompt" } & PromptOpts) | null>(null);
  const [value, setValue] = useState("");
  const resolver = useRef<((v: boolean | string | null) => void) | null>(null);

  const close = (result: boolean | string | null) => { resolver.current?.(result); resolver.current = null; setState(null); };
  const confirm = useCallback((o: ConfirmOpts) => new Promise<boolean>((res) => { resolver.current = (v) => res(v === true); setState({ kind: "confirm", ...o }); }), []);
  const promptText = useCallback((o: PromptOpts) => new Promise<string | null>((res) => { resolver.current = (v) => res(typeof v === "string" ? v : null); setValue(o.defaultValue ?? ""); setState({ kind: "prompt", ...o }); }), []);

  return (
    <ConfirmContext.Provider value={{ confirm, promptText }}>
      {children}
      <Dialog open={state != null} onOpenChange={(o) => !o && close(state?.kind === "prompt" ? null : false)}>
        <DialogContent className="sm:max-w-[440px]">
          {state && (
            <>
              <DialogHeader><DialogTitle>{state.title}</DialogTitle>{state.description && <DialogDescription className="whitespace-pre-line">{state.description}</DialogDescription>}</DialogHeader>
              {state.kind === "prompt" && (
                <Input autoFocus value={value} onChange={(e) => setValue(e.target.value)} placeholder={state.placeholder} className="tc bg-surface" onKeyDown={(e) => { if (e.key === "Enter" && value.trim()) close(value.trim()); }} />
              )}
              <DialogFooter>
                <Button variant="outline" onClick={() => close(state.kind === "prompt" ? null : false)}>{(state.kind === "confirm" && state.cancelLabel) || "Cancel"}</Button>
                {state.kind === "confirm" ? (
                  <Button variant={state.destructive ? "destructive" : "default"} onClick={() => close(true)}>{state.confirmLabel ?? "Continue"}</Button>
                ) : (
                  <Button disabled={!value.trim()} onClick={() => close(value.trim())}>{state.confirmLabel ?? "OK"}</Button>
                )}
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>
    </ConfirmContext.Provider>
  );
}

export function useConfirm(): Ctx {
  const ctx = useContext(ConfirmContext);
  if (!ctx) throw new Error("useConfirm must be used inside ConfirmProvider");
  return ctx;
}
