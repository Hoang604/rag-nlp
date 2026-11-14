<script setup lang="ts">
import { computed } from 'vue'
import { useNav, useSlideContext } from '@slidev/client'

interface Props {
  section: string
  // Empty when Slidev consumes frontmatter `title` into `$frontmatter.title` instead of layout props
  title?: string
  // Empty when the slide heading already states the full thesis without needing a supporting line
  subtitle?: string
}

const props = defineProps<Props>()
const { currentPage, total } = useNav()
const { $frontmatter } = useSlideContext()

const resolvedTitle = computed<string>(() => {
  const fmTitle = typeof $frontmatter.title === 'string' ? $frontmatter.title : ''
  return props.title ?? fmTitle
})

const pad = (n: number): string => String(n).padStart(2, '0')
</script>

<template>
  <div class="slidev-layout section-shell">
    <header class="slide-header">
      <div class="header-top-row">
        <span class="section-tag">{{ props.section }}</span>
        <div class="page-indicator tabular" aria-label="Slide progress">
          <span class="page-cur">{{ pad(currentPage) }}</span>
          <span class="page-sep">/</span>
          <span class="page-tot">{{ pad(total) }}</span>
        </div>
      </div>
      <h1 class="slide-title">{{ resolvedTitle }}</h1>
      <p v-if="props.subtitle" class="slide-subtitle">{{ props.subtitle }}</p>
    </header>

    <main class="slide-body">
      <slot />
    </main>

    <footer class="slide-footer">
      <span class="footer-brand">Agent-Oriented Hierarchical RAG &amp; Knowledge Graph Framework</span>
      <span class="footer-meta tabular">PostgreSQL 16 · pgvector · ltree · MCP</span>
    </footer>
  </div>
</template>

<style scoped>
.section-shell {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  height: 100%;
  padding: 0.98rem 2.6rem 0.74rem;
  gap: 0.46rem;
  background-color: var(--color-bg-canvas);
}

.slide-header {
  display: flex;
  flex-direction: column;
  gap: 0.32rem;
}

.header-top-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.section-tag {
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--color-accent-strong);
}

.page-indicator {
  display: inline-flex;
  align-items: baseline;
  gap: 0.2rem;
  font-size: 0.73rem;
}

.page-cur {
  font-weight: 700;
  color: var(--color-text-primary);
}

.page-sep,
.page-tot {
  color: var(--color-text-muted);
}

.slide-title {
  font-size: 1.18rem !important;
  font-weight: 700 !important;
  line-height: 1.36 !important;
  letter-spacing: -0.015em;
  color: var(--color-text-primary);
  margin: 0 0 0.1rem 0 !important;
}

.slide-subtitle {
  font-size: 0.75rem;
  line-height: 1.38;
  color: var(--color-text-muted);
  max-width: 86ch;
  opacity: 1 !important;
}

.slide-body {
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-height: 0;
  min-width: 0;
}

.slide-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 0.38rem;
  border-top: 1px solid var(--color-divider-hairline);
  font-size: 0.68rem;
  color: var(--color-text-muted);
}

.footer-brand {
  font-weight: 500;
}
</style>
