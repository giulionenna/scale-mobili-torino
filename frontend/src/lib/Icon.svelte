<script lang="ts">
  let { name = "arrow", size = 20 }: { name?: string; size?: number } =
    $props();
</script>

<svg
  width={size}
  height={size}
  viewBox="0 0 24 24"
  fill="none"
  stroke="currentColor"
  stroke-width="1.7"
  stroke-linecap="round"
  stroke-linejoin="round"
  aria-hidden="true"
>
  {#if name === "stairs"}<path
      d="M3 18h5l9-12h4M3 21h7L19 9h2M7 10l3 1M8 5a1.3 1.3 0 1 0 0 .01"
    />
  {:else if name === "lift"}<rect
      x="4"
      y="3"
      width="16"
      height="18"
      rx="3"
    /><path d="M12 7v14M8 7l-1 2m1-2 1 2m7 3-1-2m1 2 1-2" />
  {:else if name === "train"}<rect
      x="5"
      y="3"
      width="14"
      height="15"
      rx="4"
    /><path d="M5 10h14M9 3v7m6-7v7M8 18l-2 3m10-3 2 3" /><path
      d="M8 14h1m6 0h1"
    />
  {:else if name === "plus"}<path d="M12 5v14M5 12h14" />
  {:else if name === "pin"}<path
      d="M19 10c0 5-7 11-7 11s-7-6-7-11a7 7 0 0 1 14 0Z"
    /><circle cx="12" cy="10" r="2.5" />
  {:else if name === "check"}<path d="m5 12 4 4 10-10" />
  {:else if name === "shield"}<path
      d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6Z"
    /><path d="m8 12 3 3 5-6" />
  {:else if name === "user"}<circle cx="12" cy="8" r="4" /><path
      d="M4 21v-2a8 8 0 0 1 16 0v2"
    />
  {:else if name === "clock"}<circle cx="12" cy="12" r="9" /><path
      d="M12 7v5l3 2"
    />
  {:else if name === "camera"}<path d="M3 8h4l2-3h6l2 3h4v12H3Z" /><circle
      cx="12"
      cy="13"
      r="3.5"
    />
  {:else if name === "chart"}<path d="M4 3v17h17M8 15v-4m5 4V7m5 8v-6" />
  {:else if name === "compare"}<path
      d="M5 7h14m-3-3 3 3-3 3M19 17H5m3-3-3 3 3 3"
    />
  {:else if name === "search"}<circle cx="10.5" cy="10.5" r="6.5" /><path
      d="m16 16 5 5"
    />
  {:else if name === "close"}<path d="m6 6 12 12M6 18 18 6" />
  {:else if name === "warning"}<path d="m12 3 10 17H2Z" /><path
      d="M12 9v4m0 3h.01"
    />
  {:else if name === "logout"}<path d="M9 4H4v16h5m5-12 4 4-4 4m-7-4h11" />
  {:else if name === "back"}<path d="m10 5-7 7 7 7M3 12h18" />
  {:else if name === "external"}<path d="M14 3h7v7m0-7L10 14M10 3H3v18h18v-7" />
  {:else if name === "menu"}<path d="M4 6h16M4 12h16M4 18h16" />
  {:else}<path d="M4 12h16m-6-6 6 6-6 6" />{/if}
</svg>
