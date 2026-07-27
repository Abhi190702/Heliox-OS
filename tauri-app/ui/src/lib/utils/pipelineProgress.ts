export type PipelineStageStatus = "idle" | "active" | "success" | "error" | "skipped";

export function calculatePipelineProgress(statuses: PipelineStageStatus[]): number {
  if (statuses.length === 0) return 0;
  const terminal = statuses.filter(
    (status) => status === "success" || status === "error" || status === "skipped",
  ).length;
  return Math.round((terminal / statuses.length) * 100);
}
