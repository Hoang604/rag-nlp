<script setup lang="ts">
</script>

<template>
  <div class="traj-card">
    <div class="traj-head">
      <span class="eyebrow">CƠ CHẾ CHẶN TRÍCH DẪN SAI QUA 3 LÀN TƯƠNG TÁC</span>
      <span class="pill pill-danger">Trọng tâm · Cổng MCP chặn lỗi trước khi chạm PostgreSQL</span>
    </div>

    <svg
      viewBox="0 0 860 314"
      class="traj-svg"
      role="img"
      aria-label="Sơ đồ 3 làn Coding Agent, Cổng kiểm chứng MCP và PostgreSQL 16 minh họa bước 03a bị chặn tức thì"
    >
      <defs>
        <marker id="tj-arr" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5.5" markerHeight="5.5" orient="auto">
          <path d="M 0 1 L 10 5 L 0 9 z" class="mk-axis" />
        </marker>
        <marker id="tj-arr-teal" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5.5" markerHeight="5.5" orient="auto">
          <path d="M 0 1 L 10 5 L 0 9 z" class="mk-teal" />
        </marker>
        <marker id="tj-arr-red" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5.5" markerHeight="5.5" orient="auto">
          <path d="M 0 1 L 10 5 L 0 9 z" class="mk-red" />
        </marker>
        <marker id="tj-arr-sem" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5.5" markerHeight="5.5" orient="auto">
          <path d="M 0 1 L 10 5 L 0 9 z" class="mk-sem" />
        </marker>
      </defs>

      <!-- Swimlane Background Corridors & Lifelines -->
      <rect x="308" y="42" width="244" height="266" rx="12" class="corridor-gate" />
      <line x1="138" y1="40" x2="138" y2="306" class="lifeline" />
      <line x1="430" y1="40" x2="430" y2="306" class="lifeline gate" />
      <line x1="722" y1="40" x2="722" y2="306" class="lifeline" />

      <!-- Lane Headers -->
      <rect x="26" y="6" width="224" height="30" rx="8" class="lane-hdr" />
      <text x="138" y="25" text-anchor="middle" class="lane-txt">CODING AGENT</text>

      <rect x="318" y="6" width="224" height="30" rx="8" class="lane-hdr accent" />
      <text x="430" y="25" text-anchor="middle" class="lane-txt on">CỔNG KIỂM CHỨNG MCP</text>

      <rect x="610" y="6" width="224" height="30" rx="8" class="lane-hdr" />
      <text x="722" y="25" text-anchor="middle" class="lane-txt">POSTGRESQL 16</text>

      <!-- Step 01 -->
      <rect x="26" y="50" width="224" height="36" rx="8" class="node" />
      <circle cx="44" cy="68" r="10" class="dot" />
      <text x="44" y="72" text-anchor="middle" class="dot-num">01</text>
      <text x="61" y="72" class="node-code">hybrid_search</text>

      <line x1="252" y1="68" x2="318" y2="68" class="conn" marker-end="url(#tj-arr)" />
      <rect x="324" y="50" width="212" height="36" rx="8" class="node-mid" />
      <text x="430" y="72" text-anchor="middle" class="node-lbl">Truy xuất ứng viên ban đầu</text>

      <line x1="538" y1="68" x2="604" y2="68" class="conn" marker-end="url(#tj-arr)" />
      <rect x="610" y="50" width="224" height="36" rx="8" class="node" />
      <text x="722" y="72" text-anchor="middle" class="node-lbl">Khoanh vùng tài liệu liên quan</text>

      <!-- Step 02 -->
      <rect x="26" y="96" width="224" height="36" rx="8" class="node" />
      <circle cx="44" cy="114" r="10" class="dot" />
      <text x="44" y="118" text-anchor="middle" class="dot-num">02</text>
      <text x="61" y="118" class="node-code">navigate + get_raw</text>

      <line x1="252" y1="114" x2="318" y2="114" class="conn" marker-end="url(#tj-arr)" />
      <rect x="324" y="96" width="212" height="36" rx="8" class="node-mid" />
      <text x="430" y="118" text-anchor="middle" class="node-lbl">Đọc cây mục &amp; dòng gốc</text>

      <line x1="538" y1="114" x2="604" y2="114" class="conn" marker-end="url(#tj-arr)" />
      <rect x="610" y="96" width="224" height="36" rx="8" class="node" />
      <text x="722" y="118" text-anchor="middle" class="node-lbl">Trả nguyên văn đoạn chuẩn</text>

      <!-- Step 03a: HERO VETO -->
      <rect x="26" y="144" width="224" height="52" rx="9" class="node danger-soft" />
      <circle cx="44" cy="170" r="11" class="dot danger" />
      <text x="44" y="174" text-anchor="middle" class="dot-num">03a</text>
      <text x="62" y="165" class="node-code danger">graph_curate_edges</text>
      <text x="62" y="183" class="node-sub danger">Tham số sai loại thực thể</text>

      <line x1="252" y1="170" x2="316" y2="170" class="conn danger" marker-end="url(#tj-arr-red)" />
      <rect x="322" y="144" width="216" height="52" rx="9" class="node-veto" />
      <text x="430" y="166" text-anchor="middle" class="veto-title">CHẶN TỨC THÌ · TỪ CHỐI GHI</text>
      <text x="430" y="184" text-anchor="middle" class="veto-sub">Ngăn lỗi ngay tại Cổng kiểm chứng</text>

      <!-- Blocked Firewall Shield Mark between Gate and DB -->
      <line x1="540" y1="170" x2="604" y2="170" class="conn blocked" />
      <circle cx="574" cy="170" r="10" class="block-circle" />
      <path d="M 570 166 L 578 174 M 578 166 L 570 174" class="block-x" />

      <rect x="610" y="144" width="224" height="52" rx="9" class="node db-safe" />
      <text x="722" y="166" text-anchor="middle" class="node-lbl safe">DB an toàn tuyệt đối</text>
      <text x="722" y="184" text-anchor="middle" class="node-sub">Không có bản ghi sai lọt xuống</text>

      <!-- Self-Correction Retry Loop 03a -> 03b -->
      <path d="M 24 172 C 8 172, 8 226, 22 226" class="retry-arc" marker-end="url(#tj-arr-sem)" />

      <!-- Step 03b: Retry Success -->
      <rect x="26" y="208" width="224" height="36" rx="8" class="node sem-soft" />
      <circle cx="44" cy="226" r="10" class="dot sem" />
      <text x="44" y="230" text-anchor="middle" class="dot-num">03b</text>
      <text x="61" y="230" class="node-code">graph_curate_edges (đã sửa)</text>

      <line x1="252" y1="226" x2="318" y2="226" class="conn sem" marker-end="url(#tj-arr-sem)" />
      <rect x="324" y="208" width="212" height="36" rx="8" class="node sem-soft" />
      <text x="430" y="230" text-anchor="middle" class="node-lbl sem">Hợp lệ → Cho phép ghi</text>

      <line x1="538" y1="226" x2="604" y2="226" class="conn sem" marker-end="url(#tj-arr-sem)" />
      <rect x="610" y="208" width="224" height="36" rx="8" class="node" />
      <text x="722" y="230" text-anchor="middle" class="node-lbl">Lưu liên kết mới vào đồ thị</text>

      <!-- Step 04: Grounded Verification -->
      <rect x="26" y="256" width="224" height="40" rx="8" class="node accent-soft" />
      <circle cx="44" cy="276" r="10" class="dot" />
      <text x="44" y="280" text-anchor="middle" class="dot-num">04</text>
      <text x="61" y="280" class="node-code">submit_grounded_answer</text>

      <line x1="252" y1="276" x2="318" y2="276" class="conn teal" marker-end="url(#tj-arr-teal)" />
      <rect x="324" y="256" width="212" height="40" rx="8" class="node accent-soft" />
      <text x="430" y="280" text-anchor="middle" class="node-lbl accent">Khớp nguyên văn 100% trích dẫn</text>

      <line x1="538" y1="276" x2="604" y2="276" class="conn teal" marker-end="url(#tj-arr-teal)" />
      <rect x="610" y="256" width="224" height="40" rx="8" class="node accent-soft" />
      <text x="722" y="280" text-anchor="middle" class="node-lbl accent">Trả kết quả kèm dòng gốc</text>
    </svg>
  </div>
