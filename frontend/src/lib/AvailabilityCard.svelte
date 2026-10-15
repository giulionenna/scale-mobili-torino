<script lang="ts">
  import Icon from "./Icon.svelte";
  import { latest } from "./platform-model";
  import type { Data } from "./platform-model";
  let {
    data,
    unlocked = false,
    onlogin,
    id = "availability-details",
  }: {
    data: Data | null;
    unlocked?: boolean;
    onlogin: () => void;
    id?: string;
  } = $props();
  let expanded = $state(false);
  const stations = $derived(data?.stationCatalog || []);
  const stats = $derived.by(() => {
    const devices = data?.devices || [];
    const working =
      data?.availability?.working ??
      devices.filter((d) => latest(data!, d.id)?.status === "funzionante")
        .length;
    return {
      total: data?.availability?.total ?? devices.length,
      working,
      stopped: devices.filter((d) =>
        ["guasta", "manutenzione"].includes(latest(data!, d.id)?.status || ""),
      ).length,
      unknown: devices.filter(
        (d) =>
          !latest(data!, d.id) ||
          latest(data!, d.id)?.status === "non_verificabile",
      ).length,
    };
  });
  function percentage(count: number) {
    return stats.total ? `${Math.round((count / stats.total) * 100)}%` : "—";
  }
</script>

<article class="availability-card" class:expanded>
  <button
    class="availability-toggle"
    aria-expanded={expanded}
    aria-controls={id}
    onclick={() => (expanded = !expanded)}
  >
    <span class="availability-main">
      <span class="metric-kicker"
        ><Icon name="check" size={21} /> OSSERVATI FUNZIONANTI</span
      >
      <strong class="availability-value">{percentage(stats.working)}</strong>
      <span class="availability-caption"
        >{#if data}<b>{stats.working} su {stats.total}</b> impianti censiti{:else}Caricamento
          del censimento…{/if}</span
      >
    </span>
    <span class="availability-side">
      <span class="sample-chip"
        >M1 · {stations.length} stazioni{data?.availability?.synthetic ||
        !data?.availability
          ? " · demo"
          : ""}</span
      >
      {#if unlocked}<span class="availability-mini"
          ><b>{stats.stopped}</b> con criticità <b>{stats.unknown}</b> da verificare</span
        >{/if}
      <span class="expand-prompt"
        >{expanded ? "Chiudi il dettaglio" : "Esplora il dettaglio"}<span
          class="expand-icon"
          ><Icon name={expanded ? "close" : "plus"} size={22} /></span
        ></span
      >
    </span>
  </button>
  <div class="availability-track" aria-hidden="true">
    <span
      style:width={`${stats.total ? (stats.working / stats.total) * 100 : 0}%`}
    ></span>
  </div>
  <div {id} class="availability-details" hidden={!expanded}>
    {#if unlocked}<div class="availability-breakdown">
        <div>
          <strong>{stats.working}</strong><span
            >Funzionanti · {percentage(stats.working)}</span
          >
        </div>
        <div>
          <strong>{stats.stopped}</strong><span
            >Guasti / manutenzione · {percentage(stats.stopped)}</span
          >
        </div>
        <div>
          <strong>{stats.unknown}</strong><span
            >Da verificare / senza dati · {percentage(stats.unknown)}</span
          >
        </div>
      </div>{/if}
    <div class="availability-stations">
      {#each stations as station}
        {@const devices =
          data?.devices.filter((d) => d.station_id === station.id) || []}
        {@const working = devices.filter(
          (d) => latest(data!, d.id)?.status === "funzionante",
        ).length}
        <div>
          <span>{station.name}</span><strong
            >{working}<small> / {devices.length}</small></strong
          ><span>funzionanti</span>
        </div>
      {/each}
    </div>
    <p>
      Ultima osservazione community per ogni impianto, sul totale censito nel
      campione. Le osservazioni possono risalire a momenti diversi; gli
      intervalli non osservati restano sconosciuti.
    </p>
    {#if !unlocked}<button class="availability-login" onclick={onlogin}
        >Accedi per le altre statistiche<Icon name="arrow" size={17} /></button
      >{/if}
  </div>
</article>
