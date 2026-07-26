<script lang="ts">
  import { onMount } from "svelte";
  import { _ } from "svelte-i18n";
  import { call } from "../api/daemon";

  let enabled = $state(false);
  let narrateSteps = $state(true);
  let interruptOnRisk = $state(true);
  let confirmTimeoutSeconds = $state(120);
  let loading = $state(true);
  let saving = $state(false);
  let saved = $state(false);

  onMount(loadStatus);

  async function loadStatus() {
    try {
      const result = (await call("narration_status")) as {
        enabled: boolean;
        narrate_steps: boolean;
        interrupt_on_risk: boolean;
        confirm_timeout_seconds: number;
      };
      enabled = result.enabled ?? false;
      narrateSteps = result.narrate_steps ?? true;
      interruptOnRisk = result.interrupt_on_risk ?? true;
      confirmTimeoutSeconds = result.confirm_timeout_seconds ?? 120;
    } catch {
      /* daemon unreachable -- keep last known state */
    } finally {
      loading = false;
    }
  }

  async function save() {
    saving = true;
    saved = false;
    try {
      await call("narration_config_update", {
        enabled,
        narrate_steps: narrateSteps,
        interrupt_on_risk: interruptOnRisk,
        confirm_timeout_seconds: confirmTimeoutSeconds,
      });
      saved = true;
      setTimeout(() => (saved = false), 2500);
    } finally {
      saving = false;
    }
  }
</script>

<div class="narration-panel">
  <div class="narration-header">
    <h3>{$_('settings.narration')}</h3>
    <button
      class="toggle"
      class:active={enabled}
      onclick={() => (enabled = !enabled)}
      aria-label="Toggle Live Execution Narrator"
      title="Toggle Live Execution Narrator"
    >
      <span class="toggle-knob"></span>
    </button>
  </div>

  <p class="narration-note">{$_('settings.narration_desc')}</p>

  {#if loading}
    <div class="empty">Loading...</div>
  {:else}
    <div class="setting-row">
      <div class="setting-info">
        <span class="setting-label">{$_('settings.narration_narrate_steps')}</span>
        <span class="setting-desc">{$_('settings.narration_narrate_steps_desc')}</span>
      </div>
      <button
        class="toggle toggle-sm"
        class:active={narrateSteps}
        onclick={() => (narrateSteps = !narrateSteps)}
        aria-label="Toggle step narration"
      >
        <span class="toggle-knob"></span>
      </button>
    </div>

    <div class="setting-row">
      <div class="setting-info">
        <span class="setting-label">{$_('settings.narration_interrupt_on_risk')}</span>
        <span class="setting-desc">{$_('settings.narration_interrupt_on_risk_desc')}</span>
      </div>
      <button
        class="toggle toggle-sm"
        class:active={interruptOnRisk}
        onclick={() => (interruptOnRisk = !interruptOnRisk)}
        aria-label="Toggle risk interrupts"
      >
        <span class="toggle-knob"></span>
      </button>
    </div>

    <div class="setting-row">
      <div class="setting-info">
        <span class="setting-label">{$_('settings.narration_timeout')}</span>
        <span class="setting-desc">{$_('settings.narration_timeout_desc')}</span>
      </div>
      <input
        type="number"
        class="input-sm"
        value={confirmTimeoutSeconds}
        onchange={(e) => (confirmTimeoutSeconds = Number((e.target as HTMLInputElement).value))}
        min="10"
        max="600"
        step="10"
      />
    </div>

    <div class="narration-actions">
      <button class="btn-save" onclick={save} disabled={saving}>
        {saving ? "Saving..." : saved ? "✓ Saved" : $_('settings.save')}
      </button>
    </div>
  {/if}
</div>

<style>
  .narration-panel {
    display: flex;
    flex-direction: column;
  }

  .narration-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 14px;
    background: var(--bg-tertiary);
    border-bottom: 1px solid var(--border);
  }

  h3 {
    font-size: 14px;
    font-weight: 600;
    margin: 0;
  }

  .narration-note {
    margin: 10px 14px 0;
    padding: 10px 12px;
    font-size: 11px;
    line-height: 1.4;
    color: var(--text-secondary);
    background: var(--bg-tertiary);
    border-radius: var(--radius-sm);
  }

  .empty {
    padding: 20px;
    text-align: center;
    color: var(--text-muted);
    font-size: 13px;
  }

  .setting-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding: 10px 14px;
    border-bottom: 1px solid var(--border);
  }

  .setting-info {
    display: flex;
    min-width: 0;
    flex-direction: column;
    gap: 2px;
  }

  .setting-label {
    font-size: 13px;
    font-weight: 500;
  }

  .setting-desc {
    font-size: 11px;
    color: var(--text-muted);
  }

  .toggle {
    position: relative;
    width: 40px;
    height: 22px;
    flex-shrink: 0;
    cursor: pointer;
    background: var(--bg-tertiary);
    border: 1px solid var(--border);
    border-radius: 11px;
    transition: all 0.2s;
  }

  .toggle.active {
    background: var(--accent);
    border-color: var(--accent);
  }

  .toggle-knob {
    position: absolute;
    top: 2px;
    left: 2px;
    width: 16px;
    height: 16px;
    background: white;
    border-radius: 50%;
    transition: transform 0.2s;
  }

  .toggle.active .toggle-knob {
    transform: translateX(18px);
  }

  .toggle-sm {
    transform: scale(0.8);
  }

  .input-sm {
    width: 80px;
    padding: 5px 8px;
    font-size: 13px;
    color: var(--text-primary);
    text-align: right;
    background: var(--bg-primary);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
  }

  .narration-actions {
    display: flex;
    justify-content: flex-end;
    padding: 10px 14px 12px;
  }

  .btn-save {
    padding: 5px 14px;
    font-size: 12px;
    font-weight: 600;
    color: white;
    white-space: nowrap;
    background: var(--accent);
    border-radius: var(--radius-sm);
    transition: all 0.15s;
  }

  .btn-save:hover:not(:disabled) {
    background: var(--accent-hover);
  }

  .btn-save:disabled {
    cursor: not-allowed;
    color: var(--text-secondary);
    background: var(--bg-tertiary);
    border: 1px solid var(--border);
  }
</style>
