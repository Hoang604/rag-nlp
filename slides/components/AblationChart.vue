<script setup lang="ts">
interface AblationItem {
  short: string
  found: number
  r5: number
  mrr: number
  hit1: number
}

const DATA: ReadonlyArray<AblationItem> = [
  { short: '(0) No-Ctx', found: 86.0, r5: 84.0, mrr: 70.3, hit1: 58.0 },
  { short: '(1) Sparse', found: 88.0, r5: 86.0, mrr: 72.9, hit1: 60.0 },
  { short: '(2) Dense', found: 95.0, r5: 91.0, mrr: 71.9, hit1: 59.0 },
  { short: '(3) RRF', found: 95.0, r5: 93.0, mrr: 79.0, hit1: 68.0 },
  { short: '(4) +Rerank', found: 95.0, r5: 89.5, mrr: 70.7, hit1: 58.0 },
  { short: '(5) Venn', found: 97.0, r5: 92.5, mrr: 78.9, hit1: 68.0 },
  { short: '(6) Full Venn', found: 97.0, r5: 92.5, mrr: 76.5, hit1: 64.0 },
]

const plotTop = 26
const plotBottom = 216
const plotHeight = plotBottom - plotTop
const ticks = [0, 20, 40, 60, 80, 100]

const yOf = (pct: number): number => plotBottom - (pct / 100) * plotHeight
const hOf = (pct: number): number => (pct / 100) * plotHeight
const xGroup = (idx: number): number => 106 + idx * 110
</script>

<template>
  <div class="abl-wrap">
    <div class="abl-card">
      <div class="abl-head">
        <div>
          <span class="eyebrow">PHÂN TÍCH ABLATION 7 CẤU HÌNH (100 CÂU HỎI)</span>
          <div class="abl-sub">Đo đóng góp từng thành phần lên độ phủ và thứ hạng trả về</div>
        </div>
        <div class="legend-row">
          <span class="leg-item"><i class="sw sw-found" />Found</span>
          <span class="leg-item"><i class="sw sw-r5" />Recall@5</span>
          <span class="leg-item"><i class="sw sw-mrr" />MRR@10</span>
          <span class="leg-item"><i class="sw sw-hit1" />Hit@1</span>
        </div>
      </div>

      <svg
        viewBox="0 0 820 242"
        class="abl-svg"
        role="img"
        aria-label="Biểu đồ cột so sánh 7 cấu hình Ablation với 4 chỉ số Found, Recall@5, MRR@10 và Hit@1"
      >
        <g v-for="t in ticks" :key="t">
          <line x1="48" :y1="yOf(t)" x2="796" :y2="yOf(t)" :class="t === 0 ? 'ax-zero' : 'ax-grid'" />
          <text x="40" :y="yOf(t) + 3.5" text-anchor="end" class="y-tick">{{ t }}%</text>
        </g>

        <g v-for="(d, idx) in DATA" :key="d.short">
          <rect :x="xGroup(idx) - 34" :y="yOf(d.found)" width="15" :height="hOf(d.found)" rx="2" class="b-found" />
          <rect :x="xGroup(idx) - 16" :y="yOf(d.r5)" width="15" :height="hOf(d.r5)" rx="2" class="b-r5" />
          <rect :x="xGroup(idx) + 2" :y="yOf(d.mrr)" width="15" :height="hOf(d.mrr)" rx="2" class="b-mrr" />
          <rect :x="xGroup(idx) + 20" :y="yOf(d.hit1)" width="15" :height="hOf(d.hit1)" rx="2" class="b-hit1" />

          <text :x="xGroup(idx) - 26.5" :y="yOf(d.found) - 5" text-anchor="middle" class="top-val">{{ d.found }}</text>
          <text :x="xGroup(idx)" y="235" text-anchor="middle" class="x-lbl">{{ d.short }}</text>
        </g>
      </svg>
    </div>

    <div class="abl-summary">
      <span class="pill pill-accent tabular">86% → 95% → 97%</span>
      <span class="summary-txt">
        Tiền tố ngữ cảnh cha và tìm kiếm ngữ nghĩa đưa độ phủ lên <strong>95%</strong>; kênh Venn nâng lên <strong>97%</strong>.
      </span>
    </div>
  </div>
</template>

<style scoped>
.abl-wrap {
  display: flex;
  flex-direction: column;
  gap: 0.68rem;
}

.abl-card {
  background-color: var(--color-bg-surface);
  border-radius: var(--radius-lg);
  padding: 0.8rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.abl-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.eyebrow {
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  color: var(--color-accent-strong);
}

.abl-sub {
  font-size: 0.72rem;
  color: var(--color-text-muted);
}

.legend-row {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--color-text-secondary);
}

.leg-item {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
}

.sw {
  display: inline-block;
  width: 9.5px;
  height: 9.5px;
  border-radius: 2px;
}

.sw-found,
.b-found {
  background-color: var(--color-accent-solid);
  fill: var(--color-accent-solid);
}

.sw-r5,
.b-r5 {
  background-color: var(--color-sem-solid);
  fill: var(--color-sem-solid);
}

.sw-mrr,
.b-mrr {
  background-color: var(--color-verb-solid);
  fill: var(--color-verb-solid);
}

.sw-hit1,
.b-hit1 {
  background-color: var(--color-axis-line);
  fill: var(--color-axis-line);
}

.abl-svg {
  width: 100%;
  height: auto;
  display: block;
}

.ax-zero {
  stroke: var(--color-axis-line);
  stroke-width: 1.4;
}

.ax-grid {
  stroke: var(--color-grid-line);
  stroke-width: 1;
}

.y-tick {
  font-family: var(--font-mono);
  font-size: 10px;
  fill: var(--color-text-muted);
}

.top-val {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  fill: var(--color-accent-strong);
}

.x-lbl {
  font-family: var(--font-sans);
  font-size: 11px;
  font-weight: 700;
  fill: var(--color-text-primary);
}

.abl-summary {
  background-color: var(--color-bg-surface);
  border: 1px solid var(--color-divider-hairline);
  border-radius: var(--radius-md);
  padding: 0.6rem 0.9rem;
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.summary-txt {
  font-size: 0.78rem;
  color: var(--color-text-secondary);
}

.summary-txt strong {
  color: var(--color-text-primary);
}
</style>
