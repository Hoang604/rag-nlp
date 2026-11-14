<script setup lang="ts">
import SvgIcon, { type IconName } from './SvgIcon.vue'

type CardVariant = 'surface' | 'subtle' | 'accent' | 'semantic' | 'verbatim' | 'danger'

interface Props {
  // Empty when the default elevated white surface role applies
  variant?: CardVariant
  // Empty when the card groups content directly under its title without a category overline
  eyebrow?: string
  // Empty when the card renders only a formula or custom visual block
  title?: string
  // Empty when no right-hand metric or status tag accompanies the header
  badge?: string
  // Empty when the card heading uses text hierarchy alone without an icon
  icon?: IconName
  // Empty when standard card inset padding applies
  compact?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'surface',
  compact: false,
})
</script>

<template>
  <section :class="['surface-card', `variant-${props.variant}`, { 'is-compact': props.compact }]">
    <header v-if="props.eyebrow || props.title || props.badge || props.icon" class="card-head">
      <div class="card-head-main">
        <div v-if="props.eyebrow" class="card-eyebrow">{{ props.eyebrow }}</div>
        <div v-if="props.title || props.icon" class="card-title-row">
          <SvgIcon v-if="props.icon" :name="props.icon" class="card-icon" />
          <h3 v-if="props.title" class="card-title">{{ props.title }}</h3>
        </div>
      </div>
      <span v-if="props.badge" class="card-badge tabular">{{ props.badge }}</span>
    </header>
    <div class="card-body">
      <slot />
    </div>
  </section>
</template>

<style scoped>
.surface-card {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  border-radius: var(--radius-lg);
  padding: 0.78rem 0.95rem;
  border: none;
  min-width: 0;
}

.surface-card.is-compact {
  padding: 0.58rem 0.8rem;
  gap: 0.28rem;
}

.variant-surface {
  background-color: var(--color-bg-surface);
}

.variant-subtle {
  background-color: var(--color-bg-subtle);
}

.variant-accent {
  background-color: var(--color-accent-tint);
}

.variant-semantic {
  background-color: var(--color-sem-tint);
}

.variant-verbatim {
  background-color: var(--color-verb-tint);
}

.variant-danger {
  background-color: var(--color-danger-tint);
}

.card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.45rem;
}

.card-head-main {
  display: flex;
  flex-direction: column;
  gap: 0.12rem;
  min-width: 0;
}

.card-eyebrow {
  font-size: 0.64rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--color-text-muted);
}

.variant-accent .card-eyebrow,
.variant-accent .card-icon {
  color: var(--color-accent-strong);
}

.variant-semantic .card-eyebrow,
.variant-semantic .card-icon {
  color: var(--color-sem-strong);
}

.variant-verbatim .card-eyebrow,
.variant-verbatim .card-icon {
  color: var(--color-verb-strong);
}

.variant-danger .card-eyebrow,
.variant-danger .card-icon {
  color: var(--color-danger-strong);
}

.card-title-row {
  display: flex;
  align-items: center;
  gap: 0.36rem;
}

.card-icon {
  color: var(--color-accent-solid);
  font-size: 0.94rem;
}

.card-title {
  font-size: 0.86rem;
  font-weight: 700;
  line-height: 1.24;
  color: var(--color-text-primary);
}

.card-badge {
  padding: 0.12rem 0.44rem;
  border-radius: var(--radius-sm);
  font-size: 0.67rem;
  font-weight: 600;
  background-color: var(--color-bg-code);
  color: var(--color-text-primary);
  white-space: nowrap;
}

.variant-accent .card-badge {
  background-color: var(--color-accent-badge);
  color: var(--color-accent-strong);
}

.variant-semantic .card-badge {
  background-color: var(--color-sem-badge);
  color: var(--color-sem-strong);
}

.variant-verbatim .card-badge {
  background-color: var(--color-verb-badge);
  color: var(--color-verb-strong);
}

.variant-danger .card-badge {
  background-color: var(--color-danger-badge);
  color: var(--color-danger-strong);
}

.card-body {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  font-size: 0.76rem;
  line-height: 1.4;
  color: var(--color-text-secondary);
  min-width: 0;
}
</style>
