<script setup lang="ts">
</script>

<template>
  <div class="prob-grid">
    <!-- Card 1: One chunking logic for every document format -->
    <section class="prob-card">
      <div class="card-head">
        <span class="eyebrow">ĐIỂM NGHẼN 1 · ĐẦU VÀO ĐỒNG NHẤT</span>
        <h3 class="card-title">Một logic cắt cho mọi loại văn bản</h3>
      </div>

      <div class="stage">
        <svg
          viewBox="0 0 410 156"
          class="diag-svg"
          role="img"
          aria-label="Ba định dạng tài liệu khác nhau đi qua cùng một bộ cắt dẫn tới gãy cấu trúc"
        >
          <defs>
            <marker id="srp-muted" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
              <path d="M 0 1 L 10 5 L 0 9 z" class="mk-muted" />
            </marker>
            <marker id="srp-danger" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
              <path d="M 0 1 L 10 5 L 0 9 z" class="mk-danger" />
            </marker>
          </defs>

          <!-- Diverse input formats -->
          <rect x="6" y="10" width="124" height="38" rx="7" class="bx-surface" />
          <text x="68" y="27" text-anchor="middle" class="nd-bold">Next.js (.mdx)</text>
          <text x="68" y="41" text-anchor="middle" class="nd-sub">Thẻ JSX, router</text>

          <rect x="6" y="59" width="124" height="38" rx="7" class="bx-surface" />
          <text x="68" y="76" text-anchor="middle" class="nd-bold">Node.js (.md)</text>
          <text x="68" y="90" text-anchor="middle" class="nd-sub">API, bảng, code</text>

          <rect x="6" y="108" width="124" height="38" rx="7" class="bx-surface" />
          <text x="68" y="125" text-anchor="middle" class="nd-bold">Luật Bảo hiểm</text>
          <text x="68" y="139" text-anchor="middle" class="nd-sub">Chương · Điều · Khoản</text>

          <!-- Converging lines into single shared splitter -->
          <path d="M 130 29 L 146 29 L 146 78 L 160 78" fill="none" class="ln-muted" />
          <line x1="130" y1="78" x2="158" y2="78" class="ln-muted" marker-end="url(#srp-muted)" />
          <path d="M 130 127 L 146 127 L 146 78 L 160 78" fill="none" class="ln-muted" />

          <!-- Single shared chunking logic -->
          <rect x="162" y="49" width="106" height="58" rx="8" class="bx-surface" />
          <text x="215" y="74" text-anchor="middle" class="nd-bold">1 logic cắt</text>
          <text x="215" y="92" text-anchor="middle" class="nd-sub">giữ nguyên</text>

          <line x1="268" y1="78" x2="290" y2="78" class="ln-danger" marker-end="url(#srp-danger)" />

          <!-- Structural breakage -->
          <rect x="294" y="42" width="110" height="72" rx="8" class="bx-danger" />
          <text x="349" y="69" text-anchor="middle" class="nd-bold danger">Gãy cấu trúc</text>
          <text x="349" y="88" text-anchor="middle" class="nd-sub danger">Vỡ thẻ, đứt khối</text>
          <text x="349" y="102" text-anchor="middle" class="nd-sub danger">Mất phân cấp mục</text>
        </svg>
      </div>

      <div class="takeaway">
        <span class="pill pill-danger">Cắt mù ranh giới đặc thù từng miền</span>
      </div>
    </section>

    <!-- Card 2: Single-shot context stuffed into LLM -->
    <section class="prob-card">
      <div class="card-head">
        <span class="eyebrow">ĐIỂM NGHẼN 2 · ĐẦU RA THỤ ĐỘNG</span>
        <h3 class="card-title">Nhét ngữ cảnh 1 lần, bắt trả lời ngay</h3>
      </div>

      <div class="stage">
        <svg
          viewBox="0 0 410 156"
          class="diag-svg"
          role="img"
          aria-label="Tìm một lượt rồi nhét vào prompt bắt LLM trả lời ngay, gây thiếu thông tin và lãng phí sức mạnh LLM"
        >
          <defs>
            <marker id="srp2-muted" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
              <path d="M 0 1 L 10 5 L 0 9 z" class="mk-muted" />
            </marker>
            <marker id="srp2-danger" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
              <path d="M 0 1 L 10 5 L 0 9 z" class="mk-danger" />
            </marker>
          </defs>

          <!-- Top 3-step one-shot pipeline -->
          <rect x="6" y="12" width="108" height="44" rx="7" class="bx-surface" />
          <text x="60" y="31" text-anchor="middle" class="nd-bold">Tìm 1 lượt</text>
          <text x="60" y="46" text-anchor="middle" class="nd-sub">Lấy sẵn Top-K</text>

          <line x1="114" y1="34" x2="136" y2="34" class="ln-muted" marker-end="url(#srp2-muted)" />

          <rect x="140" y="12" width="122" height="44" rx="7" class="bx-surface" />
          <text x="201" y="31" text-anchor="middle" class="nd-bold">Gói vào Prompt</text>
          <text x="201" y="46" text-anchor="middle" class="nd-sub">Nhét cố định 1 lần</text>

          <line x1="262" y1="34" x2="284" y2="34" class="ln-danger" marker-end="url(#srp2-danger)" />

          <rect x="288" y="12" width="116" height="44" rx="7" class="bx-danger" />
          <text x="346" y="31" text-anchor="middle" class="nd-bold danger">Trả lời ngay</text>
          <text x="346" y="46" text-anchor="middle" class="nd-sub danger">Ép chốt kết quả</text>

          <!-- Divider label -->
          <line x1="205" y1="56" x2="205" y2="74" class="ln-danger" />
          <path d="M 101 88 L 101 74 L 309 74 L 309 88" fill="none" class="ln-danger" marker-start="url(#srp2-danger)" marker-end="url(#srp2-danger)" />

          <!-- Two consequences -->
          <rect x="6" y="92" width="192" height="54" rx="8" class="bx-danger" />
          <text x="102" y="114" text-anchor="middle" class="nd-bold danger">Trượt đầu = cụt dữ liệu</text>
          <text x="102" y="132" text-anchor="middle" class="nd-sub">Không có thông tin để đáp đúng</text>

          <rect x="212" y="92" width="192" height="54" rx="8" class="bx-sem" />
          <text x="308" y="114" text-anchor="middle" class="nd-bold sem">Bỏ phí sức mạnh LLM</text>
          <text x="308" y="132" text-anchor="middle" class="nd-sub">Chỉ đọc chép, không tự tìm tiếp</text>
        </svg>
      </div>

      <div class="takeaway">
        <span class="pill pill-danger">Thiếu dữ kiện nếu tìm sai lượt đầu</span>
        <span class="pill pill-sem">Không tận dụng suy luận LLM</span>
      </div>
    </section>
  </div>
