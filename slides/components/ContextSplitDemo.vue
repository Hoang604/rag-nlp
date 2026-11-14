<script setup lang="ts">
</script>

<template>
  <div class="ctx-canvas">
    <svg viewBox="0 0 880 300" class="ctx-svg" role="img" aria-label="Sơ đồ phân tách biểu diễn lúc Indexing và lúc trả kết quả cho Coding Agent">
      <defs>
        <marker id="cs-sem" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 1 L 10 5 L 0 9 z" class="mk-sem" />
        </marker>
        <marker id="cs-teal" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 1 L 10 5 L 0 9 z" class="mk-accent" />
        </marker>
      </defs>

      <!-- Left Source AST Chunk -->
      <rect x="10" y="64" width="250" height="172" rx="12" class="bx-surface" />
      <text x="24" y="88" class="eyebrow-muted">PHÂN ĐOẠN GỐC TỪ TỆP NGUỒN</text>
      <text x="24" y="108" class="mono-title">15_route_handlers.mdx (L87–144)</text>

      <rect x="22" y="120" width="226" height="68" rx="7" class="bx-subtle" />
      <text x="32" y="139" class="code-bold">#### With Cache Components</text>
      <text x="32" y="156" class="code-line">By default, Route Handlers are</text>
      <text x="32" y="172" class="code-line">dynamic... marked 'use cache'</text>

      <rect x="22" y="198" width="226" height="26" rx="5" class="bx-danger" />
      <text x="135" y="215" text-anchor="middle" class="warn-txt">Tiêu đề con trùng tên ở nhiều tài liệu</text>

      <!-- Bifurcation Connectors -->
      <path d="M 260 122 L 296 122 L 296 76 L 330 76" fill="none" class="ln-sem" marker-end="url(#cs-sem)" />
      <path d="M 260 178 L 296 178 L 296 224 L 330 224" fill="none" class="ln-accent" marker-end="url(#cs-teal)" />

      <!-- Top Right Track: Indexing Representation -->
      <rect x="334" y="10" width="536" height="130" rx="12" class="bx-sem" />
      <text x="350" y="32" class="eyebrow-sem">NHÁNH 1 · BIỂU DIỄN LÚC INDEXING &amp; CHẤM ĐIỂM</text>

      <rect x="350" y="42" width="504" height="26" rx="5" class="bx-sem-badge" />
      <text x="360" y="59" class="prefix-txt">[Route Handlers &gt; Caching &gt; With Cache Components]</text>

      <rect x="350" y="72" width="318" height="54" rx="6" class="bx-surface" />
      <text x="360" y="91" class="code-bold">#### With Cache Components</text>
      <text x="360" y="109" class="code-line">By default, Route Handlers are dynamic...</text>

      <rect x="680" y="72" width="174" height="54" rx="6" class="bx-surface" />
      <text x="767" y="95" text-anchor="middle" class="out-bold sem">Khử nhập nhằng ngữ cảnh</text>
      <text x="767" y="113" text-anchor="middle" class="out-sub">Tìm đúng mục cha khi xếp hạng</text>

      <!-- Bottom Right Track: Agent Output Representation -->
      <rect x="334" y="160" width="536" height="130" rx="12" class="bx-accent" />
      <text x="350" y="182" class="eyebrow-accent">NHÁNH 2 · BIỂU DIỄN TRẢ VỀ CHO CODING AGENT</text>

      <rect x="350" y="192" width="504" height="26" rx="5" class="bx-accent-badge" />
      <text x="360" y="209" class="group-txt">Nhóm theo mục cha: Route Handlers &gt; Caching (chỉ ghi tiêu đề 1 lần)</text>

      <rect x="350" y="224" width="246" height="52" rx="6" class="bx-surface" />
      <text x="360" y="243" class="code-bold accent">L62–85 · Văn bản gốc</text>
      <text x="360" y="261" class="out-sub">Đoạn mở đầu mục Caching (0 lặp)</text>

      <rect x="608" y="224" width="246" height="52" rx="6" class="bx-surface" />
      <text x="618" y="243" class="code-bold accent">L87–144 · Văn bản gốc</text>
      <text x="618" y="261" class="out-sub">Mục With Cache Components liền mạch</text>
    </svg>

    <div class="order-strip">
      <span class="pill pill-accent">Bảo toàn mạch đọc tự nhiên</span>
      <span class="order-desc">
        Nhóm liên quan nhất được đặt lên đầu; các đoạn bên trong cùng một nhóm được sắp lại theo đúng <strong>thứ tự dòng xuất hiện trong tệp gốc</strong> và loại bỏ tiền tố lặp thừa.
      </span>
    </div>
  </div>
</template>

<style scoped>
.ctx-canvas {
  display: flex;
  flex-direction: column;
  gap: 0.48rem;
}

.ctx-svg {
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

.bx-surface {
  fill: var(--color-bg-surface);
}

.bx-subtle {
  fill: var(--color-bg-subtle);
}

.bx-danger {
  fill: var(--color-danger-tint);
}

.bx-sem {
  fill: var(--color-sem-tint);
}

.bx-sem-badge {
  fill: var(--color-sem-badge);
}

.bx-accent {
  fill: var(--color-accent-tint);
}

.bx-accent-badge {
  fill: var(--color-accent-badge);
}

.ln-sem {
  stroke: var(--color-sem-solid);
  stroke-width: 2.1;
}

.ln-accent {
  stroke: var(--color-accent-solid);
  stroke-width: 2.1;
}

.eyebrow-muted {
  font-family: var(--font-sans);
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.05em;
  fill: var(--color-text-muted);
}

.eyebrow-sem {
  font-family: var(--font-sans);
  font-size: 9.5px;
  font-weight: 700;
  letter-spacing: 0.04em;
  fill: var(--color-sem-strong);
}

.eyebrow-accent {
  font-family: var(--font-sans);
  font-size: 9.5px;
  font-weight: 700;
  letter-spacing: 0.04em;
  fill: var(--color-accent-strong);
}

.mono-title {
  font-family: var(--font-mono);
  font-size: 10.5px;
  font-weight: 700;
  fill: var(--color-text-primary);
}

.code-bold {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  fill: var(--color-text-primary);
}

.code-bold.accent {
  fill: var(--color-accent-strong);
}

.code-line {
  font-family: var(--font-mono);
  font-size: 9.3px;
  fill: var(--color-text-secondary);
}

.warn-txt {
  font-family: var(--font-sans);
  font-size: 9.5px;
  font-weight: 700;
  fill: var(--color-danger-strong);
}

.prefix-txt {
  font-family: var(--font-mono);
  font-size: 9.6px;
  font-weight: 700;
  fill: var(--color-sem-strong);
}

.group-txt {
  font-family: var(--font-mono);
  font-size: 8.9px;
  font-weight: 700;
  fill: var(--color-accent-strong);
}

.out-bold {
  font-family: var(--font-sans);
  font-size: 10px;
  font-weight: 700;
}

.out-bold.sem {
  fill: var(--color-sem-strong);
}

.out-sub {
  font-family: var(--font-sans);
  font-size: 9.2px;
  fill: var(--color-text-secondary);
}

.order-strip {
  background-color: var(--color-bg-surface);
  border-radius: var(--radius-md);
  padding: 0.44rem 0.78rem;
  display: flex;
  align-items: center;
  gap: 0.65rem;
}

.order-desc {
  font-size: 0.73rem;
  color: var(--color-text-secondary);
}
</style>
