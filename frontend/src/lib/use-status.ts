"use client";
import useSWR from "swr";
import { fetcher, type Status } from "./api";

export function useStatus() {
  return useSWR<Status>("/api/status", fetcher, { refreshInterval: 2500, dedupingInterval: 1000 });
}
