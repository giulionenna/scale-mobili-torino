<script lang="ts">
  import { onMount } from "svelte";
  import { privatePhoto } from "./platform-client";
  let { id }: { id: string } = $props();
  let source = $state("");
  let error = $state("");
  onMount(() => {
    let disposed = false;
    void privatePhoto(id)
      .then((url) => {
        if (disposed) URL.revokeObjectURL(url);
        else source = url;
      })
      .catch((e) => {
        if (!disposed) error = e.message;
      });
    return () => {
      disposed = true;
      if (source) URL.revokeObjectURL(source);
    };
  });
</script>

{#if source}<img
    class="moderation-photo"
    src={source}
    alt="Fotografia privata in revisione"
  />{:else}<p role="status">
    {error || "Caricamento dell’anteprima privata…"}
  </p>{/if}
