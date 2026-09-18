/* Typed client for the Python API. In production the app is served by that server, so the base is "". */
export const API = (typeof window !== "undefined" && (window as unknown as { __RAPPORT_API__?: string }).__RAPPORT_API__) || process.env.NEXT_PUBLIC_API_BASE || "";

/** The desktop shell passes a per-launch token as ?token=…; it is kept for the session and sent with every call. */
function readToken(): string {
  if (typeof window === "undefined") return "";
  try {
    const fromUrl = new URLSearchParams(window.location.search).get("token");
    if (fromUrl) { sessionStorage.setItem("rapportToken", fromUrl); return fromUrl; }
    return sessionStorage.getItem("rapportToken") ?? "";
  } catch { return ""; }
}
export const TOKEN = readToken();
const withToken = (url: string) => (TOKEN ? `${url}${url.includes("?") ? "&" : "?"}token=${encodeURIComponent(TOKEN)}` : url);

export type Word = [string, number, number];

export type Speaker = {
  id?: number;
  label: string;
  person_id: number | null;
  person_name: string | null;
  person_color: string | null; // palette name, e.g. "sky"
  person_auto?: number | null;
  display_name?: string | null; // for transcripts imported without people (e.g. "Me" / "Others")
  speaking_sec: number;
  similarity: number | null;
  embedding_model?: string | null;
};

export type Segment = {
  id: number;
  idx: number;
  speaker_label: string;
  start: number;
  end: number;
  text: string;
  words: Word[];
};

export type Recording = {
  id: number;
  original_name: string;
  title: string | null;
  notes: string;
  recorded_at: string | null;
  duration_sec: number | null;
  sample_rate: number | null;
  transmitter: string | null;
  status: "queued" | "processing" | "done" | "error";
  stage: string | null;
  progress?: number | null;
  error: string | null;
  language: string | null;
  diarizer: string | null;
  deleted_from_device: number;
  source?: "dji" | "voicememos" | "file" | "usb" | "folder" | "microphone" | "granola" | "omi" | "notion" | null;
  source_id?: string | null;
  has_audio?: number | null;
  whisper_model?: string | null;
  processed_at?: string | null;
  imported_at?: string | null;
  summary?: string | null;
  summary_model?: string | null;
  summary_at?: string | null;
  summary_status?: "queued" | "running" | "done" | "error" | null;
  summary_error?: string | null;
  summary_template?: string | null;
  speakers: Speaker[];
  peaks_mini?: number[];
  segments?: Segment[];
  peaks?: number[];
};

export type Person = {
  id: number;
  name: string;
  auto: number;
  color: string;
  note: string;
  created_at: string;
  appearances: number;
  speaking_sec: number;
  last_heard: string | null;
  recordings?: Appearance[];
};

export type Appearance = {
  recording_id: number;
  title: string | null;
  original_name: string;
  recorded_at: string | null;
  duration_sec: number | null;
  label: string;
  speaking_sec: number;
  similarity: number | null;
};

export type Settings = {
  auto_import: boolean;
  delete_from_device_after_import: boolean;
  poll_interval_sec: number;
  whisper_model: string;
  language: string | null;
  diarizer: string;
  hf_token: string;
  person_match_threshold: number;
  cluster_distance_threshold: number;
  min_speaker_seconds: number;
  skip_silence_min_gap: number;
  skip_silence_pad: number;
  open_browser: boolean;
  auto_import_voice_memos: boolean;
  summary_provider: "auto" | "ollama" | "mlx" | "off";
  summary_model: string;
  auto_summarize: boolean;
  summary_template: string;
  summary_custom_prompt: string;
  /** Per-source defaults, `{ granola: "meeting" }`. A source that is not a key uses `summary_template`. */
  summary_template_by_source: Record<string, string>;
  usb_volumes: string[];
  watched_folders: string[];
  granola_api_key: string; granola_auto: boolean;
  omi_api_key: string; omi_auto: boolean;
  notion_token: string; notion_database_id: string; notion_auto: boolean;
  sync_interval_sec: number;
};

