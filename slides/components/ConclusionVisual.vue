<script setup lang="ts">
</script>

<template>
  <div class="concl-card">
    <svg
      viewBox="0 0 860 280"
      class="map-svg"
      role="img"
      aria-label="Sơ đồ 3 đóng góp cốt lõi và 3 hướng phát triển tiếp theo"
    >
      <defs>
        <marker id="cn-sem" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 1 L 10 5 L 0 9 z" class="mk-sem" />
        </marker>
      </defs>

      <text x="16" y="20" class="hdr-lbl accent">3 ĐÓNG GÓP CỐT LÕI ĐÃ KIỂM CHỨNG</text>
      <text x="454" y="20" class="hdr-lbl sem">3 HƯỚNG PHÁT TRIỂN TIẾP THEO</text>

      <!-- Row 1 -->
      <rect x="14" y="34" width="388" height="70" rx="10" class="bx-accent" />
      <text x="30" y="61" class="r-title accent">CH1 · Bỏ cắt chung: Parser theo 5 bất biến</text>
      <text x="30" y="84" class="r-sub">170 tài liệu (3 miền) → 5.975 chunk · 0 lỗi dòng · nạp ấm &lt;3s</text>

      <rect x="452" y="34" width="394" height="70" rx="10" class="bx-sem" />
      <text x="468" y="61" class="r-title sem">Đồ thị Tri thức đa phiên &amp; theo phiên bản</text>
      <text x="468" y="84" class="r-sub">Tích lũy tri thức liên phiên, tự gắn SUPERSEDES khi đổi bản</text>

      <!-- Row 2 -->
      <rect x="14" y="116" width="388" height="70" rx="10" class="bx-accent" />
      <text x="30" y="143" class="r-title accent">CH2 · Tìm kênh đôi &amp; Cổng tin cậy cho Agent</text>
      <text x="30" y="166" class="r-sub">Tìm thấy 97% (100% đúng phạm vi) · Recall@10 95% · p = 0,0156</text>

      <line x1="408" y1="151" x2="444" y2="151" class="ln-sem" marker-end="url(#cn-sem)" />

      <rect x="452" y="116" width="394" height="70" rx="10" class="bx-sem" />
      <text x="468" y="143" class="r-title sem">Kiểm chứng câu trả lời ở mức luận điểm</text>
      <text x="468" y="166" class="r-sub">Đảm bảo từng khẳng định khớp nghĩa nguồn, không chỉ đúng dòng</text>

      <!-- Row 3 -->
      <rect x="14" y="198" width="388" height="70" rx="10" class="bx-accent" />
      <text x="30" y="225" class="r-title accent">CH3 · Điều tra lặp MCP &amp; Chặn trích dẫn sai</text>
      <text x="30" y="248" class="r-sub">Warm MCP ~0,7s (40×) · chặn 100% nguồn sai · giải multi-hop</text>

      <rect x="452" y="198" width="394" height="70" rx="10" class="bx-sem" />
      <text x="468" y="225" class="r-title sem">Tối ưu chiến lược điều tra từ nhật ký MCP</text>
      <text x="468" y="248" class="r-sub">Học từ tool trace để rút ngắn bước multi-hop và gợi ý nhánh</text>
    </svg>
  </div>
</template>

<style scoped>
.concl-card {
  background-color: var(--color-bg-surface);
  border-radius: var(--radius-lg);
  padding: 0.78rem 0.9rem;
}

.map-svg {
  width: 100%;
  height: auto;
  display: block;
}

.mk-sem {
  fill: var(--color-sem-solid);
}

.bx-accent {
  fill: var(--color-accent-tint);
}

.bx-sem {
  fill: var(--color-sem-tint);
}

.ln-sem {
  stroke: var(--color-sem-solid);
  stroke-width: 2;
}

.hdr-lbl {
  font-family: var(--font-sans);
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: 0.05em;
}

.hdr-lbl.accent {
  fill: var(--color-accent-strong);
}

.hdr-lbl.sem {
  fill: var(--color-sem-strong);
}

.r-title {
  font-family: var(--font-sans);
  font-size: 12.5px;
  font-weight: 700;
}

.r-title.accent {
  fill: var(--color-accent-strong);
}

.r-title.sem {
  fill: var(--color-sem-strong);
}

.r-sub {
  font-family: var(--font-sans);
  font-size: 10.5px;
  fill: var(--color-text-secondary);
}
</style>
