export function pollAfterSuccessfulProbe(probe: () => Promise<boolean>, intervalMs: number): () => void {
  let interval: ReturnType<typeof setInterval> | undefined;
  let active = true;

  void probe().then((supported) => {
    if (active && supported) interval = setInterval(() => void probe(), intervalMs);
  });

  return () => {
    active = false;
    if (interval) clearInterval(interval);
  };
}
