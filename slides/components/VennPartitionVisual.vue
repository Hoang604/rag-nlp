<script setup lang="ts">
</script>

<template>
  <div class="venn-wrap">
    <div class="venn-card">
      <div class="venn-head">
        <span class="eyebrow">PHÂN HOẠCH KÊNH ĐÔI TRÊN 100 CÂU KIỂM THỬ</span>
        <span class="pill pill-accent tabular">97/97 = 100% khi lọc đúng phạm vi</span>
      </div>

      <svg viewBox="0 0 820 226" class="venn-svg" role="img" aria-label="Biểu đồ Venn phân hoạch 3 nhóm kết quả giữa kênh ngữ nghĩa và kênh nguyên văn">
        <!-- Exact intersecting circles: cx1=348, cx2=472, cy=120, r=96 (d=124, h=73.24) -->
        <circle cx="348" cy="120" r="96" class="c-sem" />
        <circle cx="472" cy="120" r="96" class="c-verb" />
        <path d="M 410 46.76 A 96 96 0 0 1 410 193.24 A 96 96 0 0 1 410 46.76 Z" class="c-both" />

        <!-- Left Crescent: Semantic Only (x=252..376, mid=310) -->
        <text x="310" y="96" text-anchor="middle" class="v-rank">Ưu tiên #2</text>
        <text x="310" y="123" text-anchor="middle" class="v-num sem">10 câu</text>
        <text x="310" y="143" text-anchor="middle" class="v-lbl">Chỉ khớp</text>
        <text x="310" y="157" text-anchor="middle" class="v-lbl">Ngữ nghĩa</text>

        <!-- Center Lens Intersection: Both (x=376..444, y=46.76..193.24) -->
        <text x="410" y="18" text-anchor="middle" class="v-rank both">Ưu tiên #1 · Khớp đồng thời cả 2 kênh</text>
        <line x1="410" y1="22" x2="410" y2="44" class="ln-both" />
        <text x="410" y="125" text-anchor="middle" class="v-num both">85 câu</text>

        <!-- Right Crescent: Verbatim Only (x=444..568, mid=510) -->
        <text x="510" y="96" text-anchor="middle" class="v-rank">Ưu tiên #3</text>
        <text x="510" y="123" text-anchor="middle" class="v-num verb">2 câu</text>
        <text x="510" y="143" text-anchor="middle" class="v-lbl">Chỉ khớp</text>
        <text x="510" y="157" text-anchor="middle" class="v-lbl">Nguyên văn</text>

        <!-- Side Callouts (gap >= 44px from circle outer edge) -->
        <rect x="14" y="78" width="194" height="84" rx="10" class="bx-subtle" />
        <text x="28" y="104" class="note-title sem">Kênh Ngữ nghĩa (RRF)</text>
        <text x="28" y="124" class="note-sub">Tìm tốt câu hỏi khái niệm,</text>
        <text x="28" y="141" class="note-sub">diễn đạt gián tiếp</text>

        <rect x="612" y="78" width="194" height="84" rx="10" class="bx-subtle" />
        <text x="626" y="104" class="note-title verb">Kênh Nguyên văn</text>
        <text x="626" y="124" class="note-sub">Cứu ký hiệu đặc thù khi</text>
        <text x="626" y="141" class="note-sub">tìm ngữ nghĩa bị trượt</text>
      </svg>
    </div>
  </div>
</template>

<style scoped>
.venn-wrap {
  display: flex;
  flex-direction: column;
}

.venn-card {
  background-color: var(--color-bg-surface);
  border-radius: var(--radius-lg);
  padding: 0.95rem 1.05rem;
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.venn-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.eyebrow {
  font-size: 0.66rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  color: var(--color-accent-strong);
}

.venn-svg {
  width: 100%;
  height: auto;
  display: block;
}

.c-sem {
  fill: var(--color-sem-tint);
  stroke: var(--color-sem-solid);
  stroke-width: 2;
}

.c-verb {
  fill: var(--color-verb-tint);
  fill-opacity: 0.86;
  stroke: var(--color-verb-solid);
  stroke-width: 2;
}

.c-both {
  fill: var(--color-accent-badge);
  stroke: var(--color-accent-solid);
  stroke-width: 2;
}

.ln-both {
  stroke: var(--color-accent-solid);
  stroke-width: 1.6;
}

.v-rank {
  font-family: var(--font-sans);
  font-size: 10.5px;
  font-weight: 700;
  fill: var(--color-text-muted);
}

.v-rank.both {
  fill: var(--color-accent-strong);
}

.v-num {
  font-family: var(--font-sans);
  font-size: 18px;
  font-weight: 700;
}

.v-num.sem {
  fill: var(--color-sem-strong);
}

.v-num.both {
  fill: var(--color-accent-strong);
}

.v-num.verb {
  fill: var(--color-verb-strong);
}

.v-lbl {
  font-family: var(--font-sans);
  font-size: 10px;
  fill: var(--color-text-secondary);
}

.bx-subtle {
  fill: var(--color-bg-subtle);
}

.note-title {
  font-family: var(--font-sans);
  font-size: 11px;
  font-weight: 700;
}

.note-title.sem {
  fill: var(--color-sem-strong);
}

.note-title.verb {
  fill: var(--color-verb-strong);
}

.note-sub {
  font-family: var(--font-sans);
  font-size: 10px;
  fill: var(--color-text-secondary);
}
</style>