export type Sources = {
  volumes: { mount: string; name: string; media: string; is_dji: boolean; files: number; enabled: boolean }[];
  microphones: string[];
  recording: { device: string; started_at: number; elapsed: number } | null;
  recording_error: string | null;
  voice_memos: Omit<VoiceMemosStatus, "memos">;
  watched_folders: string[];
  connectors: Record<"granola" | "omi" | "notion", { configured: boolean; auto: boolean; last_sync?: string; last_error?: string | null; last_count?: number }>;
  counts: Record<string, number>;
};

export type VoiceMemo = { uid: string; title: string; recorded_at: string | null; duration_sec: number | null; path: string; size_bytes: number; imported: boolean };
export type VoiceMemosStatus = { available: boolean; reason: "permission" | "not_found" | "error" | null; message: string | null; python: string; memos: VoiceMemo[]; app_name?: string; app_path?: string | null; in_app?: boolean };

/** Multipart upload of audio files; they are copied into the library and queued. */
export async function uploadFiles(files: File[]): Promise<{ imported: number[]; skipped: string[] }> {
  const fd = new FormData();
  for (const f of files) fd.append("files", f, f.name);
  const res = await fetch(API + "/api/import/upload", { method: "POST", body: fd, headers: TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {} });
  if (!res.ok) throw new ApiError(res.status, await res.text());
  return res.json();
}

export type Status = {
  library: string;
  importer: { volumes: { mount: string; name: string; media: string; files: number }[]; importing: string | null; last_scan: string | null; last_error: string | null };
  worker: { current: { id: number; name: string; stage: string; progress?: number } | null; models: { embedder_loaded: boolean; pyannote_loaded: boolean; pyannote_error: string | null; builtin_loaded: boolean } };
  stats: { recordings: number; queued: number; people: number; hours: number };
  settings: Settings;
  hf_token_present: boolean;
  recording: { device: string; started_at: number; elapsed: number } | null;
};

export type SearchHit = {
  id: number;
  recording_id: number;
  speaker_label: string;
  start: number;
  end: number;
  snippet: string;
  title: string | null;
  original_name: string;
  recorded_at: string | null;
  person_name: string | null;
  person_color: string | null;
};

/** One block of a written summary that matched. No `start`: a summary block has no second to open at,
 *  which is why its card opens the recording's Summary tab instead of the player. */
export type SummaryHit = {
  id: number;
  recording_id: number;
  idx: number;
  heading: string | null;
  text: string;
  snippet: string;
  title: string | null;
  original_name: string;
  recorded_at: string | null;
};

/** What Search finds: the turns that match and the summary blocks that do, as two lists. Not one
 *  re-ranked list — the two bm25 scores come from different FTS tables and are not on the same scale. */
export type SearchResults = { moments: SearchHit[]; summaries: SummaryHit[] };

/** One piece of evidence behind an answer: a `moment` that was said, or a block of a written `summary`.
 *  A summary has no timestamp, so `segment_id` is null and `start` is 0 — it opens on the Summary tab. */
export type AskSource = {
  n: number;
  kind: "moment" | "summary";
  recording_id: number;
  segment_id: number | null;
  start: number;
  end: number;
  speaker: string;
  person_color: string | null;
  heading: string | null;
  text: string;
  snippet: string;
  title: string;
  recorded_at: string | null;
  cited: boolean;
};

/** `answer` is null when there is nothing to write from, or no model to write it; `reason` says which. */
export type AskAnswer = {
  question: string;
  answer: string | null;
  sources: AskSource[];
  model: { provider: string; model: string } | null;
  reason: "no_matches" | "no_model" | "model_error" | "empty_answer" | null;
  error: string | null;
};

export type LogLine = { id: number; ts: string; level: "info" | "warn" | "error"; message: string };

/** A shape a summary can take. `builtin` ones ship with the app; the other is the user's own prompt. */
export type SummaryTemplate = { id: string; name: string; description: string; builtin: boolean };
export type SummaryTemplates = {
  templates: SummaryTemplate[];
  /** The default from Settings, already resolved (a "custom" with no prompt written comes back as "meeting"). */
  default: string;
  /** Defaults set for particular sources; only entries naming a template that exists. */
  by_source: Record<string, string>;
  /** The sources this library holds recordings from, most first, plus any that carry an override. */
  sources: { id: string; count: number }[];
};

