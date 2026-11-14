<script setup lang="ts">
</script>

<template>
  <div class="arch-wrap">
    <svg viewBox="0 0 880 340" class="arch-svg" role="img" aria-label="Kiến trúc tổng thể hệ thống RAG động hai pha trên PostgreSQL 16">
      <defs>
        <marker id="arr-teal" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 1 L 10 5 L 0 9 z" class="mk-accent" />
        </marker>
        <marker id="arr-indigo" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 1 L 10 5 L 0 9 z" class="mk-sem" />
        </marker>
      </defs>

      <!-- Column Headers -->
      <text x="18" y="20" class="col-lbl">1 · PHA NẠP TÀI LIỆU (INGESTION)</text>
      <text x="330" y="20" class="col-lbl">2 · KHO LƯU TRỮ TRUNG TÂM</text>
      <text x="598" y="20" class="col-lbl">3 · PHA THỰC THI (RUNTIME AGENT)</text>

      <!-- Left Column: Steps 1-4 -->
      <rect x="14" y="34" width="256" height="62" rx="10" class="nd-surface" />
      <text x="28" y="56" class="node-step">01 · Tài liệu gốc có cấu trúc</text>
      <text x="28" y="76" class="node-sub">Tài liệu kỹ thuật &amp; văn bản pháp quy</text>

      <rect x="14" y="112" width="256" height="62" rx="10" class="nd-accent" />
      <text x="28" y="134" class="node-step accent">02 · Bộ Parser chuyên biệt</text>
      <text x="28" y="154" class="node-sub">Tách theo cấu trúc, không cắt mù</text>

      <rect x="14" y="190" width="256" height="62" rx="10" class="nd-accent" />
      <text x="28" y="212" class="node-step accent">03 · Kiểm định biên nạp DB</text>
      <text x="28" y="232" class="node-sub">Khóa ltree, biên dòng rời &amp; ngữ cảnh</text>

      <rect x="14" y="268" width="256" height="62" rx="10" class="nd-surface" />
      <text x="28" y="290" class="node-step">04 · Tạo chỉ mục kép</text>
      <text x="28" y="310" class="node-sub">Vector ngữ nghĩa &amp; chỉ mục từ khóa</text>

      <!-- Vertical Arrows Left -->
      <line x1="142" y1="96" x2="142" y2="109" class="st-accent" marker-end="url(#arr-teal)" />
      <line x1="142" y1="174" x2="142" y2="187" class="st-accent" marker-end="url(#arr-teal)" />
      <line x1="142" y1="252" x2="142" y2="265" class="st-accent" marker-end="url(#arr-teal)" />

      <!-- Center PostgreSQL Hub -->
      <rect x="322" y="54" width="228" height="256" rx="14" class="nd-surface" />
      <rect x="336" y="68" width="200" height="42" rx="8" class="nd-solid-accent" />
      <text x="436" y="88" text-anchor="middle" class="db-title">PostgreSQL 16</text>
      <text x="436" y="103" text-anchor="middle" class="db-sub">Lưu trữ hợp nhất</text>

      <rect x="336" y="120" width="200" height="38" rx="7" class="nd-subtle" />
      <text x="348" y="138" class="idx-name">Vector Ngữ nghĩa</text>
      <text x="348" y="152" class="idx-sub">Tìm theo ý nghĩa câu hỏi</text>

      <rect x="336" y="166" width="200" height="38" rx="7" class="nd-subtle" />
      <text x="348" y="184" class="idx-name">Cây Mục lục (ltree)</text>
      <text x="348" y="198" class="idx-sub">Duyệt cha – con – anh em</text>

      <rect x="336" y="212" width="200" height="38" rx="7" class="nd-subtle" />
      <text x="348" y="230" class="idx-name">Từ khóa &amp; Ký tự nguyên văn</text>
      <text x="348" y="244" class="idx-sub">Khớp tên hàm, ký hiệu, mã điều</text>

      <rect x="336" y="258" width="200" height="38" rx="7" class="nd-accent" />
      <text x="348" y="276" class="idx-name accent">Knowledge Graph &amp; Kiểm chứng</text>
      <text x="348" y="290" class="idx-sub">Liên kết chéo &amp; đối chiếu nguồn</text>

      <!-- Ingestion -> DB Arrows -->
      <path d="M 270 221 L 318 221" class="st-accent-w" marker-end="url(#arr-teal)" />
      <path d="M 270 299 L 298 299 L 298 139 L 318 139" fill="none" class="st-accent-w" marker-end="url(#arr-teal)" />

      <!-- Right Column: Steps 5-8 -->
      <rect x="586" y="34" width="282" height="62" rx="10" class="nd-sem" />
      <text x="600" y="56" class="node-step sem">05 · Coding Agent chủ động</text>
      <text x="600" y="76" class="node-sub">Điều tra nhiều vòng qua giao thức MCP</text>

      <rect x="586" y="112" width="282" height="62" rx="10" class="nd-surface" />
      <text x="600" y="134" class="node-step">06 · Truy xuất kênh đôi</text>
      <text x="600" y="154" class="node-sub">Kết hợp tìm ngữ nghĩa và tìm nguyên văn</text>

      <rect x="586" y="190" width="282" height="62" rx="10" class="nd-surface" />
      <text x="600" y="212" class="node-step">07 · Mở rộng &amp; đọc dòng gốc</text>
      <text x="600" y="232" class="node-sub">Leo cây mục lục, đọc file, đi đồ thị</text>

      <rect x="586" y="268" width="282" height="62" rx="10" class="nd-accent" />
      <text x="600" y="290" class="node-step accent">08 · Xác thực &amp; trả lời</text>
      <text x="600" y="310" class="node-sub">Chặn trích dẫn sai trước khi trả về</text>

      <!-- Bidirectional Runtime Arrows -->
      <line x1="727" y1="96" x2="727" y2="109" class="st-sem" marker-end="url(#arr-indigo)" />
      <line x1="727" y1="174" x2="727" y2="187" class="st-sem" marker-end="url(#arr-indigo)" />
      <line x1="727" y1="252" x2="727" y2="265" class="st-accent" marker-end="url(#arr-teal)" />

      <line x1="552" y1="143" x2="582" y2="143" class="st-sem-w" marker-start="url(#arr-indigo)" marker-end="url(#arr-indigo)" />
      <line x1="552" y1="221" x2="582" y2="221" class="st-sem-w" marker-start="url(#arr-indigo)" marker-end="url(#arr-indigo)" />
      <line x1="584" y1="295" x2="554" y2="295" class="st-accent-dash" marker-end="url(#arr-teal)" />
    </svg>
  </div>
