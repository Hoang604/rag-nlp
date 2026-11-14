<script setup lang="ts">
</script>

<template>
  <div class="law-example-wrap">
    <svg viewBox="0 0 880 330" class="law-svg" role="img" aria-label="Ví dụ chuyển đổi Nghị định 46/2023/NĐ-CP sang cây ltree đầy đủ các cấp Chương, Mục, Tiểu mục, Điều">
      <defs>
        <marker id="lw-teal" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 1 L 10 5 L 0 9 z" class="mk-accent" />
        </marker>
      </defs>

      <!-- Left: Raw Markdown Source Lines -->
      <rect x="10" y="10" width="398" height="310" rx="12" class="bx-surface" />
      <text x="26" y="34" class="eyebrow-muted">VĂN BẢN NGUỒN (.MD) · NGHỊ ĐỊNH 46/2023/NĐ-CP</text>

      <rect x="24" y="48" width="370" height="258" rx="8" class="bx-subtle" />

      <text x="34" y="72" class="ln-num">2322</text>
      <text x="72" y="72" class="md-h2">## Chương VII: NGHIỆP VỤ BẢO HIỂM...</text>

      <text x="34" y="96" class="ln-num">2426</text>
      <text x="72" y="96" class="md-h3">### Mục 2: BẢO HIỂM LIÊN KẾT ĐẦU TƯ</text>

      <text x="34" y="120" class="ln-num">2428</text>
      <text x="72" y="120" class="md-h4">Tiểu mục 1 · ĐẶC ĐIỂM NGHIỆP VỤ...</text>

      <text x="72" y="142" class="md-dots">...</text>

      <rect x="28" y="152" width="362" height="144" rx="7" class="bx-accent" />
      <text x="36" y="174" class="ln-num accent">2432</text>
      <text x="72" y="174" class="md-h4 accent">#### Điều 101. Đặc điểm liên kết đầu tư</text>

      <text x="36" y="198" class="ln-num accent">2434</text>
      <text x="72" y="198" class="md-body">1. Nghiệp vụ bảo hiểm liên kết đầu tư...</text>

      <text x="36" y="218" class="ln-num accent">2436</text>
      <text x="72" y="218" class="md-body">2. Sản phẩm có các đặc điểm sau đây:</text>

      <text x="36" y="238" class="ln-num accent">2438</text>
      <text x="72" y="238" class="md-body">a) Tách bạch bảo hiểm rủi ro và đầu tư;</text>

      <text x="36" y="258" class="ln-num accent">2446</text>
      <text x="72" y="258" class="md-body">3. Thời hạn tối thiểu là 10 năm...</text>

      <text x="72" y="282" class="md-hint">→ Giữ nguyên từng dòng để trích dẫn khớp 1:1</text>

      <!-- Arrow Left -> Right -->
      <line x1="410" y1="165" x2="436" y2="165" class="ln-accent" marker-end="url(#lw-teal)" />

      <!-- Right: Full ltree Hierarchy & Atomic Chunk -->
      <rect x="442" y="10" width="428" height="310" rx="12" class="bx-surface" />
      <text x="458" y="34" class="eyebrow-accent">DỮ LIỆU SAU KHI PARSER CHUẨN HÓA</text>

      <!-- Hierarchy Tree: Full Levels -->
      <rect x="458" y="48" width="396" height="110" rx="8" class="bx-sem" />
      <text x="472" y="69" class="blk-lbl sem">ĐẦY ĐỦ CẤP CÂY LTREE (6 CẤP TỪ MIỀN ĐẾN ĐIỀU)</text>
      <text x="472" y="90" class="tree-txt">Miền: baohiem → Nghị định 46/2023/NĐ-CP</text>
      <text x="484" y="110" class="tree-txt">└─ Chương VII → Mục 2 → Tiểu mục 1</text>
      <text x="502" y="130" class="tree-txt accent">└─ Điều 101 (trọn Khoản 1–3, Điểm a–d bên trong)</text>
      <text x="472" y="148" class="tree-note">Các nút cha giữ tiêu đề tiếng Việt có dấu để duyệt cây</text>

      <!-- Atomic Chunk Card -->
      <rect x="458" y="170" width="396" height="136" rx="8" class="bx-accent" />
      <text x="472" y="191" class="blk-lbl">1 ĐIỀU = 1 CHUNK NGUYÊN TỬ</text>

      <rect x="470" y="202" width="372" height="46" rx="6" class="bx-surface" />
      <text x="482" y="219" class="mono-key">Đường dẫn ltree đầy đủ:</text>
      <text x="482" y="237" class="mono-val">baohiem.nghi_dinh_46_2023_nd_cp.chuong_vii.muc_2.tieu_muc_1.dieu_101</text>

      <rect x="470" y="256" width="180" height="40" rx="6" class="bx-surface" />
      <text x="482" y="272" class="mono-key">Tọa độ dòng gốc:</text>
      <text x="482" y="288" class="mono-val">Dòng 2432 – 2446 (1:1)</text>

      <rect x="662" y="256" width="180" height="40" rx="6" class="bx-surface" />
      <text x="674" y="272" class="mono-key">Đơn vị nhỏ hơn:</text>
      <text x="674" y="288" class="tree-txt">Giữ trọn Khoản &amp; Điểm</text>
    </svg>
  </div>
