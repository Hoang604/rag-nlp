<script setup lang="ts">
</script>

<template>
  <div class="blind-stack">
    <div class="protocol-card">
      <div class="proto-head">
        <span class="col-eyebrow">QUY TRÌNH 3 PHA CÁCH LY MÙ VỚI 6 SUBAGENTS ĐỘC LẬP</span>
        <span class="pill pill-accent">Ngăn rò rỉ từ vựng giữa câu hỏi và đáp án</span>
      </div>

      <svg
        viewBox="0 0 880 218"
        class="blind-svg"
        role="img"
        aria-label="Sơ đồ 3 pha cách ly mù cùng 3 hàng rào bảo vệ tính khách quan cho 100 ca kiểm thử"
      >
        <defs>
          <marker id="bl-teal" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 1 L 10 5 L 0 9 z" class="mk-accent" />
          </marker>
        </defs>

        <!-- Phase 1 -->
        <rect x="12" y="14" width="260" height="96" rx="10" class="bx-sem" />
        <text x="142" y="42" text-anchor="middle" class="p-title sem">Pha 1 · Sinh 100 câu hỏi</text>
        <text x="142" y="64" text-anchor="middle" class="p-sub">2 Subagents viết độc lập theo</text>
        <text x="142" y="83" text-anchor="middle" class="p-sub">dàn ý chủ đề tài liệu</text>

        <rect x="12" y="136" width="260" height="68" rx="8" class="wall-danger" />
        <text x="142" y="164" text-anchor="middle" class="w-bold danger">Rào 1 · Cấm đọc code &amp; CSDL</text>
        <text x="142" y="185" text-anchor="middle" class="p-sub">Không thể mượn từ khóa có sẵn</text>
        <line x1="142" y1="136" x2="142" y2="110" class="ln-wall-danger" />

        <line x1="274" y1="62" x2="306" y2="62" class="ln-accent" marker-end="url(#bl-teal)" />

        <!-- Phase 2 -->
        <rect x="310" y="14" width="260" height="96" rx="10" class="bx-sem" />
        <text x="440" y="42" text-anchor="middle" class="p-title sem">Pha 2 · Tạo lời gọi MCP</text>
        <text x="440" y="64" text-anchor="middle" class="p-sub">2 Subagents đóng vai Agent</text>
        <text x="440" y="83" text-anchor="middle" class="p-sub">chọn tham số truy xuất đầu tiên</text>

        <rect x="310" y="136" width="260" height="68" rx="8" class="wall-danger" />
        <text x="440" y="164" text-anchor="middle" class="w-bold danger">Rào 2 · Cấm xem trước đoạn văn</text>
        <text x="440" y="185" text-anchor="middle" class="p-sub">Chỉ thấy câu hỏi &amp; danh sách tên tài liệu</text>
        <line x1="440" y1="136" x2="440" y2="110" class="ln-wall-danger" />

        <line x1="572" y1="62" x2="604" y2="62" class="ln-accent" marker-end="url(#bl-teal)" />

        <!-- Phase 3 -->
        <rect x="608" y="14" width="260" height="96" rx="10" class="bx-accent" />
        <text x="738" y="42" text-anchor="middle" class="p-title accent">Pha 3 · Chấm nhãn chuẩn</text>
        <text x="738" y="64" text-anchor="middle" class="p-sub">2 Subagents đối chiếu CSDL</text>
        <text x="738" y="83" text-anchor="middle" class="p-sub">xác thực 100 đường dẫn ltree đích</text>

        <rect x="608" y="136" width="260" height="68" rx="8" class="wall-accent" />
        <text x="738" y="164" text-anchor="middle" class="w-bold accent">Khóa · Cấm sửa Pha 1 &amp; Pha 2</text>
        <text x="738" y="185" text-anchor="middle" class="p-sub">Đánh giá trung thực lượt gọi đầu tiên</text>
        <line x1="738" y1="136" x2="738" y2="110" class="ln-wall-accent" />
      </svg>
    </div>

    <div class="blind-footer">
      <span class="pill pill-sem tabular">100 câu hỏi độc lập</span>
      <span class="footer-txt">
        Chia đều <strong>50 câu Next.js</strong> + <strong>50 câu Node.js</strong> trên <strong>167 tài liệu gốc</strong> (50 câu khái niệm &amp; 50 câu tên hàm/API).
      </span>
    </div>
  </div>
</template>

<style scoped>
.blind-stack {
  display: flex;
  flex-direction: column;
  gap: 0.72rem;
}

.protocol-card {
  background-color: var(--color-bg-surface);
  border-radius: var(--radius-lg);
  padding: 0.85rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}

.proto-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.col-eyebrow {
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  color: var(--color-accent-strong);
}

.blind-svg {
  width: 100%;
  height: auto;
  display: block;
}

.mk-accent {
  fill: var(--color-accent-solid);
}

.bx-sem {
  fill: var(--color-sem-tint);
}

.bx-accent {
  fill: var(--color-accent-tint);
}

.wall-danger {
  fill: var(--color-danger-tint);
  stroke: var(--color-danger-solid);
  stroke-width: 1.5;
  stroke-dasharray: 5 3;
}

.wall-accent {
  fill: var(--color-accent-tint);
  stroke: var(--color-accent-solid);
  stroke-width: 1.5;
  stroke-dasharray: 5 3;
}

.ln-accent {
  stroke: var(--color-accent-solid);
  stroke-width: 2.2;
}

.ln-wall-danger {
  stroke: var(--color-danger-solid);
  stroke-width: 1.6;
  stroke-dasharray: 3 3;
}

.ln-wall-accent {
  stroke: var(--color-accent-solid);
  stroke-width: 1.6;
  stroke-dasharray: 3 3;
}

.p-title {
  font-family: var(--font-sans);
  font-size: 13px;
  font-weight: 700;
}

.p-title.sem {
  fill: var(--color-sem-strong);
}

.p-title.accent {
  fill: var(--color-accent-strong);
}

.p-sub {
  font-family: var(--font-sans);
  font-size: 11px;
  fill: var(--color-text-secondary);
}

.w-bold {
  font-family: var(--font-sans);
  font-size: 11.5px;
  font-weight: 700;
}

.w-bold.danger {
  fill: var(--color-danger-strong);
}

.w-bold.accent {
  fill: var(--color-accent-strong);
}

.blind-footer {
  background-color: var(--color-bg-surface);
  border: 1px solid var(--color-divider-hairline);
  border-radius: var(--radius-md);
  padding: 0.62rem 0.9rem;
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.footer-txt {
  font-size: 0.78rem;
  color: var(--color-text-secondary);
}

.footer-txt strong {
  color: var(--color-text-primary);
}
</style>
