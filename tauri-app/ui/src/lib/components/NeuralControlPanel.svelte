<script lang="ts">
  import { onMount } from "svelte";
  import { _ } from "svelte-i18n";
  import { neural } from "../stores/neural";

  let source = $state<"synthetic" | "playback" | "brainflow" | "lsl">("synthetic");
  let artifactPath = $state("");
  let playbackPath = $state("");
  let boardId = $state(0);
  let serialPort = $state("");
  let lslName = $state("HelioxEEG");
  let syntheticFrequency = $state(12);
  let warningAccepted = $state(false);

  onMount(() => {
    void neural.refresh();
    const timer = setInterval(() => void neural.refresh(), 1500);
    return () => clearInterval(timer);
  });

  function start() {
    void neural.startSidecar({
      source,
      artifactPath: artifactPath || null,
      playbackPath: playbackPath || null,
      boardId,
      serialPort,
      lslName,
      syntheticFrequency,
    });
  }

  function percent(value: number | undefined): string {
    return `${Math.round((value ?? 0) * 100)}%`;
  }
</script>

<div class="neural-panel">
  <div class="panel-header">
    <div>
      <h3>{$_("neural.title")}</h3>
      <span class="subtitle">{$_("neural.subtitle")}</span>
    </div>
    <span class:online={$neural.connected} class="status-pill">
      {$neural.connected ? $_("neural.connected") : $_("neural.disconnected")}
    </span>
  </div>

  <div class="boundary-note">
    <strong>{$_("neural.research_only")}</strong>
    <span>{$_("neural.boundary")}</span>
  </div>

  <label class="consent-row">
    <input type="checkbox" bind:checked={warningAccepted} onchange={() => neural.setStimulusEnabled(warningAccepted)} />
    <span>{$_("neural.photosensitivity")}</span>
  </label>

  <div class="configuration-grid">
    <label>
      <span>{$_("neural.source")}</span>
      <select bind:value={source} disabled={$neural.sidecarRunning}>
        <option value="synthetic">{$_("neural.synthetic")}</option>
        <option value="playback">{$_("neural.playback")}</option>
        <option value="brainflow">BrainFlow</option>
        <option value="lsl">Lab Streaming Layer</option>
      </select>
    </label>
    {#if source !== "synthetic"}
      <label class="wide">
        <span>{$_("neural.artifact_path")}</span>
        <input bind:value={artifactPath} placeholder="C:\path\calibration.json" disabled={$neural.sidecarRunning} />
      </label>
    {/if}
    {#if source === "playback"}
      <label class="wide">
        <span>{$_("neural.playback_path")}</span>
        <input bind:value={playbackPath} placeholder="C:\path\recording.npz" disabled={$neural.sidecarRunning} />
      </label>
    {:else if source === "brainflow"}
      <label>
        <span>{$_("neural.board_id")}</span>
        <input type="number" bind:value={boardId} disabled={$neural.sidecarRunning} />
      </label>
      <label>
        <span>{$_("neural.serial_port")}</span>
        <input bind:value={serialPort} placeholder="COM3" disabled={$neural.sidecarRunning} />
      </label>
    {:else if source === "lsl"}
      <label>
        <span>{$_("neural.lsl_name")}</span>
        <input bind:value={lslName} disabled={$neural.sidecarRunning} />
      </label>
    {:else}
      <label>
        <span>{$_("neural.simulated_target")}</span>
        <select bind:value={syntheticFrequency} disabled={$neural.sidecarRunning}>
          <option value={8}>8 Hz · focus left</option>
          <option value={10}>10 Hz · focus right</option>
          <option value={12}>12 Hz · select</option>
          <option value={15}>15 Hz · cancel</option>
        </select>
      </label>
    {/if}
  </div>

  <div class="actions">
    {#if !$neural.sidecarRunning}
      <button class="primary" onclick={start} disabled={!warningAccepted || $neural.busy}>
        {$_("neural.start")}
      </button>
    {:else}
      <button onclick={() => neural.stopSidecar()} disabled={$neural.busy}>{$_("neural.stop")}</button>
    {/if}
    <button
      onclick={() => neural.beginCalibration()}
      disabled={!$neural.connected || $neural.state !== "connected_uncalibrated" || $neural.busy}
      >{$_("neural.calibrate")}</button
    >
    <button
      onclick={() => neural.arm("navigate")}
      disabled={!$neural.calibrated || $neural.state !== "observe_only" || $neural.busy}>{$_("neural.arm_ui")}</button
    >
    <button
      onclick={() => neural.arm("safe_desktop")}
      disabled={!$neural.calibrated || $neural.state !== "observe_only" || $neural.busy}
      >{$_("neural.arm_desktop")}</button
    >
    <button class="danger" onclick={() => neural.disarm()} disabled={!$neural.connected}>{$_("neural.disarm")}</button>
  </div>

  <div class="status-grid">
    <div><span>{$_("neural.state")}</span><strong>{$neural.state.replaceAll("_", " ")}</strong></div>
    <div><span>{$_("neural.transport")}</span><strong>{$neural.transport || "—"}</strong></div>
    <div>
      <span>{$_("neural.signal")}</span>
      <strong class:good={$neural.quality?.quality === "good"}>{$neural.quality?.quality ?? "waiting"}</strong>
    </div>
    <div>
      <span>{$_("neural.buffer")}</span><strong>{$neural.bufferedSamples} / {$neural.droppedSamples} dropped</strong>
    </div>
    <div><span>{$_("neural.calibration")}</span><strong>{$neural.calibrated ? "verified" : "required"}</strong></div>
    <div>
      <span>{$_("neural.held_accuracy")}</span>
      <strong>{percent($neural.calibrationMetrics?.balanced_accuracy)}</strong>
    </div>
  </div>

  {#if $neural.quality?.artifact_flags.length}
    <div class="artifact-warning" role="alert">
      {$_("neural.artifacts")}: {$neural.quality.artifact_flags.join(", ")} · {$neural.quality.reasons.join(", ")}
    </div>
  {/if}

  <div class="goal-list" aria-label={$_("neural.safe_goals")}>
    <div class="goal-header">
      <strong>{$_("neural.safe_goals")}</strong>
      <span>{$_("neural.physical_disabled")}</span>
    </div>
    {#each $neural.safeGoals as goal (goal.command_id)}
      <div class:focused={$neural.focusedCommandId === goal.command_id} class="goal">
        <span>{goal.label}</span>
        <small>{goal.description}</small>
        <code>Tier {goal.permission_tier} · {goal.action_type}</code>
      </div>
    {:else}
      <p class="empty">{$_("neural.no_goals")}</p>
    {/each}
  </div>

  {#if $neural.error}<div class="error" role="alert">{$neural.error}</div>{/if}
</div>

<style>
  .neural-panel {
    overflow: hidden;
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    background: var(--bg-secondary);
  }
  .panel-header,
  .actions,
  .goal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }
  .panel-header {
    padding: 14px;
    background: var(--bg-tertiary);
  }
  h3 {
    margin: 0;
    font-size: 14px;
  }
  .subtitle,
  label span,
  .status-grid span,
  small,
  .goal-header span {
    color: var(--text-muted);
    font-size: 11px;
  }
  .status-pill {
    padding: 4px 9px;
    color: var(--text-muted);
    border: 1px solid var(--border);
    border-radius: 999px;
    font-size: 10px;
    text-transform: uppercase;
  }
  .status-pill.online,
  .good {
    color: var(--success);
    border-color: color-mix(in srgb, var(--success) 45%, transparent);
  }
  .boundary-note {
    display: grid;
    gap: 4px;
    padding: 12px 14px;
    color: var(--warning);
    background: color-mix(in srgb, var(--warning) 8%, transparent);
    font-size: 11px;
  }
  .boundary-note span {
    color: var(--text-secondary);
    line-height: 1.45;
  }
  .consent-row {
    display: flex;
    gap: 9px;
    align-items: flex-start;
    padding: 12px 14px 0;
  }
  .consent-row input {
    margin-top: 2px;
  }
  .configuration-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
    padding: 12px 14px;
  }
  label {
    display: grid;
    gap: 5px;
  }
  label.wide {
    grid-column: 1 / -1;
  }
  input,
  select {
    min-width: 0;
    padding: 7px 9px;
    color: var(--text-primary);
    background: var(--bg-primary);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
  }
  .actions {
    justify-content: flex-start;
    flex-wrap: wrap;
    padding: 0 14px 12px;
  }
  button {
    padding: 7px 11px;
    color: var(--text-secondary);
    background: var(--bg-tertiary);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
  }
  button.primary {
    color: white;
    background: var(--accent);
    border-color: var(--accent);
  }
  button.danger {
    color: var(--danger);
    border-color: color-mix(in srgb, var(--danger) 50%, transparent);
  }
  button:disabled {
    cursor: not-allowed;
    opacity: 0.45;
  }
  .status-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 8px;
    padding: 12px 14px;
    border-top: 1px solid var(--border);
  }
  .status-grid div {
    display: grid;
    gap: 4px;
    padding: 9px;
    background: var(--bg-primary);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
  }
  .status-grid strong {
    overflow: hidden;
    font-size: 11px;
    text-overflow: ellipsis;
    text-transform: capitalize;
  }
  .artifact-warning,
  .error {
    padding: 10px 14px;
    color: var(--danger);
    background: color-mix(in srgb, var(--danger) 9%, transparent);
    font-size: 11px;
  }
  .goal-list {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 8px;
    padding: 12px 14px 14px;
    border-top: 1px solid var(--border);
  }
  .goal-header,
  .empty {
    grid-column: 1 / -1;
  }
  .goal {
    display: grid;
    gap: 4px;
    padding: 9px;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
  }
  .goal.focused {
    border-color: var(--accent);
    box-shadow: 0 0 0 1px color-mix(in srgb, var(--accent) 35%, transparent);
  }
  .goal code {
    color: var(--text-muted);
    font-size: 9px;
  }
  .empty {
    color: var(--text-muted);
    font-size: 11px;
  }
  @media (max-width: 900px) {
    .status-grid,
    .goal-list {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }
</style>
