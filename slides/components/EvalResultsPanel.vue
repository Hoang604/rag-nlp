<script setup lang="ts">
interface ChartGroup {
  label: string
  found: number
  r5: number
  ndcg: number
  mrr: number
}

const GROUPS: ReadonlyArray<ChartGroup> = [
  { label: 'TS1-API (50)', found: 98.0, r5: 95.0, ndcg: 89.2, mrr: 82.8 },
  { label: 'TS2-Con (50)', found: 96.0, r5: 90.0, ndcg: 77.4, mrr: 70.2 },
  { label: 'Venn w/o CE', found: 97.0, r5: 92.5, ndcg: 85.0, mrr: 78.9 },
  { label: 'Full Venn', found: 97.0, r5: 92.5, ndcg: 83.3, mrr: 76.5 },
]

const plotTop = 28
const plotBottom = 220
const plotHeight = plotBottom - plotTop
const ticks = [0, 20, 40, 60, 80, 100]

const yOf = (pct: number): number => plotBottom - (pct / 100) * plotHeight
const hOf = (pct: number): number => (pct / 100) * plotHeight
const xCenter = (idx: number): number => 148 + idx * 184
</script>

<template>
  <div class="eval-wrap">
    <section class="chart-card">
      <header class="chart-head">
        <div>
          <div class="col-eyebrow">KẾT QUẢ ĐỘ PHỦ &amp; XẾP HẠNG TRÊN 100 CÂU KIỂM THỬ</div>
          <div class="chart-sub">Trục tung neo tại 0% · Đạt đỉnh 98,0% trên bộ TS1-API</div>
        </div>
        <div class="legend-row">
          <span class="leg"><i class="sw sw-found" />Found</span>
          <span class="leg"><i class="sw sw-r5" />Recall@5</span>
          <span class="leg"><i class="sw sw-ndcg" />NDCG@10</span>
          <span class="leg"><i class="sw sw-mrr" />MRR@10</span>
        </div>
      </header>

      <svg
        viewBox="0 0 820 248"
        class="res-svg"
        role="img"
        aria-label="Biểu đồ cột ghép 4 chỉ số Found, Recall@5, NDCG@10 và MRR@10 trên 4 nhóm đánh giá"
      >
        <g v-for="t in ticks" :key="t">
          <line x1="54" :y1="yOf(t)" x2="796" :y2="yOf(t)" :class="t === 0 ? 'ax-zero' : 'ax-grid'" />
          <text x="46" :y="yOf(t) + 3.5" text-anchor="end" class="y-tick">{{ t }}%</text>
        </g>

        <g v-for="(g, idx) in GROUPS" :key="g.label">
          <rect :x="xCenter(idx) - 61" :y="yOf(g.found)" width="26" :height="hOf(g.found)" rx="3" class="b-found" />
          <rect :x="xCenter(idx) - 29" :y="yOf(g.r5)" width="26" :height="hOf(g.r5)" rx="3" class="b-r5" />
          <rect :x="xCenter(idx) + 3" :y="yOf(g.ndcg)" width="26" :height="hOf(g.ndcg)" rx="3" class="b-ndcg" />
          <rect :x="xCenter(idx) + 35" :y="yOf(g.mrr)" width="26" :height="hOf(g.mrr)" rx="3" class="b-mrr" />

          <text :x="xCenter(idx) - 48" :y="yOf(g.found) - 5" text-anchor="middle" class="val-lbl accent">{{ g.found }}</text>
          <text :x="xCenter(idx) - 16" :y="yOf(g.r5) - 5" text-anchor="middle" class="val-lbl">{{ g.r5 }}</text>
          <text :x="xCenter(idx) + 16" :y="yOf(g.ndcg) - 5" text-anchor="middle" class="val-lbl">{{ g.ndcg }}</text>
          <text :x="xCenter(idx) + 48" :y="yOf(g.mrr) - 5" text-anchor="middle" class="val-lbl">{{ g.mrr }}</text>

          <text :x="xCenter(idx)" y="240" text-anchor="middle" class="x-lbl">{{ g.label }}</text>
        </g>
      </svg>
    </section>

    <div class="scope-callout">
      <span class="pill pill-accent tabular">Node.js: 50/50 = 100%</span>
      <span class="scope-txt">
        3 câu trượt trên Next.js chỉ do chọn phạm vi lọc hẹp lúc tạo truy vấn → đạt <strong>100% (97/97)</strong> khi đúng phạm vi tài liệu.
      </span>
    </div>
  </div>
</template>

<style scoped>
.eval-wrap {
  display: flex;
  flex-direction: column;
  gap: 0.68rem;
}

.chart-card {
  background-color: var(--color-bg-surface);
  border-radius: var(--radius-lg);
  padding: 0.8rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.chart-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.col-eyebrow {
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  color: var(--color-accent-strong);
}

.chart-sub {
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

.leg {
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

.sw-ndcg,
.b-ndcg {
  background-color: var(--color-verb-solid);
  fill: var(--color-verb-solid);
}

.sw-mrr,
.b-mrr {
  background-color: var(--color-axis-line);
  fill: var(--color-axis-line);
}

.res-svg {
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

.val-lbl {
  font-family: var(--font-mono);
  font-size: 9.5px;
  font-weight: 600;
  fill: var(--color-text-secondary);
}

.val-lbl.accent {
  font-weight: 700;
  fill: var(--color-accent-strong);
}

.x-lbl {
  font-family: var(--font-sans);
  font-size: 11.5px;
  font-weight: 700;
  fill: var(--color-text-primary);
}

.scope-callout {
  background-color: var(--color-bg-surface);
  border: 1px solid var(--color-divider-hairline);
  border-radius: var(--radius-md);
  padding: 0.6rem 0.9rem;
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.scope-txt {
  font-size: 0.78rem;
  color: var(--color-text-secondary);
}

.scope-txt strong {
  color: var(--color-text-primary);
}
</style>
