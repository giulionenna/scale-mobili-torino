<script lang="ts">
  import type { Snippet } from "svelte";
  import Icon from "./Icon.svelte";
  let {
    unlocked,
    kind,
    onlogin,
    children,
  }: {
    unlocked: boolean;
    kind: "alignment" | "incidents" | "comparison";
    onlogin: () => void;
    children: Snippet;
  } = $props();
  const title = $derived(
    kind === "alignment"
      ? "Quanto è allineato GTT?"
      : kind === "incidents"
        ? "Nuovi fermi e streak"
        : "GTT e community",
  );
</script>

{#if unlocked}
  {@render children()}
{:else}
  <section
    class="locked-statistic"
    class:locked-incidents={kind === "incidents"}
    class:locked-comparison={kind === "comparison"}
    aria-label={`${title}: accesso richiesto`}
  >
    <div class="locked-preview" aria-hidden="true" inert>
      <div class="locked-preview-heading">
        <span class="metric-kicker">{title}</span><Icon
          name={kind === "incidents" ? "warning" : "compare"}
          size={28}
        />
      </div>
      {#if kind === "alignment"}<div class="locked-preview-metric">••%</div>
        <div class="locked-preview-lines"><span></span><span></span></div>
      {:else}<div class="locked-preview-rows">
          {#each [1, 2, 3] as row}<div>
              <span></span><span></span><b>••</b>
            </div>{/each}
        </div>{/if}
    </div>
    <div class="statistic-unlock">
      <span class="unlock-symbol"><Icon name="shield" size={22} /></span>
      <h2>{title}</h2>
      <p>
        Accedi per vedere {kind === "alignment"
          ? "l’allineamento tra le fonti."
          : kind === "incidents"
            ? "i nuovi fermi e le segnalazioni consecutive."
            : "il confronto impianto per impianto."}
      </p>
      <button class="button navy small" onclick={onlogin}
        >Accedi e sblocca<Icon name="arrow" size={17} /></button
      >
    </div>
  </section>
{/if}
