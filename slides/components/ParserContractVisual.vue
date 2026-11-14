<script setup lang="ts">
</script>

<template>
  <div class="contract-wrap">
    <div class="col-eyebrow">CỔNG KIỂM ĐỊNH HỆ THỐNG (XANH) &amp; QUY ƯỚC PARSER AST THEO MIỀN (CHÀM)</div>
    <svg viewBox="0 0 860 322" class="contract-svg" role="img" aria-label="Sơ đồ luồng tiếp nhận CodingParserRegistry, cổng kiểm định biên trước DB và chuẩn thiết kế Parser AST">
      <defs>
        <marker id="pc-teal" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5.5" markerHeight="5.5" orient="auto-start-reverse">
          <path d="M 0 1 L 10 5 L 0 9 z" class="mk-accent" />
        </marker>
        <marker id="pc-rose" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5.5" markerHeight="5.5" orient="auto-start-reverse">
          <path d="M 0 1 L 10 5 L 0 9 z" class="mk-danger" />
        </marker>
      </defs>

      <!-- Top Row: Raw Doc -> Registry -> Fast-Fail Guard -->
      <rect x="16" y="10" width="214" height="62" rx="9" class="bx-subtle" />
      <text x="123" y="33" text-anchor="middle" class="nd-bold">1. Tài liệu gốc đánh số dòng</text>
      <text x="123" y="53" text-anchor="middle" class="nd-sub">.mdx · .md kỹ thuật · văn bản pháp quy</text>

      <line x1="230" y1="41" x2="274" y2="41" class="ln-accent" marker-end="url(#pc-teal)" />

      <rect x="278" y="10" width="280" height="62" rx="9" class="bx-accent" />
      <text x="418" y="33" text-anchor="middle" class="nd-bold accent">2. CodingParserRegistry</text>
      <text x="418" y="53" text-anchor="middle" class="nd-mono">Chọn đúng Parser theo miền · 0 generic fallback</text>

      <line x1="558" y1="41" x2="602" y2="41" class="ln-danger" marker-end="url(#pc-rose)" />

      <rect x="606" y="10" width="238" height="62" rx="9" class="bx-danger" />
      <text x="725" y="33" text-anchor="middle" class="nd-bold danger">Ngoài đặc tả → Chặn tức thì</text>
      <text x="725" y="53" text-anchor="middle" class="nd-mono danger">UnsupportedFrameworkError</text>

      <line x1="418" y1="72" x2="418" y2="96" class="ln-accent" marker-end="url(#pc-teal)" />

      <!-- 5 Invariants Container -->
      <rect x="16" y="100" width="828" height="212" rx="12" class="bx-frame" />
      <text x="34" y="122" class="frame-lbl">3. BIÊN KIỂM ĐỊNH TRƯỚC POSTGRESQL (GATE TỔNG QUÁT) &amp; CHUẨN PARSER AST THEO MIỀN</text>

      <!-- Inv 1 -->
      <rect x="34" y="134" width="388" height="50" rx="8" class="bx-accent" />
      <text x="48" y="153" class="inv-tag">INV 1 · LTREE DUY NHẤT [GATE + DB]</text>
      <text x="48" y="172" class="nd-sub">Khóa đường dẫn ltree duy nhất trong tiền tố doc_slug.*</text>

      <!-- Inv 2 -->
      <rect x="438" y="134" width="388" height="50" rx="8" class="bx-accent" />
      <text x="452" y="153" class="inv-tag">INV 2 · BIÊN DÒNG RỜI NHAU [GATE + DB]</text>
      <text x="452" y="172" class="nd-sub">Ép 1 ≤ start ≤ end ≤ số dòng &amp; không chồng lấn (AST neo gốc)</text>

      <!-- Inv 3 -->
      <rect x="34" y="194" width="388" height="50" rx="8" class="bx-accent" />
      <text x="48" y="213" class="inv-tag">INV 3 · NGỮ CẢNH CHA [GATE + PARSER]</text>
      <text x="48" y="232" class="nd-sub">Gate ép khớp ngữ cảnh ⟷ nguyên văn; Parser gắn đường dẫn cha</text>

      <!-- Inv 4 -->
      <rect x="438" y="194" width="388" height="50" rx="8" class="bx-sem" />
      <text x="452" y="213" class="inv-tag sem">INV 4 · NÚT CHA TRUNG GIAN [PARSER AST]</text>
      <text x="452" y="232" class="nd-sub">Parser giữ đủ định danh Chương, Mục...; lược bỏ nút rỗng</text>

      <!-- Inv 5 -->
      <rect x="34" y="254" width="792" height="44" rx="8" class="bx-sem" />
      <text x="48" y="272" class="inv-tag sem">INV 5 · NGUYÊN TỬ THEO NGỮ PHÁP MIỀN [PARSER AST + UNIT TEST]</text>
      <text x="48" y="289" class="nd-sub">Không cắt ngang khối code, bảng hay Điều luật — bảo chứng bằng cây AST và bộ test từng miền</text>
    </svg>
  </div>
</template>

<style scoped>
.contract-wrap {
  background-color: var(--color-bg-surface);
  border-radius: var(--radius-lg);
  padding: 0.72rem 0.9rem;
  display: flex;
  flex-direction: column;
  gap: 0.42rem;
}

.col-eyebrow {
  font-size: 0.66rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  color: var(--color-accent-strong);
}

.contract-svg {
  width: 100%;
  height: auto;
  max-height: 318px;
  display: block;
}

.mk-accent {
  fill: var(--color-accent-solid);
}

.mk-danger {
  fill: var(--color-danger-solid);
}

.bx-subtle {
  fill: var(--color-bg-subtle);
}

.bx-surface {
  fill: var(--color-bg-surface);
}

.bx-frame {
  fill: var(--color-bg-subtle);
}

.bx-accent {
  fill: var(--color-accent-tint);
}

.bx-sem {
  fill: var(--color-sem-tint);
}

.bx-danger {
  fill: var(--color-danger-tint);
}

.ln-accent {
  stroke: var(--color-accent-solid);
  stroke-width: 1.9;
}

.ln-danger {
  stroke: var(--color-danger-solid);
  stroke-width: 1.9;
  stroke-dasharray: 4 3;
}

.nd-bold {
  font-family: var(--font-sans);
  font-size: 11.5px;
  font-weight: 700;
  fill: var(--color-text-primary);
}

.nd-bold.accent {
  fill: var(--color-accent-strong);
}

.nd-bold.danger {
  fill: var(--color-danger-strong);
}

.nd-sub {
  font-family: var(--font-sans);
  font-size: 10px;
  fill: var(--color-text-secondary);
}

.nd-mono {
  font-family: var(--font-mono);
  font-size: 9.8px;
  font-weight: 600;
  fill: var(--color-text-primary);
}

.nd-mono.danger {
  fill: var(--color-danger-strong);
}

.frame-lbl {
  font-family: var(--font-sans);
  font-size: 9.8px;
  font-weight: 700;
  letter-spacing: 0.04em;
  fill: var(--color-text-muted);
}

.inv-tag {
  font-family: var(--font-sans);
  font-size: 9.8px;
  font-weight: 700;
  fill: var(--color-accent-strong);
}

.inv-tag.sem {
  fill: var(--color-sem-strong);
}
</style>
