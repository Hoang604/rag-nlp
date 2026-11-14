<script setup lang="ts">
interface Props {
  src: string
  alt: string
  caption: string
  // Empty when no technical coordinate or view badge is shown in the caption bar
  badge?: string
  // Empty when natural aspect sizing inside flex/grid suffices without an explicit cap
  maxHeight?: string
}

const props = defineProps<Props>()
</script>

<template>
  <figure class="fig-frame">
    <div class="fig-img-wrap">
      <img
        :src="props.src"
        :alt="props.alt"
        class="fig-img"
        :style="props.maxHeight ? { maxHeight: props.maxHeight } : undefined"
      />
    </div>
    <figcaption class="fig-caption">
      <span class="fig-cap-text">{{ props.caption }}</span>
      <span v-if="props.badge" class="pill pill-accent tabular">{{ props.badge }}</span>
    </figcaption>
  </figure>
</template>

<style scoped>
.fig-frame {
  margin: 0;
  background-color: var(--color-bg-surface);
  border-radius: var(--radius-lg);
  padding: 0.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  min-width: 0;
}

.fig-img-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: var(--color-bg-surface);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.fig-img {
  display: block;
  max-width: 100%;
  width: auto;
  height: auto;
  object-fit: contain;
  border-radius: var(--radius-md);
  outline: 1px solid oklch(0 0 0 / 0.1);
  outline-offset: -1px;
}

.fig-caption {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  padding-inline: 0.25rem;
}

.fig-cap-text {
  font-size: 0.7rem;
  color: var(--color-text-muted);
}
</style>
