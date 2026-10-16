<script lang="ts">
  import { onMount } from "svelte";
  import type { Data, Member, DeviceStatus } from "./platform-model";
  import { labels } from "./platform-model";
  import { getFavorites, saveFavorites, submitReport } from "./platform-client";
  import type { Favorites } from "./platform-client";
  let {
    data,
    user,
    onlogin,
    onsaved,
  }: {
    data: Data;
    user: Member | null;
    onlogin: () => void;
    onsaved: () => Promise<void>;
  } = $props();
  let favorites = $state<Favorites>({ station_ids: [], version: 0 });
  let selected = $state<string[]>([]);
  let open = $state(false),
    editing = $state(false),
    loaded = $state(false),
    busy = $state(false);
  let error = $state("");
  let answers = $state<Record<string, DeviceStatus | "">>({});
  let sent = $state<string[]>([]);
  let times = $state<Record<string, string>>({});
  const attempts: Record<string, { body: string; key: string }> = {};
  const sessionKey = "smt.favorites-checked";
  const stations = $derived(data.stationCatalog || []);
  const devices = $derived(
    data.devices.filter((d) => favorites.station_ids.includes(d.station_id)),
  );
  const names = $derived(
    stations
      .filter((s) => favorites.station_ids.includes(s.id))
      .map((s) => s.name),
  );
  function dismiss() {
    if (busy) return;
    open = false;
    if (user) sessionStorage.setItem(sessionKey, user.id);
  }
  function show(edit = false) {
    if (!user) {
      onlogin();
      return;
    }
    error = "";
    answers = {};
    times = {};
    sent = [];
    selected = [...favorites.station_ids];
    editing = edit || !favorites.station_ids.length;
    open = true;
  }
  onMount(() => {
    let mounted = true;
    if (user)
      void (async () => {
        try {
          const result = await getFavorites();
          if (!mounted) return;
          favorites = result;
          loaded = true;
          if (sessionStorage.getItem(sessionKey) !== user!.id) show();
        } catch (e) {
          if (mounted)
            error =
              e instanceof Error ? e.message : "Preferiti non disponibili.";
        }
      })();
    return () => {
      mounted = false;
    };
  });
  async function save() {
    busy = true;
    error = "";
    const body = JSON.stringify({
      station_ids: selected,
      version: favorites.version,
    });
    if (attempts.preferences?.body !== body)
      attempts.preferences = { body, key: crypto.randomUUID() };
    try {
      favorites = await saveFavorites(
        selected,
        favorites.version,
        attempts.preferences.key,
      );
      loaded = true;
      editing = false;
      if (!favorites.station_ids.length) {
        busy = false;
        dismiss();
      }
    } catch (e) {
      error = e instanceof Error ? e.message : "Salvataggio non riuscito.";
      // A second session may have changed the version. Keep the user's selection for review.
      try {
        favorites = await getFavorites();
      } catch {
        /* Retain the last confirmed version. */
      }
    } finally {
      busy = false;
    }
  }
  function localNow() {
    const now = new Date();
    return new Date(now.getTime() - now.getTimezoneOffset() * 60000)
      .toISOString()
      .slice(0, 16);
  }
  async function report(id: string) {
    const device = devices.find((d) => d.id === id);
    const status = answers[id];
    if (!device || !status || !times[id]) return;
    busy = true;
    error = "";
    const input = {
      device_id: id,
      station_id: device.station_id,
      status,
      description: "",
      observed_at: new Date(times[id]).toISOString(),
    };
    const body = JSON.stringify(input);
    if (attempts[id]?.body !== body)
      attempts[id] = { body, key: crypto.randomUUID() };
    try {
      await submitReport(input, attempts[id].key);
      sent = [...sent, id];
      await onsaved();
    } catch (e) {
      error =
        e instanceof Error ? e.message : "Invio non riuscito. Puoi riprovare.";
    } finally {
      busy = false;
    }
  }
  function focusDialog(node: HTMLElement) {
    const previous = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    node.focus();
    const keys = (e: KeyboardEvent) => {
      if (e.key === "Escape") dismiss();
      if (e.key !== "Tab") return;
      const items = [
        ...node.querySelectorAll<HTMLElement>(
          "button:not(:disabled), input:not(:disabled), select:not(:disabled)",
        ),
      ];
      if (!items.length) {
        e.preventDefault();
        return;
      }
      if (
        e.shiftKey &&
        (document.activeElement === items[0] || document.activeElement === node)
      ) {
        e.preventDefault();
        items.at(-1)?.focus();
      } else if (!e.shiftKey && document.activeElement === items.at(-1)) {
        e.preventDefault();
        items[0]?.focus();
      }
    };
    node.addEventListener("keydown", keys);
    return {
      destroy() {
        node.removeEventListener("keydown", keys);
        document.body.style.overflow = overflow;
        if (previous?.isConnected) previous.focus();
      },
    };
  }