</template>

<style scoped>
.arch-wrap {
  background-color: var(--color-bg-subtle);
  border-radius: var(--radius-lg);
  padding: 0.45rem 0.65rem;
}

.arch-svg {
  width: 100%;
  height: auto;
  max-height: 342px;
  display: block;
}

.mk-accent {
  fill: var(--color-accent-solid);
}

.mk-sem {
  fill: var(--color-sem-solid);
}

.nd-surface {
  fill: var(--color-bg-surface);
}

.nd-subtle {
  fill: var(--color-bg-subtle);
}

.nd-accent {
  fill: var(--color-accent-tint);
}

.nd-sem {
  fill: var(--color-sem-tint);
}

.nd-solid-accent {
  fill: var(--color-accent-solid);
}

.st-accent {
  stroke: var(--color-accent-solid);
  stroke-width: 1.8;
}

.st-accent-w {
  stroke: var(--color-accent-solid);
  stroke-width: 2;
}

.st-accent-dash {
  stroke: var(--color-accent-solid);
  stroke-width: 1.9;
  stroke-dasharray: 4 3;
}

.st-sem {
  stroke: var(--color-sem-solid);
  stroke-width: 1.8;
}

.st-sem-w {
  stroke: var(--color-sem-solid);
  stroke-width: 1.9;
}

.col-lbl {
  font-family: var(--font-sans);
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: 0.05em;
  fill: var(--color-text-muted);
}

.node-step {
  font-family: var(--font-sans);
  font-size: 12.5px;
  font-weight: 700;
  fill: var(--color-text-primary);
}

.node-step.accent {
  fill: var(--color-accent-strong);
}

.node-step.sem {
  fill: var(--color-sem-strong);
}

.node-sub {
  font-family: var(--font-sans);
  font-size: 11px;
  fill: var(--color-text-secondary);
}

.db-title {
  font-family: var(--font-sans);
  font-size: 13.5px;
  font-weight: 700;
  fill: var(--color-text-on-solid);
}

.db-sub {
  font-family: var(--font-sans);
  font-size: 10.5px;
  fill: var(--color-accent-badge);
}

.idx-name {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  fill: var(--color-text-primary);
}

.idx-name.accent {
  fill: var(--color-accent-strong);
}

.idx-sub {
  font-family: var(--font-sans);
  font-size: 10px;
  fill: var(--color-text-muted);
}
</style>
