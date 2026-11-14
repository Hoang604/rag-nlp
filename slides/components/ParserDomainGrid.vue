<script setup lang="ts">
import { computed } from 'vue'
import SvgIcon, { type IconName } from './SvgIcon.vue'

interface DomainSpec {
  id: 'nextjs' | 'nodejs' | 'baohiem'
  icon: IconName
  domain: string
  format: string
  docs: number
  chunks: number
  summary: string
  depth: string
}

const DOMAINS: ReadonlyArray<DomainSpec> = [
  {
    id: 'nextjs',
    icon: 'file-code',
    domain: 'Next.js Official Docs',
    format: '.mdx, .md',
    docs: 101,
    chunks: 1239,
    summary: 'Tách theo tiêu đề và bảo toàn nguyên vẹn thẻ JSX, khối code mẫu.',
    depth: 'Độ sâu ≤ 7 tầng',
  },
  {
    id: 'nodejs',
    icon: 'terminal',
    domain: 'Node.js Core API',
    format: '.md',
    docs: 66,
    chunks: 4394,
    summary: 'Gom nhóm chữ ký hàm trùng tên và tách rõ hàm con độc lập.',
    depth: 'Độ sâu ≤ 6 tầng',
  },
  {
    id: 'baohiem',
    icon: 'scale',
    domain: 'Pháp luật Bảo hiểm VN',
    format: '.md pháp quy',
    docs: 3,
    chunks: 342,
    summary: 'Tổ chức chặt theo cấp Chương → Mục → Điều → Khoản → Điểm.',
    depth: 'Chương → Điều',
  },
]

const fmtInt = (n: number): string => n.toLocaleString('de-DE')

const totalDocs = computed<number>(() => DOMAINS.reduce((acc, d) => acc + d.docs, 0))
const totalChunks = computed<number>(() => DOMAINS.reduce((acc, d) => acc + d.chunks, 0))

const barTotalWidth = 840
const wNext = computed<number>(() => Math.round((DOMAINS[0].chunks / totalChunks.value) * barTotalWidth))
const wNode = computed<number>(() => Math.round((DOMAINS[1].chunks / totalChunks.value) * barTotalWidth))
const wLaw = computed<number>(() => barTotalWidth - wNext.value - wNode.value)
</script>

<template>
  <div class="domain-stack">
    <div class="domain-grid">
      <article v-for="item in DOMAINS" :key="item.id" class="domain-card">
        <header class="domain-head">
          <div class="title-wrap">
            <SvgIcon :name="item.icon" class="domain-ico" />
            <h3 class="domain-name">{{ item.domain }}</h3>
          </div>
          <span class="pill pill-neutral tabular">{{ item.format }}</span>
        </header>

        <div class="kpi-row tabular">
          <span><strong>{{ fmtInt(item.docs) }}</strong> tài liệu</span>
          <span>·</span>
          <span class="accent-val">{{ fmtInt(item.chunks) }} chunks</span>
        </div>

        <p class="domain-summary">{{ item.summary }}</p>

        <footer class="domain-foot">
          <span class="depth-chip tabular">{{ item.depth }}</span>
        </footer>
      </article>
    </div>

    <!-- Proportional Stacked Corpus Bar -->
    <div class="corpus-bar-card">
      <div class="bar-top tabular">
        <span>
          <strong>Toàn bộ kho ngữ liệu:</strong> {{ fmtInt(totalDocs) }} tài liệu ·
          <strong>{{ fmtInt(totalChunks) }} chunks có cấu trúc</strong>
        </span>
        <span class="pill pill-accent">Khớp 100% số dòng gốc</span>
      </div>
      <svg viewBox="0 0 840 28" class="prop-svg" role="img" aria-label="Tỷ trọng 5.975 chunks theo ba miền dữ liệu">
        <rect x="0" y="2" :width="wNode" height="24" rx="5" class="seg-node" />
        <text :x="wNode / 2" y="18" text-anchor="middle" class="seg-txt">Node.js API · 4.394 (73,5%)</text>

        <rect :x="wNode + 3" y="2" :width="wNext - 3" height="24" rx="5" class="seg-next" />
        <text :x="wNode + wNext / 2" y="18" text-anchor="middle" class="seg-txt">Next.js · 1.239 (20,7%)</text>

        <rect :x="wNode + wNext + 3" y="2" :width="Math.max(wLaw - 3, 28)" height="24" rx="5" class="seg-law" />
        <text :x="wNode + wNext + 3 + Math.max(wLaw - 3, 28) / 2" y="18" text-anchor="middle" class="seg-txt">342</text>
      </svg>
      <div class="law-callout tabular">
        <i class="law-swatch" aria-hidden="true" />
        <span>Pháp luật Bảo hiểm VN · 342 chunks (5,7%)</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.domain-stack {
  display: flex;
  flex-direction: column;
  gap: 0.95rem;
}

.domain-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.8rem;
  align-items: stretch;
}

.domain-card {
  background-color: var(--color-bg-surface);
  border-radius: var(--radius-lg);
  padding: 0.95rem 1rem;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 0.65rem;
  min-width: 0;
}

.domain-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.35rem;
}

.title-wrap {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  min-width: 0;
}

.domain-ico {
  color: var(--color-accent-solid);
  font-size: 1rem;
}

.domain-name {
  font-size: 0.78rem;
  font-weight: 700;
  color: var(--color-text-primary);
  white-space: nowrap;
}

.kpi-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  font-size: 0.78rem;
  color: var(--color-text-secondary);
  background-color: var(--color-bg-subtle);
  padding: 0.38rem 0.58rem;
  border-radius: var(--radius-sm);
}

.accent-val {
  font-weight: 700;
  color: var(--color-accent-strong);
}

.domain-summary {
  margin: 0;
  font-size: 0.76rem;
  line-height: 1.45;
  color: var(--color-text-secondary);
}

.domain-foot {
  padding-top: 0.38rem;
  border-top: 1px solid var(--color-divider-hairline);
  display: flex;
  align-items: center;
}

.depth-chip {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  font-weight: 700;
  color: var(--color-accent-strong);
}

.corpus-bar-card {
  background-color: var(--color-bg-surface);
  border-radius: var(--radius-lg);
  padding: 0.72rem 0.95rem;
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.bar-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  font-size: 0.78rem;
  color: var(--color-text-secondary);
}

.prop-svg {
  width: 100%;
  height: auto;
  display: block;
}

.seg-node {
  fill: var(--color-accent-solid);
}

.seg-next {
  fill: var(--color-sem-solid);
}

.seg-law {
  fill: var(--color-verb-solid);
}

.seg-txt {
  font-family: var(--font-sans);
  font-size: 10px;
  font-weight: 700;
  fill: var(--color-text-on-solid);
}

.law-callout {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.38rem;
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--color-verb-strong);
}

.law-swatch {
  width: 9px;
  height: 9px;
  border-radius: 2px;
  background-color: var(--color-verb-solid);
  flex-shrink: 0;
}
</style>