</script>

<section class="favorites-panel panel" aria-label="Stazioni preferite">
  <div>
    <p class="eyebrow">IL TUO PERCORSO</p>
    <h2>Le tue stazioni preferite</h2>
    <p>
      {names.length
        ? names.join(" · ")
        : "Scegli le stazioni che usi: al prossimo accesso ti chiederemo come stanno i loro impianti."}
    </p>
  </div>
  <div class="favorites-actions">
    {#if user && favorites.station_ids.length}<button
        class="button navy"
        disabled={busy || !loaded}
        onclick={() => show()}>Verifica i preferiti</button
      >{/if}
    <button
      class="button outline"
      disabled={busy || (!!user && !loaded && !error)}
      onclick={() => {
        if (user && !loaded) {
          location.reload();
        } else show(true);
      }}
      >{favorites.station_ids.length
        ? "Modifica preferiti"
        : "Scegli le stazioni"}</button
    >
  </div>
  {#if error && !open}<p role="alert">{error}</p>{/if}
</section>
{#if open && user}
  <div class="modal-backdrop" role="presentation">
    <div
      class="dialog favorites-dialog"
      role="dialog"
      aria-modal="true"
      aria-labelledby="favorites-title"
      tabindex="-1"
      use:focusDialog
    >
      <p class="eyebrow">{editing ? "IL TUO PERCORSO" : "BENTORNATO"}</p>
      <h2 id="favorites-title">
        {editing
          ? "Quali stazioni usi di più?"
          : "Funzionano gli impianti delle tue stazioni?"}
      </h2>
      {#if editing}
        <p>
          Seleziona le tue stazioni preferite. Sono private e salvate nel tuo
          account, anche su altri dispositivi.
        </p>
        <div class="favorite-options">
          {#each stations as station}<label
              ><input
                type="checkbox"
                value={station.id}
                bind:group={selected}
                disabled={busy}
              /><span>{station.name}</span></label
            >{/each}
        </div>
        <button class="button yellow" disabled={busy} onclick={save}
          >Salva preferiti</button
        >
      {:else}
        <p>
          Segnala solo ciò che hai osservato. Scegli uno stato e il momento per
          ciascun impianto, poi conferma l’invio. Puoi saltare quelli che non
          hai visto.
        </p>
        <div class="favorite-checks">
          {#each devices as device}
            <article class="favorite-device">
              <p class="eyebrow">
                {stations.find((s) => s.id === device.station_id)?.name}
              </p>
              <h3>{device.name}</h3>
              <p>{device.location}</p>
              {#if sent.includes(device.id)}<p role="status">
                  ✓ Segnalazione salvata
                </p>
              {:else}
                <label
                  >Stato osservato<select
                    aria-label={`Stato di ${device.name}`}
                    value={answers[device.id] || ""}
                    disabled={busy}
                    onchange={(e) => {
                      answers[device.id] = e.currentTarget
                        .value as DeviceStatus;
                      times[device.id] ||= localNow();
                    }}
                    ><option value="">Non l’ho osservato</option
                    >{#each Object.entries(labels) as [value, label]}<option
                        {value}>{label}</option
                      >{/each}</select
                  ></label
                >
                {#if answers[device.id]}<label
                    >Quando l’hai osservato?<input
                      type="datetime-local"
                      bind:value={times[device.id]}
                      disabled={busy}
                    /></label
                  >
                  <button
                    class="button navy"
                    disabled={busy || !times[device.id]}
                    onclick={() => report(device.id)}>Invia osservazione</button
                  >{/if}
              {/if}
            </article>
          {/each}
          {#if !devices.length}<p>
              Nessun impianto disponibile nel censimento per queste stazioni.
            </p>{/if}
        </div>
        <button
          class="text-button"
          disabled={busy}
          onclick={() => {
            selected = [...favorites.station_ids];
            editing = true;
          }}>Modifica le stazioni preferite</button
        >
      {/if}
      {#if error}<p role="alert">{error}</p>{/if}
      <div class="favorites-footer">
        <button class="button outline" disabled={busy} onclick={dismiss}
          >{sent.length ? "Fatto, continua" : "Salta e continua"}</button
        ><small>Nessun invio automatico. I preferiti restano salvati.</small>
      </div>
    </div>
  </div>
{/if}
