<script lang="ts">
  import { PUBLIC_BROWSER_DEMO } from '$env/static/public';
  import Dashboard from '$lib/Dashboard.svelte';
  import Platform from '$lib/Platform.svelte';
</script>
{#if PUBLIC_BROWSER_DEMO === 'true'}<Platform />{:else}<Dashboard />{/if}