/** The template a recording without one of its own will be summarized with: its source's default, else the default. */
export function defaultTemplateFor(source: string | null | undefined, tpl: SummaryTemplates | undefined): string {
  return tpl ? (tpl.by_source?.[source || "dji"] ?? tpl.default) : "";
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function api<T>(path: string, init?: RequestInit & { json?: unknown }): Promise<T> {
  const { json, ...rest } = init ?? {};
  const res = await fetch(API + path, {
    ...rest,
    headers: { "Content-Type": "application/json", ...(TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {}), ...(rest.headers ?? {}) },
    body: json !== undefined ? JSON.stringify(json) : rest.body,
  });
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const data = await res.json();
      msg = typeof data?.detail === "string" ? data.detail : JSON.stringify(data?.detail ?? data);
    } catch {
      /* keep statusText */
    }
    throw new ApiError(res.status, msg);
  }
  const ct = res.headers.get("content-type") ?? "";
  return (ct.includes("json") ? res.json() : res.text()) as Promise<T>;
}

export const fetcher = <T,>(path: string) => api<T>(path);

/** One line of `/api/ask`: a piece of the answer as the model writes it, or the finished answer itself. */
export type AskEvent = { delta: string } | AskAnswer;

/**
 * Ask a question and watch the answer being written. `onDelta` is called with each piece; the promise
 * resolves with the same body `/api/ask` used to return in one go, which is the only thing that carries
 * `sources` — so a citation number cannot be resolved until it arrives.
 *
 * `api()` is not reused: it reads one JSON body, and this one comes a line at a time.
 */
export async function askStream(q: string, onDelta: (piece: string) => void): Promise<AskAnswer> {
  const res = await fetch(API + "/api/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {}) },
    body: JSON.stringify({ q }),
  });
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const data = await res.json();
      msg = typeof data?.detail === "string" ? data.detail : JSON.stringify(data?.detail ?? data);
    } catch {
      /* keep statusText */
    }
    throw new ApiError(res.status, msg);
  }
  const reader = res.body?.getReader();
  if (!reader) throw new ApiError(500, "This browser cannot read a streamed answer.");

  const decoder = new TextDecoder();
  let buffer = "";
  let answer: AskAnswer | null = null;
  const take = (line: string) => {
    if (!line.trim()) return;
    const event = JSON.parse(line) as AskEvent;
    if ("delta" in event) onDelta(event.delta);
    else answer = event;
  };
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let nl: number;
    // A JSON object never spans two lines, so a newline is always the end of one event.
    while ((nl = buffer.indexOf("\n")) >= 0) {
      take(buffer.slice(0, nl));
      buffer = buffer.slice(nl + 1);
    }
  }
  take(buffer); // a last line the server did not end with a newline
  if (!answer) throw new ApiError(500, "The answer stopped before it was finished.");
  return answer;
}

export const urls = {
  audio: (id: number) => withToken(`${API}/api/recordings/${id}/audio`),
  original: (id: number) => withToken(`${API}/api/recordings/${id}/original`),
  transcript: (id: number) => withToken(`${API}/api/recordings/${id}/transcript.txt`),
  condensed: (id: number, minGap: number, pad: number) => withToken(`${API}/api/recordings/${id}/condensed?min_gap=${minGap}&pad=${pad}`),
};


/** Open a web page in the user's default browser. Inside the desktop WebView, target="_blank" does nothing, so the backend opens it. */
export async function openExternal(url: string): Promise<void> {
  if (TOKEN) { await api("/api/system/open", { method: "POST", json: { target: `url:${url}` } }); return; }
  window.open(url, "_blank", "noopener");
}

/** Save an export (transcript, original audio, condensed audio) to ~/Downloads/Rapport and reveal it in Finder. */
export async function exportRecording(id: number, kind: "transcript" | "original" | "condensed"): Promise<{ path: string }> {
  return api(`/api/recordings/${id}/export`, { method: "POST", json: { kind } });
}