</template>

<style scoped>
.traj-card {
  background-color: var(--color-bg-surface);
  border-radius: var(--radius-lg);
  padding: 0.72rem 0.9rem;
  display: flex;
  flex-direction: column;
  gap: 0.48rem;
}

.traj-head {
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

.pill-danger {
  background-color: var(--color-danger-badge);
  color: var(--color-danger-strong);
}

.traj-svg {
  width: 100%;
  height: auto;
  display: block;
}

.corridor-gate {
  fill: var(--color-accent-tint);
  stroke: var(--color-divider-hairline);
  stroke-width: 1;
}

.lifeline {
  stroke: var(--color-divider-hairline);
  stroke-width: 1.5;
  stroke-dasharray: 4 4;
}

.lifeline.gate {
  stroke: var(--color-accent-badge);
}

.lane-hdr {
  fill: var(--color-bg-subtle);
  stroke: var(--color-divider-hairline);
  stroke-width: 1.2;
}

.lane-hdr.accent {
  fill: var(--color-accent-solid);
  stroke: var(--color-accent-solid);
}

.lane-txt {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  fill: var(--color-text-primary);
}

.lane-txt.on {
  fill: var(--color-text-on-solid);
}

.node {
  fill: var(--color-bg-subtle);
  stroke: var(--color-divider-hairline);
  stroke-width: 1.3;
}

.node-mid {
  fill: var(--color-bg-surface);
  stroke: var(--color-divider-hairline);
  stroke-width: 1.3;
}

.node.danger-soft {
  fill: var(--color-danger-tint);
  stroke: var(--color-danger-solid);
  stroke-width: 1.8;
}

.node.sem-soft {
  fill: var(--color-sem-tint);
  stroke: var(--color-sem-solid);
  stroke-width: 1.4;
}

.node.accent-soft {
  fill: var(--color-bg-surface);
  stroke: var(--color-accent-solid);
  stroke-width: 1.6;
}

.node.db-safe {
  fill: var(--color-bg-surface);
  stroke: var(--color-connector-muted);
  stroke-width: 1.5;
  stroke-dasharray: 4 3;
}

.node-veto {
  fill: var(--color-danger-solid);
}

.dot {
  fill: var(--color-accent-solid);
}

.dot.sem {
  fill: var(--color-sem-solid);
}

.dot.danger {
  fill: var(--color-danger-solid);
}

.dot-num {
  font-size: 9.5px;
  font-weight: 700;
  fill: var(--color-text-on-solid);
}

.node-code {
  font-family: var(--font-mono);
  font-size: 10.6px;
  font-weight: 700;
  fill: var(--color-text-primary);
}

.node-code.danger {
  fill: var(--color-danger-strong);
}

.node-lbl {
  font-size: 11px;
  font-weight: 600;
  fill: var(--color-text-secondary);
}

.node-lbl.sem {
  fill: var(--color-sem-strong);
}

.node-lbl.accent {
  fill: var(--color-accent-strong);
}

.node-lbl.safe {
  fill: var(--color-text-primary);
  font-weight: 700;
}

.node-sub {
  font-size: 10px;
  font-weight: 500;
  fill: var(--color-text-muted);
}

.node-sub.danger {
  fill: var(--color-danger-strong);
}

.veto-title {
  font-size: 11.5px;
  font-weight: 700;
  fill: var(--color-text-on-solid);
}

.veto-sub {
  font-size: 10px;
  font-weight: 500;
  fill: var(--color-danger-badge);
}

.conn {
  fill: none;
  stroke: var(--color-axis-line);
  stroke-width: 1.6;
}

.conn.teal {
  stroke: var(--color-accent-solid);
  stroke-width: 1.8;
}

.conn.sem {
  stroke: var(--color-sem-solid);
  stroke-width: 1.7;
}

.conn.danger {
  stroke: var(--color-danger-solid);
  stroke-width: 2.1;
}

.conn.blocked {
  stroke: var(--color-danger-solid);
  stroke-width: 1.6;
  stroke-dasharray: 3 3;
}

.retry-arc {
  fill: none;
  stroke: var(--color-sem-solid);
  stroke-width: 1.9;
}

.block-circle {
  fill: var(--color-bg-surface);
  stroke: var(--color-danger-solid);
  stroke-width: 1.8;
}

.block-x {
  stroke: var(--color-danger-solid);
  stroke-width: 2;
  stroke-linecap: round;
}

.mk-axis {
  fill: var(--color-axis-line);
}

.mk-teal {
  fill: var(--color-accent-solid);
}

.mk-red {
  fill: var(--color-danger-solid);
}

.mk-sem {
  fill: var(--color-sem-solid);
}
</style>
