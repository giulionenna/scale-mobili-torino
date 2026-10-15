<script lang="ts">
  import { onMount, untrack } from "svelte";
  import Icon from "./Icon.svelte";
  import AvailabilityCard from "./AvailabilityCard.svelte";
  import PrivatePhoto from "./PrivatePhoto.svelte";
  import { ApiError } from "./api";
  import StatisticGate from "./StatisticGate.svelte";
  import { overviewFor } from "./platform-overview";
  import {
    load,
    member,
    signIn,
    signOut,
    stationName as resolveStationName,
    gttSource,
    submitReport,
    submitProposal,
    reviewProposal,
    reviewPhoto,
    preparePhoto,
    browserDemo,
    developmentLogin,
    backendMode,
    moreReports,
  } from "./platform-client";
  import {
    latest,
    deviceName,
    labels,
    kindLabels,
    age,
    date,
  } from "./platform-model";
  import type {
    Data,
    Member,
    View,
    Device,
    DeviceStatus,
    Kind,
    Photo,
  } from "./platform-model";
  let { initialView = "landing" }: { initialView?: View } = $props();
  let view = $state<View>(untrack(() => initialView)),
    data = $state<Data | null>(null),
    user = $state<Member | null>(null);
  let ready = $state(false),
    loginOpen = $state(false),
    desiredView: View = "home";
  let error = $state(""),
    notice = $state(""),
    search = $state(""),
    filter = $state("all"),
    streamFilter = $state("all");
  let selectedStation = $state(""),
    selectedDevice = $state(""),
    selectedStatus = $state<DeviceStatus>("guasta");
  let reportDescription = $state(""),
    proposalKind = $state<Kind>("scala_mobile"),
    proposalName = $state(""),
    proposalLocation = $state("");
  let photo = $state<Photo | undefined>(),
    photoInput = $state<HTMLInputElement>(),
    busy = $state(false),
    requestId = "";
  let moderationTab = $state("devices"),
    detail = $state<Device | null>(null),
    mobileMenu = $state(false);
  let reviewReasons = $state<Record<string, string>>({});
  let reviewKeys: Record<string, string> = {};
  const stations = $derived(data?.stationCatalog || []);
  function stationName(id: string) {
    return resolveStationName(data, id);
  }
  let incidentTab = $state<"new" | "streak">("new");
  const paths: Record<View, string> = {
    landing: "/",
    home: "/home/",
    report: "/segnala/",
    proposal: "/proponi/",
    moderation: "/moderazione/",
  };
  function needsLogin(next: View) {
    return next === "report" || next === "proposal" || next === "moderation";
  }
  function requestLogin(next: View = "home") {
    desiredView = next;
    loginOpen = true;
    mobileMenu = false;
  }
  onMount(() => {
    let mounted = true;
    requestId = crypto.randomUUID();
    void (async () => {
      try {
        const identity = await member();
        const loaded = await load();
        if (!mounted) return;
        user = identity;
        data = loaded;
        if (user && view === "moderation" && user.role !== "moderator") {
          view = "home";
          error = "La revisione è riservata al moderatore.";
          window.history.replaceState({}, "", paths.home);
        }
        if (!user && needsLogin(view)) {
          desiredView = view;
          view = "home";
          window.history.replaceState({}, "", paths.home);
          loginOpen = true;
        }
      } catch (e) {
        showError(e);
      } finally {
        if (mounted) ready = true;
      }
    })();
    const pop = () => {
      const next = (Object.entries(paths).find(
        ([, p]) => p === window.location.pathname,
      )?.[0] || "landing") as View;
      if (!user && needsLogin(next)) {
        desiredView = next;
        view = "home";
        window.history.replaceState({}, "", paths.home);
        loginOpen = true;
      } else if (next === "moderation" && user?.role !== "moderator") {
        view = "home";
        window.history.replaceState({}, "", paths.home);
        error = "La revisione è riservata al moderatore.";
      } else view = next;
    };
    window.addEventListener("popstate", pop);
    return () => {
      mounted = false;
      window.removeEventListener("popstate", pop);
    };
  });
  const totalDevices = $derived(data?.devices.length || 0);
  const pending = $derived(
    data?.proposals.filter((p) => p.status === "pending") || [],
  );
  const photoQueue = $derived(
    data?.photoQueue ??
      (data
        ? [
            ...data.reports
              .filter((r) => r.photo?.status === "pending")
              .map((r) => ({
                id: r.id,
                origin: "report" as const,
                photo: r.photo!,
                name: deviceName(data!, r.device_id),
                station_id: r.station_id,
              })),
            ...data.proposals
              .filter(
                (p) => p.photo?.status === "pending" && p.status === "approved",
              )
              .map((p) => ({
                id: p.id,
                origin: "proposal" as const,
                photo: p.photo!,
                name: p.name,
                station_id: p.station_id,
              })),
          ]
        : []),
  );
  const visibleStations = $derived(
    stations.filter(
      (s) =>
        s.name.toLowerCase().includes(search.toLowerCase()) &&
        (filter === "all" ||
          data?.devices.some(
            (d) =>
              d.station_id === s.id &&
              (filter === "issues"
                ? ["guasta", "manutenzione"].includes(
                    latest(data!, d.id)?.status || "",
                  )
                : filter === "lift"
                  ? d.kind === "ascensore"
                  : d.kind === "scala_mobile"),
          )),
    ),
  );
  const feed = $derived(
    data?.reports
      .filter((r) => streamFilter === "all" || r.station_id === streamFilter)
      .toSorted((a, b) => b.recorded_at.localeCompare(a.recorded_at)) || [],
  );
  const overview = $derived(overviewFor(data));
  const comparable = $derived(overview.comparable);
  const differences = $derived(overview.differences);
  const visibleIncidents = $derived(
    incidentTab === "new" ? overview.newStops : overview.streaks,
  );
  const formDevices = $derived(
    data?.devices.filter((d) => d.station_id === selectedStation) || [],
  );
  function comparisonObservation(id: string) {
    const row = data?.statistics?.alignment.items.find(
      (item) => item.device_id === id,
    );
    return row
      ? { status: row.community_status, observed_at: row.observed_at }
      : latest(data!, id);
  }
  function showError(e: unknown) {
    if (e instanceof ApiError && e.status === 401) {
      leave();
      loginOpen = true;
    }
    error = e instanceof Error ? e.message : "Operazione non riuscita.";
  }
  function go(next: View) {
    mobileMenu = false;
    error = "";
    detail = null;
    if (!user && needsLogin(next)) {
      requestLogin(next);
      return;
    }
    if (next === "moderation" && user?.role !== "moderator") {
      error = "La revisione è riservata al moderatore.";
      return;
    }
    view = next;
    window.history.pushState({}, "", paths[next]);
    window.scrollTo({ top: 0, behavior: "instant" });
    if (["report", "proposal"].includes(next)) {
      requestId = crypto.randomUUID();
      reportDescription = "";
      photo = undefined;
    }
  }
  async function enter(role: "citizen" | "moderator") {
    busy = true;
    error = "";
    try {
      const identity = await signIn(role, paths[desiredView]);
      if (!identity) return; // Cognito redirects to its authorization endpoint.
      user = identity;
      data = await load();
      loginOpen = false;
      const destination =
        desiredView === "moderation" && user.role !== "moderator"
          ? "home"
          : desiredView;
      if (destination !== view) go(destination);
    } catch (e) {
      showError(e);
    } finally {
      busy = false;
    }
  }
  async function refresh() {
    busy = true;
    error = "";
    try {
      const identity = await member();
      if (user && !identity) leave();
      user = identity;
      data = await load();
    } catch (e) {
      showError(e);
    } finally {
      busy = false;
    }
  }
  async function refreshAfterSave() {
    try {
      data = await load();
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        leave();
        notice = "Contributo salvato. Accedi nuovamente per continuare.";
      } else {
        notice +=
          " Il salvataggio è riuscito; aggiorna la panoramica per rileggere i dati.";
      }
    }
  }
  async function loadMore() {
    if (!data) return;
    busy = true;
    try {
      data = await moreReports(data);
    } catch (e) {
      showError(e);
    } finally {
      busy = false;
    }
  }
  function leave() {
    signOut();
    user = null;
    if (data)
      data = {
        ...data,
        statistics: undefined,
        statisticsError: undefined,
        proposals: [],
        photoQueue: undefined,
        officialExamples: {},
        audit: [],
      };
    detail = null;
    mobileMenu = false;
    loginOpen = false;
    if (view !== "landing") {
      view = "home";
      window.history.replaceState({}, "", paths.home);
    }
    notice = "";
    error = "";
  }
  function reportFor(device?: Device) {
    selectedStation = device?.station_id || "";
    selectedDevice = device?.id || "";
    go("report");
  }
  async function pickPhoto(e: Event) {
    error = "";
    photo = undefined;
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    busy = true;
    try {
      photo = await preparePhoto(file);
    } catch (e) {
      showError(e);
      input.value = "";
    } finally {
      busy = false;
    }
  }
  function removePhoto() {
    photo = undefined;
    if (photoInput) photoInput.value = "";
  }
  async function sendReport(e: SubmitEvent) {
    e.preventDefault();
    busy = true;
    error = "";
    try {
      await submitReport(
        {
          station_id: selectedStation,
          device_id: selectedDevice,
          status: selectedStatus,
          description: reportDescription,
          photo,
        },
        requestId,
      );
      notice = photo
        ? "Segnalazione inviata. La foto rimane privata fino all’approvazione."
        : "Grazie! La tua segnalazione è stata aggiunta allo stream.";
      go("home");
      await refreshAfterSave();
    } catch (e) {
      showError(e);
    } finally {
      busy = false;
    }
  }
  async function sendProposal(e: SubmitEvent) {
    e.preventDefault();
    busy = true;
    error = "";
    try {
      await submitProposal(
        {
          station_id: selectedStation,
          kind: proposalKind,
          name: proposalName,
          location: proposalLocation,
          description: reportDescription,
          photo,
        },
        requestId,
      );
      notice =
        "Proposta inviata al moderatore. L’impianto comparirà nel censimento dopo l’approvazione.";
      proposalName = "";
      proposalLocation = "";
      go("home");
      await refreshAfterSave();
    } catch (e) {
      showError(e);
    } finally {
      busy = false;
    }
  }
  async function decide(id: string, decision: "approved" | "rejected") {
    const item = data?.proposals.find((p) => p.id === id);
    if (!item) return;
    busy = true;
    error = "";
    const key = `proposal:${id}:${decision}:${item.version || 1}`;
    reviewKeys[key] ||= crypto.randomUUID();
    try {
      await reviewProposal(
        id,
        decision,
        item.version || 1,
        reviewReasons[id] || "",
        reviewKeys[key],
      );
      notice =
        decision === "approved"
          ? "Impianto approvato e aggiunto al censimento."
          : "Proposta respinta. La decisione è conservata.";
      await refreshAfterSave();
    } catch (e) {
      showError(e);
    } finally {
      busy = false;
    }
  }
  async function decidePhoto(
    id: string,
    origin: "report" | "proposal",
    decision: "approved" | "rejected",
  ) {
    const item = photoQueue.find((p) => p.id === id);
    if (!item) return;
    busy = true;
    error = "";
    const key = `photo:${id}:${decision}:${item.photo.version || 1}`;
    reviewKeys[key] ||= crypto.randomUUID();
    try {
      await reviewPhoto(
        id,
        origin,
        decision,
        item.photo.version || 1,
        reviewReasons[id] || "",
        reviewKeys[key],
      );
      notice =
        decision === "approved"
          ? "Foto approvata. Ora è pubblica."
          : "Foto respinta: rimane privata.";
      await refreshAfterSave();
    } catch (e) {
      showError(e);
    } finally {
      busy = false;
    }
  }

  function focusDialog(node: HTMLElement) {
    const previous = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const elements = () => [
      ...node.querySelectorAll<HTMLElement>(
        "button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled)",
      ),
    ];
    const focus = requestAnimationFrame(() => elements()[0]?.focus());
    const key = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        loginOpen = false;
        detail = null;
        return;
      }
      if (event.key !== "Tab") return;
      const items = elements();
      if (event.shiftKey && document.activeElement === items[0]) {
        event.preventDefault();
        items.at(-1)?.focus();
      } else if (!event.shiftKey && document.activeElement === items.at(-1)) {
        event.preventDefault();
        items[0]?.focus();
      }
    };
    window.addEventListener("keydown", key);
    return {
      destroy() {
        cancelAnimationFrame(focus);
        window.removeEventListener("keydown", key);
        document.body.style.overflow = overflow;
        if (previous?.isConnected) previous.focus();
      },
    };
  }