</template>

<style scoped>
.prob-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.9rem;
  align-items: stretch;
}

.prob-card {
  background-color: var(--color-bg-surface);
  border-radius: var(--radius-lg);
  padding: 0.95rem 1.05rem;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 0.72rem;
}

.card-head {
  display: flex;
  flex-direction: column;
  gap: 0.18rem;
}

.eyebrow {
  font-size: 0.66rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  color: var(--color-danger-strong);
}

.card-title {
  font-size: 0.96rem;
  font-weight: 700;
  color: var(--color-text-primary);
}

.stage {
  background-color: var(--color-bg-subtle);
  border-radius: var(--radius-md);
  padding: 0.68rem 0.72rem;
  flex: 1;
  display: flex;
  align-items: center;
}

.diag-svg {
  width: 100%;
  height: auto;
  display: block;
}

.bx-surface {
  fill: var(--color-bg-surface);
}

.bx-danger {
  fill: var(--color-danger-tint);
}

.bx-sem {
  fill: var(--color-sem-tint);
}

.ln-muted {
  stroke: var(--color-axis-line);
  stroke-width: 1.7;
}

.ln-danger {
  stroke: var(--color-danger-solid);
  stroke-width: 1.8;
  stroke-dasharray: 4 3;
}

.mk-muted {
  fill: var(--color-axis-line);
}

.mk-danger {
  fill: var(--color-danger-solid);
}

.nd-bold {
  font-family: var(--font-sans);
  font-size: 11px;
  font-weight: 700;
  fill: var(--color-text-primary);
}

.nd-bold.danger {
  fill: var(--color-danger-strong);
}

.nd-bold.sem {
  fill: var(--color-sem-strong);
}

.nd-sub {
  font-family: var(--font-sans);
  font-size: 9.5px;
  fill: var(--color-text-secondary);
}

.nd-sub.danger {
  fill: var(--color-danger-strong);
}

.takeaway {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}

.pill-danger {
  background-color: var(--color-danger-badge);
  color: var(--color-danger-strong);
}
</style>
