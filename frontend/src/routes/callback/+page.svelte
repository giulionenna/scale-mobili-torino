<script lang="ts">
  import { onMount } from "svelte";
  import { finishLogin, returnDestination } from "$lib/auth";
  let message = $state("Completiamo l’accesso…");
  onMount(() => {
    finishLogin()
      .then(() => window.location.replace(returnDestination()))
      .catch((error) => (message = error.message));
  });
</script>

<svelte:head><title>Accesso · Scale Mobili Torino</title></svelte:head>
<main class="callback">
  <h1>Accesso</h1>
  <p role="status">{message}</p>
  <a href="/">Torna al sito</a>
</main>