</script>

<svelte:head
  ><title
    >{view === "landing"
      ? "Scale Mobili Torino · La metro, insieme"
      : view === "home"
        ? "Panoramica · Scale Mobili Torino"
        : view === "report"
          ? "Nuova segnalazione"
          : view === "proposal"
            ? "Proponi un impianto"
            : "Moderazione"}</title
  ><meta
    name="description"
    content="Scale mobili e ascensori della metro di Torino: osservazioni condivise, fonti ufficiali e un censimento costruito insieme."
  /><meta name="robots" content="noindex,nofollow" /></svelte:head
>

<header class="topbar" class:landing={view === "landing"}>
  <div class="nav-inner">
    <a
      class="brand"
      href="/"
      onclick={(e) => {
        e.preventDefault();
        go("landing");
      }}
      ><span class="brand-symbol"><Icon name="stairs" size={25} /></span><span
        >Scale Mobili <strong>Torino</strong><small
          >UNA METRO PIÙ ACCESSIBILE</small
        ></span
      ></a
    >
    {#if view === "landing"}<nav
        class="landing-nav"
        aria-label="Navigazione principale"
      >
        <a href="#come-funziona">Come funziona</a><a href="#insieme"
          >Il progetto</a
        >
      </nav>
      <button
        class="button navy small"
        onclick={() => (user ? go("home") : requestLogin())}
        >{user ? "Vai alla home" : "Accedi"}<Icon
          name="arrow"
          size={16}
        /></button
      >
    {:else}<nav
        class:open={mobileMenu}
        class="app-nav"
        aria-label="Navigazione principale"
      >
        <button class:active={view === "home"} onclick={() => go("home")}
          ><Icon name="chart" size={17} />Panoramica</button
        ><button
          class:active={view === "proposal"}
          onclick={() => go("proposal")}
          ><Icon name="plus" size={17} />Proponi un impianto</button
        >{#if user?.role === "moderator"}<button
            class:active={view === "moderation"}
            onclick={() => go("moderation")}
            ><Icon name="shield" size={17} />Moderazione {#if pending.length + photoQueue.length}<span
                class="nav-count">{pending.length + photoQueue.length}</span
              >{/if}</button
          >{/if}
      </nav>
      {#if user}<div class="account">
          <span class="avatar"
            ><Icon
              name={user?.role === "moderator" ? "shield" : "user"}
              size={17}
            /></span
          ><span
            >{user?.name}<small
              >{browserDemo
                ? "Accesso simulato"
                : developmentLogin()
                  ? "Accesso di prova"
                  : "Account verificato"}</small
            ></span
          ><button class="icon-button" aria-label="Esci" onclick={leave}
            ><Icon name="logout" size={17} /></button
          >
        </div>
      {:else}<button
          class="button navy small guest-login"
          onclick={() => requestLogin()}
          >Accedi<Icon name="arrow" size={16} /></button
        >{/if}
      <button
        class="icon-button menu-button"
        aria-label="Menu"
        onclick={() => (mobileMenu = !mobileMenu)}><Icon name="menu" /></button
      >{/if}
  </div>
</header>

{#if error}<div class="app-main">
    <div class="toast error" role="alert">
      {error}<button class="text-button" onclick={refresh} disabled={busy}
        >Riprova</button
      >
    </div>
  </div>{/if}
{#if !ready}<p class="app-main" role="status">
    Caricamento della piattaforma…
  </p>{/if}
{#if view === "landing"}<main class="landing-main">
    <section class="landing-hero">
      <div class="hero-copy">
        <span class="eyebrow"
          ><span class="tiny-dot"></span>LA METRO DI TORINO, VISTA DA CHI LA USA</span
        >
        <h1>Piccoli gradini.<br /><span>Grandi differenze.</span></h1>
        <p class="hero-lead">
          Una scala mobile ferma o un ascensore fuori servizio cambiano un
          viaggio. Condividiamo quello che vediamo, per rendere più semplice il
          percorso di tutti.
        </p>
        <div class="hero-actions">
          <button class="button yellow" onclick={() => go("home")}
            >Esplora la panoramica<Icon name="arrow" size={19} /></button
          ><a href="#come-funziona" class="quiet-link"
            >Come funziona<Icon name="arrow" size={16} /></a
          >
        </div>
        <p class="hero-footnote">
          <Icon name="shield" size={15} />Un progetto civico indipendente.
          Aperto ai contributi di tutti.
        </p>
      </div>
      <div class="landing-availability">
        <AvailabilityCard
          {data}
          unlocked={!!user}
          onlogin={() => requestLogin()}
          id="landing-availability-details"
        />
        <p class="landing-availability-note">
          <Icon name="clock" size={16} /> Ultima osservazione community · {browserDemo ||
          data?.availability?.synthetic
            ? "campione dimostrativo"
            : "censimento disponibile"}
        </p>
        <p class="landing-open-note">
          La panoramica è aperta a tutti. Accedi per il confronto GTT e le altre
          statistiche.
        </p>
      </div>
    </section>
    <div class="landing-strip">
      <span><Icon name="stairs" />Scale mobili</span><span
        ><Icon name="lift" />Ascensori</span
      ><span><Icon name="compare" />Fonti a confronto</span><span
        ><Icon name="user" />Una community, tanti percorsi</span
      >
    </div>
    <section class="how-section" id="come-funziona">
      <div class="section-intro">
        <p class="eyebrow">POCHI PASSI, UN AIUTO CONCRETO</p>
        <h2>Come funziona</h2>
        <p>
          La città diventa più accessibile quando le informazioni circolano.
        </p>
      </div>
      <div class="how-grid">
        <article>
          <span class="step-number">01</span>
          <div class="feature-icon"><Icon name="search" size={26} /></div>
          <h3>Guarda prima di partire</h3>
          <p>
            Trova gli impianti delle stazioni e consulta le osservazioni più
            recenti, con fonte e momento della verifica.
          </p>
        </article>
        <article>
          <span class="step-number">02</span>
          <div class="feature-icon"><Icon name="plus" size={26} /></div>
          <h3>Condividi ciò che vedi</h3>
          <p>
            Accedi, scegli la stazione e l’impianto. Indica lo stato e, se vuoi,
            aggiungi una foto o una descrizione.
          </p>
        </article>
        <article>
          <span class="step-number">03</span>
          <div class="feature-icon"><Icon name="compare" size={26} /></div>
          <h3>Mettiamo le fonti a confronto</h3>
          <p>
            Le comunicazioni GTT e le segnalazioni restano distinguibili.
            Differenze e informazioni mancanti sono esplicite.
          </p>
        </article>
      </div>
    </section>
    <section class="together" id="insieme">
      <div>
        <span class="eyebrow">COSTRUIAMOLO INSIEME</span>
        <h2>Ogni impianto ha una storia.<br />Aiutaci a renderla visibile.</h2>
        <p>
          Non trovi una scala mobile o un ascensore? Proponilo al censimento. Il
          moderatore lo verificherà prima di pubblicarlo.
        </p>
        <button class="button navy" onclick={() => go("proposal")}
          >Proponi un impianto<Icon name="arrow" size={18} /></button
        >
      </div>
      <div class="together-symbol">
        <Icon name="lift" size={68} /><span>+</span><Icon
          name="stairs"
          size={68}
        />
      </div>
    </section>
    <div class="landing-demo-note">
      <Icon name="warning" size={17} />
      <p>
        {browserDemo
          ? "Stai esplorando un prototipo: impianti, stati e segnalazioni sono dimostrativi. L’accesso alla piattaforma è simulato."
          : data?.availability?.synthetic
            ? "Ambiente di sviluppo con impianti fittizi: i contributi sono salvati nel backend."
            : "Progetto indipendente: consulta fonte e momento di ogni osservazione."}
      </p>
    </div>
  </main>
{:else if ready && data && (user || view === "home")}<main class="app-main">
    <div class="demo-ribbon">
      <span><span class="tiny-dot"></span>ANTEPRIMA INTERATTIVA</span>
      <p>
        {browserDemo
          ? "Impianti e segnalazioni di esempio · dati temporanei di questa sessione"
          : backendMode() === "demo"
            ? "Dati di prova salvati nel backend in memoria"
            : data.availability?.synthetic
              ? "Censimento fittizio · contributi persistenti nel backend di sviluppo"
              : "Censimento e osservazioni della community"}
      </p>
    </div>
    {#if notice}<div class="toast success" role="status">
        <Icon name="check" size={18} /><span>{notice}</span><button
          class="icon-button"
          aria-label="Chiudi messaggio"
          onclick={() => (notice = "")}><Icon name="close" size={17} /></button
        >
      </div>{/if}
    {#if view === "home"}
      <section class="dashboard-heading">
        <div>
          <p class="eyebrow">BENVENUTO NELLA COMMUNITY</p>
          <h1>La metro, <span>un passo alla volta.</span></h1>
          <p>
            Scale mobili e ascensori: una panoramica condivisa, fonti sempre
            distinguibili.
          </p>
        </div>
        <button class="button yellow report-cta" onclick={() => reportFor()}
          ><Icon name="plus" size={21} />Invia una segnalazione</button
        >
        <button class="text-button" onclick={refresh} disabled={busy}
          >Aggiorna panoramica</button
        >
      </section>
      {#if user && data.statisticsError}<p role="status">
          {data.statisticsError}
        </p>{/if}
      {#if user && data.statistics && (data.statistics.stale || data.statistics.pending_recalculation)}<p
          role="status"
        >
          Statistiche in aggiornamento · ultimo calcolo {date(
            data.statistics.generated_at,
          )}
        </p>{/if}
      <section class="overview-stack" aria-label="Statistiche della community">
        <AvailabilityCard
          {data}
          unlocked={!!user}
          onlogin={() => requestLogin()}
        />

        <StatisticGate
          unlocked={!!user}
          kind="alignment"
          onlogin={() => requestLogin()}
        >
          <article
            class="alignment-card"
            aria-label="Allineamento GTT e community"
          >
            <div class="alignment-number">
              <span class="metric-kicker">STESSO STATO NELLE DUE FONTI</span
              ><strong>{overview.alignment}</strong><span
                >{overview.aligned} su {comparable.length} confrontabili</span
              >
            </div>
            <div class="alignment-copy">
              <div class="alignment-heading">
                <h2>Quanto è allineato GTT?</h2>
                <span class="demo-label"
                  >{browserDemo ? "Confronto demo" : "Fonti verificate"}</span
                >
              </div>
              <p>
                GTT e ultima osservazione della community, impianto per
                impianto.
              </p>
              <div class="alignment-counts">
                <span><b>{differences.length}</b> differenze</span><span
                  ><b>{totalDevices - comparable.length}</b> senza confronto</span
                >
              </div>
              <small
                >Stati identici / impianti con entrambe le fonti verificabili.
                {browserDemo
                  ? "Gli esempi GTT sono fittizi."
                  : "Il confronto non comprende gli impianti privi di evidenze."}</small
              >
              <a href="#comparison-detail" class="text-button"
                >Vedi il confronto<Icon name="arrow" size={17} /></a
              >
            </div>
          </article>
        </StatisticGate>
        <StatisticGate
          unlocked={!!user}
          kind="incidents"
          onlogin={() => requestLogin()}
        >
          <section
            class="incident-banner"
            aria-label="Nuovi fermi e sequenze di fermo"
          >
            <div class="incident-heading">
              <div class="incident-title">
                <span class="incident-symbol"
                  ><Icon name="warning" size={24} /></span
                >
                <div>
                  <span class="metric-kicker">DA TENERE D’OCCHIO</span>
                  <h2>Gli ultimi fermi segnalati</h2>
                </div>
              </div>
              <div
                class="incident-switch"
                role="group"
                aria-label="Tipo di fermo"
              >
                <button
                  class:active={incidentTab === "new"}
                  aria-pressed={incidentTab === "new"}
                  onclick={() => (incidentTab = "new")}
                  >Nuovi fermi <b>{overview.newStops.length}</b></button
                >
                <button
                  class:active={incidentTab === "streak"}
                  aria-pressed={incidentTab === "streak"}
                  onclick={() => (incidentTab = "streak")}
                  >Streak <b>{overview.streaks.length}</b></button
                >
              </div>
            </div>
            <p class="incident-context">
              {incidentTab === "new"
                ? "Prima osservazione di fermo nelle ultime 24 ore, con criticità ancora segnalata."
                : "Almeno due osservazioni consecutive di guasto o manutenzione, senza un ritorno al funzionamento segnalato."}
            </p>
            <div class="incident-list" aria-live="polite">
              {#each visibleIncidents as incident}
                <button
                  class="incident-row"
                  onclick={() => (detail = incident.device)}
                >
                  <Icon
                    name={incident.device.kind === "ascensore"
                      ? "lift"
                      : "stairs"}
                    size={23}
                  />
                  <span class="incident-device"
                    ><strong>{stationName(incident.device.station_id)}</strong
                    ><span>{incident.device.name}</span></span
                  >
                  <span class="incident-evidence"
                    ><b
                      >{incidentTab === "streak"
                        ? `${incident.count} segnalazioni consecutive`
                        : incident.firstKnown
                          ? "Primo fermo osservato"
                          : "Nuovo fermo osservato"}</b
                    ><span
                      >{incidentTab === "streak"
                        ? `Ultima osservazione ${age(incident.latest.observed_at)}`
                        : age(incident.first.observed_at)}</span
                    ></span
                  >
                  <span class="incident-status"
                    >{labels[incident.latest.status]}</span
                  ><Icon name="arrow" size={18} />
                </button>
              {:else}
                <div class="incident-empty">
                  <Icon name="check" size={21} /><span
                    >{incidentTab === "new"
                      ? "Nessun nuovo fermo osservato nelle ultime 24 ore."
                      : "Nessuna sequenza ripetuta di fermo nelle osservazioni disponibili."}</span
                  >
                </div>
              {/each}
            </div>
            <p class="incident-footnote">
              Osservazioni disponibili · una sequenza di segnalazioni non prova
              un guasto continuo tra le osservazioni.
            </p>
          </section>
        </StatisticGate>
      </section>
      <div class="dashboard-grid">
        <section class="panel stations-panel">
          <div class="panel-heading">
            <div>
              <p class="eyebrow">IL CENSIMENTO</p>
              <h2>Le stazioni</h2>
            </div>
            <span class="line-chip">M1 · Torino</span>
          </div>
          <div class="station-tools">
            <label class="search-box"
              ><Icon name="search" size={18} /><input
                aria-label="Cerca una stazione"
                placeholder="Cerca una stazione…"
                bind:value={search}
              /></label
            ><select aria-label="Filtra gli impianti" bind:value={filter}
              ><option value="all">Tutti gli impianti</option><option
                value="issues">Con criticità</option
              ><option value="stairs">Scale mobili</option><option value="lift"
                >Ascensori</option
              ></select
            >
          </div>
          <div class="station-grid">
            {#each visibleStations as station}<article class="station-card">
                <div class="station-heading">
                  <span class="station-pin"><Icon name="pin" size={18} /></span>
                  <div>
                    <h3>{station.name}</h3>
                    <small
                      >{data.devices.filter((d) => d.station_id === station.id)
                        .length} impianti{browserDemo ||
                      data.availability?.synthetic
                        ? " · esempio"
                        : ""}</small
                    >
                  </div>
                  <span class="station-line">M1</span>
                </div>
                <div class="device-list">
                  {#each data.devices.filter((d) => d.station_id === station.id && (filter === "lift" ? d.kind === "ascensore" : filter === "stairs" ? d.kind === "scala_mobile" : true)) as device}{@const report =
                      latest(data, device.id)}<button
                      class="device-row"
                      onclick={() => (detail = device)}
                      ><Icon
                        name={device.kind === "ascensore" ? "lift" : "stairs"}
                        size={17}
                      /><span>{device.name}</span><span
                        class:unknown={!report ||
                          report.status === "non_verificabile"}
                        class:broken={report?.status === "guasta"}
                        class:maintenance={report?.status === "manutenzione"}
                        class:functioning={report?.status === "funzionante"}
                        class="status compact"
                        ><span></span>{report
                          ? labels[report.status]
                          : "Senza dati"}</span
                      ></button
                    >{/each}
                </div>
                <button
                  class="station-bottom"
                  onclick={() => {
                    selectedStation = station.id;
                    selectedDevice = "";
                    go("report");
                  }}
                  >Segnala in questa stazione<Icon
                    name="arrow"
                    size={15}
                  /></button
                >
              </article>{/each}
            {#if !visibleStations.length}<div class="empty-state">
                <Icon name="search" size={28} />
                <h3>Nessuna stazione trovata</h3>
                <p>Prova un altro nome o modifica il filtro.</p>
              </div>{/if}
          </div>
          <div class="inventory-footer">
            <span>Il censimento cresce con i tuoi contributi.</span><button
              class="text-button"
              onclick={() => go("proposal")}
              >Manca un impianto?<Icon name="plus" size={15} /></button
            >
          </div>
        </section>
        <StatisticGate
          unlocked={!!user}
          kind="comparison"
          onlogin={() => requestLogin()}
        >
          <aside class="panel comparison-panel" id="comparison-detail">
            <div class="panel-heading">
              <div>
                <p class="eyebrow">DUE FONTI, PIÙ CONTESTO</p>
                <h2>GTT e community</h2>
              </div>
              <span class="compare-icon"><Icon name="compare" size={23} /></span
              >
            </div>
            <div class="comparison-banner">
              <strong>{differences.length} differenze</strong><span
                >{browserDemo
                  ? "nel confronto dimostrativo"
                  : "tra le fonti disponibili"}</span
              >
            </div>
            <p class="comparison-explanation">
              Cosa indica la fonte ufficiale e cosa è stato osservato? Ecco come
              mostriamo le differenze.
            </p>
            <div class="comparison-list">
              {#each comparable as device}{@const observation =
                  comparisonObservation(device.id)!}
                <article>
                  <h3>
                    {stationName(device.station_id)}<small
                      >{device.name}{browserDemo ? " · esempio" : ""}</small
                    >
                  </h3>
                  <div class="comparison-source">
                    <span
                      >GTT {#if browserDemo}<small>esempio</small>{/if}</span
                    ><strong>{labels[data.officialExamples[device.id]]}</strong>
                  </div>
                  <div class="comparison-source">
                    <span>Community</span><strong
                      class:discrepancy={observation.status !==
                        data.officialExamples[device.id]}
                      >{labels[observation.status]}</strong
                    >
                  </div>
                  <small
                    >Community osservata il {date(
                      observation.observed_at,
                    )}</small
                  >
                </article>{/each}
            </div>
            <div class="source-warning">
              <Icon name="warning" size={15} />
              <p>
                {browserDemo
                  ? "Nessun report GTT è stato acquisito in questa demo."
                  : "Il confronto usa soltanto interpretazioni di fonti archiviate e verificate."}
                L’assenza di un impianto da un report non ne dimostra il funzionamento.
              </p>
            </div>
            <a
              class="source-link"
              href={gttSource}
              target="_blank"
              rel="noreferrer"
              >Apri la fonte ufficiale GTT<Icon name="external" size={15} /></a
            >
          </aside>
        </StatisticGate>
      </div>
      <section class="panel feed-panel">
        <div class="panel-heading">
          <div>
            <p class="eyebrow">DALLA COMMUNITY</p>
            <h2>Le ultime segnalazioni</h2>
          </div>
          <label class="feed-select"
            >Stazione<select
              aria-label="Filtra le segnalazioni per stazione"
              bind:value={streamFilter}
              ><option value="all">Tutte le stazioni</option
              >{#each stations as s}<option value={s.id}>{s.name}</option
                >{/each}</select
            ></label
          >
        </div>
        <div class="feed-list">
          {#each feed as report}{@const device = data.devices.find(
              (d) => d.id === report.device_id,
            )}
            <article class="feed-item">
              <span class="feed-avatar"
                ><Icon
                  name={device?.kind === "ascensore" ? "lift" : "stairs"}
                  size={22}
                /></span
              >
              <div class="feed-content">
                <div class="feed-top">
                  <h3>{stationName(report.station_id)}</h3>
                  <span>·</span><small
                    >{deviceName(data, report.device_id)}</small
                  ><span
                    class:functioning={report.status === "funzionante"}
                    class:broken={report.status === "guasta"}
                    class:maintenance={report.status === "manutenzione"}
                    class:unknown={report.status === "non_verificabile"}
                    class="status compact"
                    ><span></span>{labels[report.status]}</span
                  >
                </div>
                {#if report.description}<p>
                    {report.description}
                  </p>{/if}{#if report.photo?.status === "approved"}<img
                    class="feed-photo"
                    src={report.photo.data}
                    alt="Foto approvata della segnalazione"
                  />{/if}
                <div class="feed-meta">
                  <span>{report.author_name}</span><span
                    >Osservazione {age(report.observed_at)}</span
                  >{#if report.photo && report.photo.status !== "rejected"}<span
                      ><Icon name="camera" size={12} />{report.photo.status ===
                      "approved"
                        ? "Foto approvata"
                        : "Foto in revisione"}</span
                    >{/if}
                </div>
              </div>
              <time datetime={report.recorded_at}
                >{age(report.recorded_at)}</time
              >
            </article>{/each}{#if !feed.length}<div class="empty-state">
              <h3>Ancora nessuna segnalazione</h3>
              <p>Contribuisci con una prima osservazione.</p>
            </div>{/if}
        </div>
        <div class="feed-footnote">
          <Icon name="clock" size={14} />Osservazione e registrazione sono
          separate. {browserDemo || data.availability?.synthetic
            ? "Gli esempi non descrivono lo stato reale della metro."
            : "Controlla sempre il momento dell’osservazione."}
        </div>
      </section>
      {#if data.feedCursor}<button
          class="button outline"
          onclick={loadMore}
          disabled={busy}>Carica altre segnalazioni</button
        >{/if}
      <section class="contribute-banner">
        <span class="contribute-icon"><Icon name="plus" size={28} /></span>
        <div>
          <h3>C’è un impianto che non trovi?</h3>
          <p>
            Proponi una scala mobile o un ascensore. Il moderatore verificherà
            la proposta.
          </p>
        </div>
        <button class="button outline" onclick={() => go("proposal")}
          >Proponi un impianto<Icon name="arrow" size={17} /></button
        >
      </section>
      {#if user && data.proposals.some((p) => p.actor_id === user?.id)}<section
          class="my-proposals"
        >
          <h3>Le tue proposte</h3>
          {#each data.proposals.filter((p) => p.actor_id === user?.id) as p}<div
            >
              <span>{stationName(p.station_id)} · {p.name}</span><span
                class="status"
                class:maintenance={p.status === "pending"}
                class:functioning={p.status === "approved"}
                class:broken={p.status === "rejected"}
                >{p.status === "pending"
                  ? "In attesa di approvazione"
                  : p.status === "approved"
                    ? "Approvata"
                    : "Respinta"}</span
              >
            </div>{/each}
        </section>{/if}
    {:else if view === "report" || view === "proposal"}
      <button class="back-link" onclick={() => go("home")}
        ><Icon name="back" size={17} />Torna alla panoramica</button
      >
      <div class="form-heading">
        <p class="eyebrow">IL TUO CONTRIBUTO CONTA</p>
        <h1>
          {view === "report" ? "Una segnalazione," : "Un nuovo impianto,"}<br
          /><span
            >{view === "report"
              ? "un percorso più chiaro."
              : "un censimento più completo."}</span
          >
        </h1>
        <p>
          {view === "report"
            ? "Raccontaci cosa hai osservato. Stazione e impianto sono obbligatori; foto e descrizione sono facoltative."
            : "Non trovi una scala mobile o un ascensore? Descrivi dove si trova. Sarà pubblicato solo dopo la verifica del moderatore."}
        </p>
      </div>
      <div class="form-layout">
        <form
          class="panel contribution-form"
          onsubmit={view === "report" ? sendReport : sendProposal}
        >
          <div class="form-section-title">
            <span>01</span>
            <h2>
              {view === "report"
                ? "Dove si trova l’impianto?"
                : "Identifichiamo l’impianto"}
            </h2>
          </div>
          <label for="station">Stazione <span class="required">*</span></label
          ><select
            id="station"
            bind:value={selectedStation}
            onchange={() => (selectedDevice = "")}
            required
            disabled={busy}
            ><option value="" disabled>Scegli la stazione</option
            >{#each stations as s}<option value={s.id}>{s.name}</option
              >{/each}</select
          >
          {#if view === "report"}<label for="device"
              >Scala mobile o ascensore <span class="required">*</span></label
            ><select
              id="device"
              bind:value={selectedDevice}
              required
              disabled={busy || !selectedStation}
              ><option value="" disabled>Scegli l’impianto</option
              >{#each formDevices as d}<option value={d.id}
                  >{kindLabels[d.kind]} · {d.name} — {d.location}</option
                >{/each}</select
            >
            <div class="missing-device">
              <Icon name="search" size={15} /><span>Non trovi l’impianto?</span
              ><button
                type="button"
                class="text-button"
                onclick={() => go("proposal")}
                >Proponilo al censimento<Icon name="arrow" size={14} /></button
              >
            </div>
          {:else}<label for="kind"
              >Tipo di impianto <span class="required">*</span></label
            ><select
              id="kind"
              bind:value={proposalKind}
              required
              disabled={busy}
              ><option value="scala_mobile">Scala mobile</option><option
                value="ascensore">Ascensore</option
              ></select
            ><label for="proposal-name"
              >Nome o identificazione <span class="required">*</span></label
            ><input
              id="proposal-name"
              bind:value={proposalName}
              minlength="3"
              maxlength="100"
              placeholder="Es. Ascensore lato uscita nord"
              required
              disabled={busy}
            /><label for="location"
              >Posizione e percorso servito <span class="required">*</span
              ></label
            ><textarea
              id="location"
              bind:value={proposalLocation}
              minlength="5"
              maxlength="300"
              placeholder="Indica l’ingresso, il piano e il collegamento: es. lato nord, strada → mezzanino."
              required
              disabled={busy}></textarea>{/if}
          {#if view === "report"}<div class="form-section-title">
              <span>02</span>
              <h2>Cosa hai osservato?</h2>
            </div>
            <fieldset class="status-options">
              <legend
                >Stato dell’impianto <span class="required">*</span></legend
              >{#each Object.entries(labels) as [value, label]}<label
                  class:selected={selectedStatus === value}
                  ><input
                    type="radio"
                    bind:group={selectedStatus}
                    {value}
                    disabled={busy}
                  /><span class="radio-circle"></span><span>{label}</span
                  ></label
                >{/each}
            </fieldset>{/if}
          <div class="form-section-title">
            <span>{view === "report" ? "03" : "02"}</span>
            <h2>Un po’ di contesto <small>facoltativo</small></h2>
          </div>
          <label for="description">Descrizione</label><textarea
            id="description"
            bind:value={reportDescription}
            maxlength="1000"
            placeholder={view === "report"
              ? "Es. l’ascensore non risponde al pulsante di chiamata. Non inserire dati personali."
              : "Aggiungi indicazioni utili per riconoscere e verificare l’impianto."}
            rows="4"
            disabled={busy}></textarea>
          <div class="character-count">{reportDescription.length}/1.000</div>
          <label for="photo">Fotografia</label>
          <div class="photo-upload">
            <input
              id="photo"
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onchange={pickPhoto}
              bind:this={photoInput}
              disabled={busy}
            /><Icon name="camera" size={29} /><strong
              >{busy
                ? "Elaborazione…"
                : photo
                  ? "Foto aggiunta"
                  : "Aggiungi una foto"}</strong
            ><span>JPEG, PNG o WebP · massimo 5 MB</span>
          </div>
          {#if photo}<div class="photo-preview">
              <img
                src={photo.data}
                alt="Anteprima privata della foto allegata"
              />
              <div>
                <strong>La foto rimane in revisione</strong>
                <p>Comparirà solo dopo l’approvazione.</p>
                <button class="text-button" type="button" onclick={removePhoto}
                  >Rimuovi foto<Icon name="close" size={14} /></button
                >
              </div>
            </div>{/if}
          <div class="form-submit">
            <span
              ><Icon name="shield" size={16} />{view === "report"
                ? "Contributo attribuito al tuo account"
                : "La proposta sarà esaminata prima della pubblicazione"}</span
            ><button type="submit" class="button yellow" disabled={busy}
              >{busy
                ? "Invio in corso…"
                : view === "report"
                  ? "Invia segnalazione"
                  : "Invia proposta"}<Icon name="arrow" size={18} /></button
            >
          </div>
        </form>
        <aside class="form-aside">
          <span class="aside-icon"
            ><Icon
              name={view === "report" ? "user" : "shield"}
              size={27}
            /></span
          >
          <h3>
            {view === "report"
              ? "Un’osservazione utile è un’osservazione precisa."
              : "Prima la verifica, poi la pubblicazione."}
          </h3>
          <p>
            {view === "report"
              ? "Scegli il singolo impianto che hai visto. Una stazione può avere più scale mobili e ascensori."
              : "Le proposte non entrano subito nel censimento. Il moderatore verifica posizione, identificazione ed eventuali duplicati."}
          </p>
          <ul>
            <li>Condividi ciò che hai osservato direttamente.</li>
            <li>Evita volti, documenti e dati personali nelle foto.</li>
            <li>
              Le fotografie vengono ricodificate e sottoposte a revisione.
            </li>
          </ul>
          <div class="form-aside-note">
            <Icon name="warning" size={16} /><span
              >{browserDemo || backendMode() !== "aws"
                ? "Usa solo contenuti di prova in questo ambiente."
                : "Condividi solo fotografie che puoi pubblicare."}</span
            >
          </div>
        </aside>
      </div>
    {:else if view === "moderation" && user?.role === "moderator"}
      <section class="dashboard-heading">
        <div>
          <p class="eyebrow">AREA MODERATORE</p>
          <h1>Un censimento <span>di cui fidarsi.</span></h1>
          <p>Verifica le proposte e le fotografie prima della pubblicazione.</p>
        </div>
        <span class="moderator-label"
          ><Icon name="shield" size={20} />Moderazione</span
        >
      </section>
      <div class="moderation-tabs">
        <button
          class:active={moderationTab === "devices"}
          onclick={() => (moderationTab = "devices")}
          >Nuovi impianti<span>{pending.length}</span></button
        ><button
          class:active={moderationTab === "photos"}
          onclick={() => (moderationTab = "photos")}
          >Foto in revisione<span>{photoQueue.length}</span></button
        >{#if browserDemo}<button
            class:active={moderationTab === "history"}
            onclick={() => (moderationTab = "history")}
            >Decisioni precedenti</button
          >{/if}
      </div>
      {#if moderationTab === "devices"}<div class="moderation-list">
          {#each pending as proposal}<article class="panel moderation-card">
              <div class="moderation-card-heading">
                <span class="device-icon blue"
                  ><Icon
                    name={proposal.kind === "ascensore" ? "lift" : "stairs"}
                    size={25}
                  /></span
                >
                <div>
                  <span class="eyebrow">{stationName(proposal.station_id)}</span
                  >
                  <h2>{proposal.name}</h2>
                </div>
                <span class="status maintenance">Da verificare</span>
              </div>
              <dl>
                <div>
                  <dt>Tipo</dt>
                  <dd>{kindLabels[proposal.kind]}</dd>
                </div>
                <div>
                  <dt>Posizione</dt>
                  <dd>{proposal.location}</dd>
                </div>
                <div>
                  <dt>Inviata il</dt>
                  <dd>{date(proposal.created_at)}</dd>
                </div>
              </dl>
              {#if proposal.description}<p>
                  {proposal.description}
                </p>{/if}{#if proposal.photo}{#if browserDemo}<img
                    class="moderation-photo"
                    src={proposal.photo.data}
                    alt="Foto privata della proposta da verificare"
                  />{:else}<PrivatePhoto id={proposal.photo.id!} />{/if}{/if}
              <p class="review-note">
                <Icon name="shield" size={15} />L’approvazione aggiunge
                l’impianto. L’eventuale foto resta in una revisione separata.
              </p>
              {#if !browserDemo}<label for={`reason-${proposal.id}`}
                  >Motivazione della decisione (privata)</label
                ><textarea
                  id={`reason-${proposal.id}`}
                  bind:value={reviewReasons[proposal.id]}
                  minlength="3"
                  maxlength="1000"
                  disabled={busy}></textarea>{/if}
              <div class="review-actions">
                <button
                  class="button navy"
                  disabled={busy ||
                    (!browserDemo &&
                      (reviewReasons[proposal.id]?.trim().length || 0) < 3)}
                  onclick={() => decide(proposal.id, "approved")}
                  ><Icon name="check" size={17} />Approva impianto</button
                ><button
                  class="button outline"
                  disabled={busy ||
                    (!browserDemo &&
                      (reviewReasons[proposal.id]?.trim().length || 0) < 3)}
                  onclick={() => decide(proposal.id, "rejected")}
                  ><Icon name="close" size={17} />Respingi proposta</button
                >
              </div>
            </article>{/each}{#if !pending.length}<div
              class="panel empty-state large"
            >
              <span class="empty-icon"><Icon name="check" size={32} /></span>
              <h2>Tutte le proposte sono state esaminate</h2>
              <p>
                I nuovi impianti proposti dai cittadini compariranno qui prima
                di entrare nel censimento.
              </p>
            </div>{/if}
        </div>
      {:else if moderationTab === "photos"}<div class="moderation-list">
          {#each photoQueue as item}<article class="panel moderation-card">
              <div class="moderation-card-heading">
                <div>
                  <p class="eyebrow">{stationName(item.station_id)}</p>
                  <h2>{item.name}</h2>
                </div>
                <span class="status maintenance">Foto privata</span>
              </div>
              {#if browserDemo}<img
                  class="moderation-photo"
                  src={item.photo.data}
                  alt="Fotografia privata in revisione"
                />{:else}<PrivatePhoto id={item.id} />{/if}
              <p class="review-note">
                Controlla che la foto riguardi l’impianto e non contenga volti,
                documenti o dati personali.
              </p>
              {#if !browserDemo}<label for={`reason-${item.id}`}
                  >Motivazione della decisione (privata)</label
                ><textarea
                  id={`reason-${item.id}`}
                  bind:value={reviewReasons[item.id]}
                  minlength="3"
                  maxlength="1000"
                  disabled={busy}></textarea>{/if}
              <div class="review-actions">
                <button
                  class="button navy"
                  disabled={busy ||
                    (!browserDemo &&
                      (reviewReasons[item.id]?.trim().length || 0) < 3)}
                  onclick={() => decidePhoto(item.id, item.origin, "approved")}
                  ><Icon name="check" size={17} />Approva foto</button
                ><button
                  class="button outline"
                  disabled={busy ||
                    (!browserDemo &&
                      (reviewReasons[item.id]?.trim().length || 0) < 3)}
                  onclick={() => decidePhoto(item.id, item.origin, "rejected")}
                  >Respingi foto</button
                >
              </div>
            </article>{/each}{#if !photoQueue.length}<div
              class="panel empty-state large"
            >
              <Icon name="camera" size={32} />
              <h2>Nessuna foto in attesa</h2>
              <p>
                Le foto delle segnalazioni e degli impianti approvati saranno
                revisionate qui.
              </p>
            </div>{/if}
        </div>
      {:else}<section class="panel decision-history">
          <h2>Decisioni registrate</h2>
          {#each data.audit.toReversed() as item}<div>
              <Icon name="shield" size={17} /><span
                >{item.decision === "approved"
                  ? "Impianto approvato"
                  : item.decision === "rejected"
                    ? "Proposta respinta"
                    : item.decision === "photo_approved"
                      ? "Foto approvata"
                      : "Foto respinta"}</span
              ><time>{date(item.recorded_at)}</time>
            </div>{/each}{#if !data.audit.length}<p>
              Non sono ancora state prese decisioni in questa sessione.
            </p>{/if}
        </section>{/if}
    {/if}
  </main>{/if}

<footer class="site-footer">
  <div>
    <span class="footer-brand"
      ><Icon name="stairs" size={20} />Scale Mobili Torino</span
    >
    <p>Un progetto civico indipendente, non affiliato a GTT.</p>
  </div>
  <div>
    <span>Scale mobili. Ascensori. Persone.</span><small
      >{browserDemo || data?.availability?.synthetic
        ? "Prototipo con dati dimostrativi"
        : "Prototipo civico"} · Orari Europe/Rome</small
    >
  </div>
</footer>
{#if loginOpen}<div
    class="modal-backdrop"
    role="presentation"
    onclick={(e) => {
      if (e.target === e.currentTarget) loginOpen = false;
    }}
  >
    <div
      use:focusDialog
      class="dialog login-dialog"
      role="dialog"
      aria-modal="true"
      aria-labelledby="login-title"
      tabindex="-1"
      onkeydown={(e) => {
        if (e.key === "Escape") loginOpen = false;
      }}
    >
      <button
        class="icon-button dialog-close"
        aria-label="Chiudi accesso"
        onclick={() => (loginOpen = false)}><Icon name="close" /></button
      ><span class="login-symbol"><Icon name="user" size={30} /></span>
      <p class="eyebrow">UNA COMMUNITY, TANTI PERCORSI</p>
      <h2 id="login-title">Entra nella piattaforma</h2>
      <p>
        Accedi per vedere tutte le statistiche, segnalare un problema o proporre
        un impianto.
      </p>
      {#if error}<p role="alert">{error}</p>{/if}
      {#if developmentLogin()}
        <div class="login-demo-box">
          <strong
            >{browserDemo ? "Accesso alla demo" : "Accesso di sviluppo"}</strong
          ><span
            >Identità di prova per questo ambiente. Nessuna registrazione reale.</span
          >
        </div>
        <button
          class="button yellow full"
          onclick={() => enter("citizen")}
          disabled={busy}
          >Continua come cittadino<Icon name="arrow" size={18} /></button
        >
        <button
          class="button outline full"
          onclick={() => enter("moderator")}
          disabled={busy}
          ><Icon name="shield" size={18} />Prova la modalità moderatore</button
        >
        <small class="login-footnote"
          >La modalità moderatore serve a provare l’approvazione di impianti e
          foto.</small
        >
      {:else}<button
          class="button yellow full"
          onclick={() => enter("citizen")}
          disabled={busy}
          >Accedi al tuo account<Icon name="arrow" size={18} /></button
        ><small class="login-footnote"
          >L’accesso avviene attraverso il servizio di autenticazione.</small
        >{/if}
    </div>
  </div>{/if}
{#if detail && data}{@const observation = latest(data, detail.id)}
  <div
    class="modal-backdrop"
    role="presentation"
    onclick={(e) => {
      if (e.target === e.currentTarget) detail = null;
    }}
  >
    <div
      use:focusDialog
      class="dialog detail-dialog"
      role="dialog"
      aria-modal="true"
      aria-labelledby="detail-title"
      tabindex="-1"
      onkeydown={(e) => {
        if (e.key === "Escape") detail = null;
      }}
    >
      <button
        class="icon-button dialog-close"
        aria-label="Chiudi scheda"
        onclick={() => (detail = null)}><Icon name="close" /></button
      ><span class="device-icon blue"
        ><Icon
          name={detail.kind === "ascensore" ? "lift" : "stairs"}
          size={30}
        /></span
      >
      <p class="eyebrow">
        {stationName(detail.station_id)}{detail.synthetic
          ? " · IMPIANTO DEMO"
          : ""}
      </p>
      <h2 id="detail-title">{detail.name}</h2>
      <p>{detail.location}</p>
      <div class="detail-evidence">
        <strong>Community</strong><span
          >{observation
            ? labels[observation.status]
            : "Nessuna informazione disponibile"}</span
        ><small
          >{observation
            ? `Osservata il ${date(observation.observed_at)}`
            : "L’assenza di dati non è uno stato di funzionamento."}</small
        >
      </div>
      <div class="detail-evidence muted">
        <strong>Fonte ufficiale</strong><span
          >{data.officialEvidence?.[detail.id]
            ? labels[data.officialEvidence[detail.id]!.status]
            : "Nessuna evidenza disponibile"}</span
        ><small
          >{browserDemo
            ? "I valori del confronto in home sono esclusivamente dimostrativi."
            : data.officialEvidence?.[detail.id]?.published_at
              ? `Pubblicata il ${date(data.officialEvidence[detail.id]!.published_at!)}`
              : "L’assenza di comunicazioni non prova il funzionamento."}</small
        >
      </div>
      <button
        class="button yellow full"
        onclick={() => {
          const chosen = detail!;
          detail = null;
          reportFor(chosen);
        }}>Segnala questo impianto<Icon name="plus" size={18} /></button
      >
    </div>
  </div>{/if}
