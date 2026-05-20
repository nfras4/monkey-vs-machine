<script lang="ts">
  // Light/dark toggle. data-theme on <html> is the source of truth; pre-paint
  // FOUC-prevention happens in app.html. We mirror that into Svelte state on
  // mount so the toggle reflects current theme.
  let theme = $state<"light" | "dark">("light");
  let mounted = $state(false);

  $effect(() => {
    const initial = (document.documentElement.dataset.theme as "light" | "dark") || "light";
    theme = initial;
    mounted = true;
  });

  function toggle() {
    const next = theme === "dark" ? "light" : "dark";
    theme = next;
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem("mvm-theme", next);
    } catch {
      /* private mode */
    }
    // Let charts know to re-skin
    window.dispatchEvent(new CustomEvent("mvm:theme", { detail: next }));
  }
</script>

<button
  class="theme-toggle"
  type="button"
  onclick={toggle}
  aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
  aria-pressed={theme === "dark"}
  title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
>
  {#if mounted}
    <span class="icon" aria-hidden="true">
      {#if theme === "dark"}
        <!-- sun -->
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round">
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
        </svg>
      {:else}
        <!-- moon -->
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
        </svg>
      {/if}
    </span>
    <span class="label">{theme === "dark" ? "light" : "dark"}</span>
  {:else}
    <span class="icon placeholder" aria-hidden="true"></span>
  {/if}
</button>

<style>
  .theme-toggle {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 10px;
    border: 1px solid var(--border);
    border-radius: 100px;
    background: var(--bg-card);
    color: var(--fg-muted);
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.04em;
    text-transform: lowercase;
    cursor: pointer;
    transition: color 0.15s ease, border-color 0.15s ease, background 0.15s ease;
    line-height: 1;
  }
  .theme-toggle:hover,
  .theme-toggle:focus-visible {
    color: var(--fg);
    border-color: var(--border-strong);
  }
  .icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 16px;
    height: 16px;
  }
  .icon.placeholder { width: 16px; height: 16px; }
  .label { display: inline-block; }
  @media (max-width: 520px) {
    .label { display: none; }
    .theme-toggle { padding: 6px 8px; }
  }
</style>
