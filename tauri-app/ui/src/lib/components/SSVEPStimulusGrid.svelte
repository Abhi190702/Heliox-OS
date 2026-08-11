<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import { call } from "../api/daemon";
  import { neural } from "../stores/neural";

  const targets = [
    { id: "focus_left", label: "Focus left", frequency: "8 Hz", period: "125ms" },
    { id: "focus_right", label: "Focus right", frequency: "10 Hz", period: "100ms" },
    { id: "select", label: "Select", frequency: "12 Hz", period: "83.333ms" },
    { id: "cancel", label: "Cancel / stop", frequency: "15 Hz", period: "66.667ms" },
  ];

  function marker(event: "grid_shown" | "grid_hidden" | "target_on" | "target_off", targetId?: string) {
    if (!$neural.sessionId) return;
    void call("neural_stimulus_marker", {
      session_id: $neural.sessionId,
      event,
      target_id: targetId ?? null,
      client_performance_ms: performance.now(),
    }).catch((cause) => console.warn("SSVEP marker was not accepted.", cause));
  }

  onMount(() => marker("grid_shown"));
  onDestroy(() => marker("grid_hidden"));
</script>

<div class="stimulus-shell" aria-label="Four-target SSVEP research stimulus">
  <div class="stimulus-header">
    <strong>SSVEP research targets</strong>
    <span>Display timing is approximate until monitor refresh and marker timing are validated.</span>
  </div>
  <div class="stimulus-grid">
    {#each targets as target (target.id)}
      <button
        class="stimulus-target"
        style={`--stimulus-period: ${target.period}`}
        onpointerdown={() => marker("target_on", target.id)}
        onpointerup={() => marker("target_off", target.id)}
        onpointercancel={() => marker("target_off", target.id)}
      >
        <span class="flicker" aria-hidden="true"></span>
        <strong>{target.label}</strong>
        <small>{target.frequency}</small>
      </button>
    {/each}
  </div>
</div>

<style>
  .stimulus-shell {
    position: absolute;
    left: 18px;
    right: 18px;
    bottom: 72px;
    z-index: 70;
    padding: 10px;
    background: color-mix(in srgb, var(--bg-secondary) 96%, transparent);
    border: 1px solid color-mix(in srgb, var(--accent) 45%, var(--border));
    border-radius: 12px;
    box-shadow: var(--shadow);
    backdrop-filter: blur(14px);
  }
  .stimulus-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 8px;
  }
  .stimulus-header strong {
    font-size: 10px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }
  .stimulus-header span {
    color: var(--warning);
    font-size: 9px;
  }
  .stimulus-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 8px;
  }
  .stimulus-target {
    display: grid;
    grid-template-columns: 22px 1fr auto;
    gap: 8px;
    align-items: center;
    min-width: 0;
    padding: 8px;
    background: var(--bg-primary);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: inherit;
    font: inherit;
    text-align: left;
  }
  .stimulus-target strong {
    overflow: hidden;
    font-size: 10px;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .stimulus-target small {
    color: var(--text-muted);
    font: 9px var(--font-mono, monospace);
  }
  .flicker {
    width: 22px;
    height: 22px;
    background: white;
    border: 1px solid rgba(255, 255, 255, 0.45);
    border-radius: 4px;
    animation: ssvep-flicker var(--stimulus-period) steps(1, end) infinite;
  }
  @keyframes ssvep-flicker {
    0%,
    49% {
      background: white;
    }
    50%,
    100% {
      background: #050509;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .flicker {
      animation: none;
      background: repeating-linear-gradient(45deg, #fff 0 3px, #050509 3px 6px);
    }
  }
</style>
