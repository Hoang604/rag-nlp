<script setup lang="ts">
import KatexMath from './KatexMath.vue'
</script>

<template>
  <div class="sem-stack">
    <div class="pipe-card">
      <div class="pipe-eyebrow">LUỒNG XỬ LÝ KÊNH NGỮ NGHĨA &amp; TỪ VỰNG</div>
      <svg viewBox="0 0 880 202" class="pipe-svg" role="img" aria-label="Sơ đồ đường ống truy xuất kết hợp Vector ngữ nghĩa, Từ khóa nguyên văn và hợp nhất RRF">
        <defs>
          <marker id="sp-sem" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5.5" markerHeight="5.5" orient="auto-start-reverse">
            <path d="M 0 1 L 10 5 L 0 9 z" class="mk-sem" />
          </marker>
          <marker id="sp-teal" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5.5" markerHeight="5.5" orient="auto-start-reverse">
            <path d="M 0 1 L 10 5 L 0 9 z" class="mk-accent" />
          </marker>
        </defs>

        <!-- Query Input -->
        <rect x="10" y="66" width="102" height="70" rx="10" class="bx-subtle" />
        <text x="61" y="96" text-anchor="middle" class="p-bold">Câu truy vấn</text>
        <text x="61" y="116" text-anchor="middle" class="p-sub">Top K = 10</text>

        <path d="M 112 86 L 138 86 L 138 50 L 164 50" fill="none" class="ln-sem" marker-end="url(#sp-sem)" />
        <path d="M 112 116 L 138 116 L 138 152 L 164 152" fill="none" class="ln-accent" marker-end="url(#sp-teal)" />

        <!-- Top Branch: Qwen3 MRL -->
        <rect x="168" y="14" width="318" height="74" rx="10" class="bx-sem" />
        <text x="184" y="38" class="p-bold sem">1. Kênh Vector Ngữ nghĩa (Qwen3)</text>
        <rect x="184" y="48" width="154" height="26" rx="5" class="vec-kept" />
        <text x="261" y="65" text-anchor="middle" class="vec-txt-on">Giữ 512 chiều (-50% RAM)</text>
        <rect x="342" y="48" width="128" height="26" rx="5" class="vec-cut" />
        <text x="406" y="65" text-anchor="middle" class="vec-txt-off">Bỏ 513..1024</text>

        <!-- Bottom Branch: FTS simple -->
        <rect x="168" y="114" width="318" height="74" rx="10" class="bx-accent" />
        <text x="184" y="138" class="p-bold accent">2. Kênh Từ khóa Nguyên vẹn (FTS simple)</text>
        <rect x="184" y="148" width="144" height="26" rx="5" class="bx-surface" />
        <text x="256" y="165" text-anchor="middle" class="p-sub">Giữ nguyên tên hàm</text>
        <rect x="334" y="148" width="136" height="26" rx="5" class="bx-surface" />
        <text x="402" y="165" text-anchor="middle" class="p-sub">Thưởng từ khóa kề nhau</text>

        <!-- Merge into RRF -->
        <path d="M 486 50 L 516 50 L 516 86 L 542 86" fill="none" class="ln-sem" marker-end="url(#sp-sem)" />
        <path d="M 486 152 L 516 152 L 516 116 L 542 116" fill="none" class="ln-accent" marker-end="url(#sp-teal)" />

        <rect x="546" y="54" width="144" height="94" rx="10" class="bx-subtle" />
        <text x="618" y="84" text-anchor="middle" class="p-bold">Hợp nhất RRF</text>
        <text x="618" y="106" text-anchor="middle" class="p-sub">Cộng thứ hạng hai kênh</text>
        <rect x="564" y="116" width="108" height="22" rx="4" class="bx-accent-badge" />
        <text x="618" y="131" text-anchor="middle" class="p-mono accent">k = 60</text>

        <line x1="690" y1="101" x2="718" y2="101" class="ln-accent" marker-end="url(#sp-teal)" />

        <!-- Cross-Encoder Reranker -->
        <rect x="722" y="54" width="148" height="94" rx="10" class="bx-sem" />
        <text x="796" y="84" text-anchor="middle" class="p-bold sem">Reranker</text>
        <text x="796" y="105" text-anchor="middle" class="p-sub">Chấm lại cặp (q, chunk)</text>
        <text x="796" y="124" text-anchor="middle" class="p-sub">Chọn ra ứng viên tốt nhất</text>
      </svg>
    </div>

    <div class="rrf-strip">
      <div class="rrf-formula">
        <KatexMath
          display
          expr="\operatorname{RRF}(q, c) = \frac{1}{60 + r_{\text{dense}}(c)} + \frac{1}{60 + r_{\text{sparse}}(c)}"
        />
      </div>
      <div class="rrf-note">
        <strong>Vì sao dùng RRF:</strong> Hai kênh có thang điểm khác hẳn nhau; cộng nghịch đảo thứ hạng giúp hòa trộn công bằng mà không cần chỉnh tay trọng số.
      </div>
    </div>
  </div>
