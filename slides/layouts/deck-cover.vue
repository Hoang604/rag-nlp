<script setup lang="ts">
import CoverHeroDiagram from '../components/CoverHeroDiagram.vue'

interface Props {
  eyebrow: string
  subtitle: string
  course: string
  group: string
  advisor: string
  repo: string
}

const props = defineProps<Props>()
</script>

<template>
  <div class="slidev-layout cover-shell">
    <header class="cover-top">
      <span class="cover-eyebrow">{{ props.eyebrow }}</span>
      <span class="cover-course tabular">{{ props.course }}</span>
    </header>

    <main class="cover-hero-grid">
      <div class="cover-left">
        <div class="cover-title-wrap">
          <slot />
        </div>
        <p class="cover-subtitle">{{ props.subtitle }}</p>

        <div class="cover-meta-stack">
          <div class="meta-block">
            <div class="meta-value">{{ props.group }}</div>
            <div class="meta-label">Thành viên thực hiện</div>
          </div>
          <div class="meta-row-2">
            <div class="meta-block">
              <div class="meta-value">{{ props.advisor }}</div>
              <div class="meta-label">Giảng viên hướng dẫn</div>
            </div>
            <div class="meta-block">
              <div class="meta-value mono">{{ props.repo }}</div>
              <div class="meta-label">Mã nguồn &amp; Bộ kiểm thử mù</div>
            </div>
          </div>
        </div>
      </div>

      <div class="cover-right">
        <CoverHeroDiagram />
      </div>
    </main>
  </div>
</template>

<style scoped>
.cover-shell {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  height: 100%;
  padding: 1.8rem 2.5rem 1.7rem;
  gap: 1.15rem;
  background:
    radial-gradient(circle at 88% 18%, var(--color-accent-tint) 0%, transparent 48%),
    var(--color-bg-canvas);
}

.cover-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.cover-eyebrow {
  display: inline-block;
  padding: 0.24rem 0.62rem;
  border-radius: var(--radius-sm);
  background-color: var(--color-accent-badge);
  color: var(--color-accent-strong);
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.cover-course {
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--color-text-muted);
}

.cover-hero-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.18fr) minmax(0, 0.92fr);
  gap: 1.25rem;
  align-items: center;
  min-height: 0;
}

.cover-left {
  display: flex;
  flex-direction: column;
  gap: 0.78rem;
  min-width: 0;
}

.cover-title-wrap :deep(h1) {
  font-size: 2.02rem;
  font-weight: 700;
  line-height: 1.13;
  letter-spacing: -0.02em;
  color: var(--color-text-primary);
  max-width: 26ch;
}

.cover-subtitle {
  font-size: 0.86rem;
  line-height: 1.46;
  color: var(--color-text-secondary);
  max-width: 60ch;
}

.cover-meta-stack {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.meta-row-2 {
  display: grid;
  grid-template-columns: 0.95fr 1.05fr;
  gap: 0.5rem;
}

.meta-block {
  background-color: var(--color-bg-surface);
  border-radius: var(--radius-md);
  padding: 0.52rem 0.75rem;
}

.meta-value {
  font-size: 0.77rem;
  font-weight: 600;
  color: var(--color-text-primary);
}

.meta-value.mono {
  font-family: var(--font-mono);
  font-size: 0.72rem;
  color: var(--color-accent-strong);
}

.meta-label {
  font-size: 0.67rem;
  color: var(--color-text-muted);
  margin-top: 0.1rem;
}

.cover-right {
  min-width: 0;
}
</style>
