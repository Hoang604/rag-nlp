<script setup lang="ts">
</script>

<template>
  <div class="gate-wrap">
    <div class="gate-card">
      <div class="gate-head">
        <span class="eyebrow">MA TRẬN CỔNG KIỂM SOÁT TIN CẬY (CONFIDENCE GATE)</span>
        <span class="pill pill-accent">Hợp nhất 2 kênh → 4 nhãn tường minh</span>
      </div>

      <svg
        viewBox="0 0 820 212"
        class="gate-svg"
        role="img"
        aria-label="Ma trận kết hợp xác nhận từ khóa và độ khớp ngữ nghĩa qua Reranker để xuất nhãn high, medium, low hoặc none"
      >
        <!-- Column Headers -->
        <text x="314" y="20" text-anchor="middle" class="col-hdr">Ngữ nghĩa rất khớp</text>
        <text x="314" y="34" text-anchor="middle" class="col-sub">Qua bước kiểm tra lại</text>

        <text x="514" y="20" text-anchor="middle" class="col-hdr">Ngữ nghĩa khá khớp</text>
        <text x="514" y="34" text-anchor="middle" class="col-sub">Qua bước kiểm tra lại</text>

        <text x="714" y="20" text-anchor="middle" class="col-hdr">Ngữ nghĩa yếu / bị loại</text>
        <text x="714" y="34" text-anchor="middle" class="col-sub">Yếu hoặc bị Reranker hạ</text>

        <!-- Row 1 Header -->
        <rect x="12" y="48" width="194" height="72" rx="10" class="bx-subtle" />
        <text x="109" y="78" text-anchor="middle" class="row-hdr">Có từ khóa</text>
        <text x="109" y="98" text-anchor="middle" class="row-sub">Hai kênh cùng xác nhận</text>

        <!-- Row 2 Header -->
        <rect x="12" y="130" width="194" height="72" rx="10" class="bx-subtle" />
        <text x="109" y="160" text-anchor="middle" class="row-hdr">Không có từ khóa</text>
        <text x="109" y="180" text-anchor="middle" class="row-sub">Chỉ dựa vào ngữ nghĩa</text>

        <!-- Row 1 Cells -->
        <rect x="220" y="48" width="188" height="72" rx="10" class="cell-high" />
        <text x="314" y="78" text-anchor="middle" class="c-tag high">HIGH</text>
        <text x="314" y="100" text-anchor="middle" class="c-desc">Đủ 2 kênh · Tin cậy cao</text>

        <rect x="420" y="48" width="188" height="72" rx="10" class="cell-med" />
        <text x="514" y="78" text-anchor="middle" class="c-tag med">MEDIUM</text>
        <text x="514" y="100" text-anchor="middle" class="c-desc">Đọc thêm bối cảnh</text>

        <rect x="620" y="48" width="188" height="72" rx="10" class="cell-low" />
        <text x="714" y="78" text-anchor="middle" class="c-tag low">LOW</text>
        <text x="714" y="100" text-anchor="middle" class="c-desc">Chứng cứ yếu · Tự kiểm tra</text>

        <!-- Row 2 Cells (merged LOW across strong/moderate semantic when keyword is absent) -->
        <rect x="220" y="130" width="388" height="72" rx="10" class="cell-low" />
        <text x="414" y="160" text-anchor="middle" class="c-tag low">LOW</text>
        <text x="414" y="182" text-anchor="middle" class="c-desc">Khóa trần do thiếu từ khóa xác nhận</text>

        <rect x="620" y="130" width="188" height="72" rx="10" class="cell-none" />
        <text x="714" y="160" text-anchor="middle" class="c-tag none">NONE</text>
        <text x="714" y="182" text-anchor="middle" class="c-desc">Chặn · Không đoán mò</text>
      </svg>
    </div>

    <div class="gate-summary">
      <span class="pill pill-accent tabular">Thực nghiệm 100 câu</span>
      <span class="summary-text">
        <strong>11%</strong> <code>high</code> · <strong>61%</strong> <code>medium</code> · <strong>28%</strong> <code>low</code> · <strong>0%</strong> <code>none</code> (Reranker tự hạ 1 ca yếu từ <code>medium</code> xuống <code>low</code>)
      </span>
    </div>
  </div>
</template>

<style scoped>
.gate-wrap {
  display: flex;
  flex-direction: column;
  gap: 0.72rem;
}

.gate-card {
  background-color: var(--color-bg-surface);
  border-radius: var(--radius-lg);
  padding: 0.85rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}

.gate-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.eyebrow {
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  color: var(--color-accent-strong);
}

.gate-svg {
  width: 100%;
  height: auto;
  display: block;
}

.col-hdr {
  font-size: 13px;
  font-weight: 700;
  fill: var(--color-text-primary);
}

.col-sub {
  font-size: 10.5px;
  font-weight: 500;
  fill: var(--color-text-muted);
}

.bx-subtle {
  fill: var(--color-bg-subtle);
  stroke: var(--color-divider-hairline);
  stroke-width: 1.4;
}

.row-hdr {
  font-size: 13.5px;
  font-weight: 700;
  fill: var(--color-text-primary);
}

.row-sub {
  font-size: 11px;
  font-weight: 500;
  fill: var(--color-text-muted);
}

.cell-high {
  fill: var(--color-accent-tint);
  stroke: var(--color-accent-solid);
  stroke-width: 2;
}

.cell-med {
  fill: var(--color-sem-tint);
  stroke: var(--color-sem-solid);
  stroke-width: 1.75;
}

.cell-low {
  fill: var(--color-verb-tint);
  stroke: var(--color-verb-solid);
  stroke-width: 1.75;
}

.cell-none {
  fill: var(--color-danger-tint);
  stroke: var(--color-danger-solid);
  stroke-width: 1.75;
}

.c-tag {
  font-size: 15px;
  font-weight: 700;
  font-family: var(--font-mono);
}

.c-tag.high {
  fill: var(--color-accent-strong);
}

.c-tag.med {
  fill: var(--color-sem-strong);
}

.c-tag.low {
  fill: var(--color-verb-strong);
}

.c-tag.none {
  fill: var(--color-danger-strong);
}

.c-desc {
  font-size: 11.5px;
  font-weight: 500;
  fill: var(--color-text-secondary);
}

.gate-summary {
  background-color: var(--color-bg-surface);
  border: 1px solid var(--color-divider-hairline);
  border-radius: var(--radius-md);
  padding: 0.62rem 0.9rem;
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.summary-text {
  font-size: 0.78rem;
  color: var(--color-text-secondary);
}

.summary-text strong {
  color: var(--color-text-primary);
}

.summary-text code {
  font-family: var(--font-mono);
  font-size: 0.74rem;
  background-color: var(--color-bg-subtle);
  padding: 0.08rem 0.34rem;
  border-radius: var(--radius-sm);
  color: var(--color-text-primary);
}
</style>