</template>

<style scoped>
.sem-stack {
  display: flex;
  flex-direction: column;
  gap: 0.72rem;
}

.pipe-card {
  background-color: var(--color-bg-surface);
  border-radius: var(--radius-lg);
  padding: 0.65rem 0.85rem;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.pipe-eyebrow {
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  color: var(--color-accent-strong);
}

.pipe-svg {
  width: 100%;
  height: auto;
  display: block;
}

.mk-sem {
  fill: var(--color-sem-solid);
}

.mk-accent {
  fill: var(--color-accent-solid);
}

.bx-subtle {
  fill: var(--color-bg-subtle);
}

.bx-surface {
  fill: var(--color-bg-surface);
}

.bx-sem {
  fill: var(--color-sem-tint);
}

.bx-accent {
  fill: var(--color-accent-tint);
}

.bx-accent-badge {
  fill: var(--color-accent-badge);
}

.vec-kept {
  fill: var(--color-sem-solid);
}

.vec-cut {
  fill: var(--color-bg-surface);
  stroke: var(--color-connector-muted);
  stroke-width: 1.2;
  stroke-dasharray: 3 2;
}

.ln-sem {
  stroke: var(--color-sem-solid);
  stroke-width: 2;
}

.ln-accent {
  stroke: var(--color-accent-solid);
  stroke-width: 2;
}

.p-bold {
  font-family: var(--font-sans);
  font-size: 11.5px;
  font-weight: 700;
  fill: var(--color-text-primary);
}

.p-bold.sem {
  fill: var(--color-sem-strong);
}

.p-bold.accent {
  fill: var(--color-accent-strong);
}

.p-sub {
  font-family: var(--font-sans);
  font-size: 10px;
  fill: var(--color-text-secondary);
}

.p-mono {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  fill: var(--color-text-primary);
}

.p-mono.accent {
  fill: var(--color-accent-strong);
}

.vec-txt-on {
  font-family: var(--font-sans);
  font-size: 9.2px;
  font-weight: 700;
  fill: var(--color-text-on-solid);
}

.vec-txt-off {
  font-family: var(--font-sans);
  font-size: 9px;
  fill: var(--color-text-muted);
}

.rrf-strip {
  background-color: var(--color-accent-tint);
  border-radius: var(--radius-lg);
  padding: 0.55rem 0.9rem;
  display: grid;
  grid-template-columns: max-content minmax(0, 1fr);
  align-items: center;
  gap: 1rem;
}

.rrf-formula :deep(.katex-display) {
  margin: 0.1rem 0 !important;
  overflow: visible;
}

.rrf-formula :deep(.katex) {
  font-size: 0.94em;
}

.rrf-note {
  font-size: 0.76rem;
  line-height: 1.45;
  color: var(--color-text-secondary);
}
</style>
