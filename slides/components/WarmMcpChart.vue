<script setup lang="ts">
</script>

<template>
  <div class="mcp-card">
    <div class="mcp-head">
      <span class="eyebrow">6 CÔNG CỤ MCP QUANH CODING AGENT</span>
      <span class="pill pill-accent">Khám phá động thay cho nạp ngữ cảnh tĩnh</span>
    </div>

    <svg
      viewBox="0 0 820 278"
      class="hub-svg"
      role="img"
      aria-label="Sơ đồ 6 công cụ MCP kết nối hai chiều quanh Coding Agent Loop"
    >
      <!-- Group Band Labels -->
      <text x="410" y="16" text-anchor="middle" class="band-lbl">NHÓM 1 · TÌM KIẾM &amp; ĐỌC NGUYÊN VĂN</text>
      <text x="410" y="268" text-anchor="middle" class="band-lbl">NHÓM 2 · MỞ RỘNG ĐỒ THỊ &amp; KIỂM CHỨNG ĐẦU RA</text>

      <!-- Connectors: Top 3 -> Center -->
      <path d="M 140 88 L 140 105 L 330 105 L 330 116" class="conn" />
      <line x1="410" y1="88" x2="410" y2="116" class="conn" />
      <path d="M 680 88 L 680 105 L 490 105 L 490 116" class="conn" />

      <!-- Connectors: Center -> Bottom 3 -->
      <path d="M 330 164 L 330 175 L 140 175 L 140 190" class="conn" />
      <line x1="410" y1="164" x2="410" y2="190" class="conn" />
      <path d="M 490 164 L 490 175 L 680 175 L 680 190" class="conn accent" />

      <!-- Top Tool 1 -->
      <rect x="24" y="26" width="232" height="62" rx="10" class="tool-box" />
      <text x="140" y="51" text-anchor="middle" class="tool-name">hybrid_search</text>
      <text x="140" y="71" text-anchor="middle" class="tool-role">Tìm kiếm lai &amp; gán nhãn tin cậy</text>

      <!-- Top Tool 2 -->
      <rect x="294" y="26" width="232" height="62" rx="10" class="tool-box" />
      <text x="410" y="51" text-anchor="middle" class="tool-name">hierarchical_navigate</text>
      <text x="410" y="71" text-anchor="middle" class="tool-role">Duyệt cây mục Cha / Con / Anh em</text>

      <!-- Top Tool 3 -->
      <rect x="564" y="26" width="232" height="62" rx="10" class="tool-box" />
      <text x="680" y="51" text-anchor="middle" class="tool-name">get_raw</text>
      <text x="680" y="71" text-anchor="middle" class="tool-role">Đọc nguyên văn theo khoảng dòng</text>

      <!-- Center Hub -->
      <rect x="275" y="116" width="270" height="48" rx="12" class="hub-box" />
      <text x="410" y="138" text-anchor="middle" class="hub-title">Coding Agent Loop</text>
      <text x="410" y="155" text-anchor="middle" class="hub-sub">Chủ động chọn công cụ &amp; tự kiểm chứng</text>

      <!-- Bottom Tool 4 -->
      <rect x="24" y="190" width="232" height="62" rx="10" class="tool-box" />
      <text x="140" y="215" text-anchor="middle" class="tool-name">graph_traverse</text>
      <text x="140" y="235" text-anchor="middle" class="tool-role">Truy vết quan hệ giữa các thực thể</text>

      <!-- Bottom Tool 5 -->
      <rect x="294" y="190" width="232" height="62" rx="10" class="tool-box" />
      <text x="410" y="215" text-anchor="middle" class="tool-name">graph_curate_edges</text>
      <text x="410" y="235" text-anchor="middle" class="tool-role">Ghi nhận liên kết đã kiểm tra hợp lệ</text>

      <!-- Bottom Tool 6 (Verification Final Gate) -->
      <rect x="564" y="190" width="232" height="62" rx="10" class="tool-box gate" />
      <text x="680" y="215" text-anchor="middle" class="tool-name gate">submit_grounded_answer</text>
      <text x="680" y="235" text-anchor="middle" class="tool-role">Kiểm chứng &amp; khóa trích dẫn gốc</text>
    </svg>
  </div>
</template>

<style scoped>
.mcp-card {
  background-color: var(--color-bg-surface);
  border-radius: var(--radius-lg);
  padding: 0.9rem 1.05rem;
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.mcp-head {
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

.hub-svg {
  width: 100%;
  height: auto;
  display: block;
}

.band-lbl {
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: 0.06em;
  fill: var(--color-text-muted);
}

.conn {
  fill: none;
  stroke: var(--color-connector-muted);
  stroke-width: 1.9;
}

.conn.accent {
  stroke: var(--color-accent-solid);
  stroke-width: 2.2;
}

.tool-box {
  fill: var(--color-bg-subtle);
  stroke: var(--color-divider-hairline);
  stroke-width: 1.5;
}

.tool-box.gate {
  fill: var(--color-accent-tint);
  stroke: var(--color-accent-solid);
  stroke-width: 2;
}

.tool-name {
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 700;
  fill: var(--color-text-primary);
}

.tool-name.gate {
  fill: var(--color-accent-strong);
}

.tool-role {
  font-size: 11px;
  font-weight: 500;
  fill: var(--color-text-secondary);
}

.hub-box {
  fill: var(--color-accent-solid);
}

.hub-title {
  font-size: 14.5px;
  font-weight: 700;
  fill: var(--color-text-on-solid);
}

.hub-sub {
  font-size: 11px;
  font-weight: 500;
  fill: var(--color-accent-badge);
}
</style>