</template>

<style scoped>
.law-example-wrap {
  background-color: var(--color-bg-subtle);
  border-radius: var(--radius-lg);
  padding: 0.45rem 0.65rem;
}

.law-svg {
  width: 100%;
  height: auto;
  max-height: 336px;
  display: block;
}

.mk-accent {
  fill: var(--color-accent-solid);
}

.ln-accent {
  stroke: var(--color-accent-solid);
  stroke-width: 2.2;
}

.bx-surface {
  fill: var(--color-bg-surface);
}

.bx-subtle {
  fill: var(--color-bg-subtle);
}

.bx-accent {
  fill: var(--color-accent-tint);
}

.bx-sem {
  fill: var(--color-sem-tint);
}

.eyebrow-muted,
.eyebrow-accent {
  font-family: var(--font-sans);
  font-size: 9.8px;
  font-weight: 700;
  letter-spacing: 0.05em;
}

.eyebrow-muted {
  fill: var(--color-text-muted);
}

.eyebrow-accent {
  fill: var(--color-accent-strong);
}

.ln-num {
  font-family: var(--font-mono);
  font-size: 9.8px;
  font-weight: 600;
  fill: var(--color-text-muted);
}

.ln-num.accent {
  fill: var(--color-accent-strong);
}

.md-h2,
.md-h3,
.md-h4 {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  fill: var(--color-text-primary);
}

.md-h4.accent {
  fill: var(--color-accent-strong);
}

.md-body {
  font-family: var(--font-sans);
  font-size: 10.2px;
  fill: var(--color-text-secondary);
}

.md-hint {
  font-family: var(--font-sans);
  font-size: 9.5px;
  font-weight: 600;
  fill: var(--color-accent-strong);
}

.md-dots {
  font-family: var(--font-mono);
  font-size: 11px;
  fill: var(--color-text-muted);
}

.blk-lbl {
  font-family: var(--font-sans);
  font-size: 9.5px;
  font-weight: 700;
  letter-spacing: 0.04em;
  fill: var(--color-accent-strong);
}

.blk-lbl.sem {
  fill: var(--color-sem-strong);
}

.tree-txt {
  font-family: var(--font-sans);
  font-size: 10.4px;
  font-weight: 600;
  fill: var(--color-text-primary);
}

.tree-txt.accent {
  fill: var(--color-accent-strong);
}

.tree-note {
  font-family: var(--font-sans);
  font-size: 9.4px;
  fill: var(--color-text-muted);
}

.mono-key {
  font-family: var(--font-sans);
  font-size: 9.5px;
  fill: var(--color-text-muted);
}

.mono-val {
  font-family: var(--font-mono);
  font-size: 8.6px;
  font-weight: 700;
  fill: var(--color-accent-strong);
}
</style>
