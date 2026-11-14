<script setup lang="ts">
</script>

<template>
  <div class="hero-card">
    <div class="hero-caption">MÔ HÌNH KHÉP KÍN HAI ĐẦU</div>
    <svg viewBox="0 0 380 230" class="hero-svg" role="img" aria-label="Sơ đồ khái quát ba trụ cột của hệ thống trên PostgreSQL 16">
      <defs>
        <marker id="cv-teal" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5.5" markerHeight="5.5" orient="auto-start-reverse">
          <path d="M 0 1 L 10 5 L 0 9 z" class="mk-accent" />
        </marker>
        <marker id="cv-sem" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5.5" markerHeight="5.5" orient="auto-start-reverse">
          <path d="M 0 1 L 10 5 L 0 9 z" class="mk-sem" />
        </marker>
      </defs>

      <!-- Top: Ingestion -->
      <rect x="20" y="10" width="340" height="50" rx="10" class="bx-accent" />
      <text x="36" y="30" class="nd-tag accent">1 · PHA NẠP TÀI LIỆU</text>
      <text x="36" y="48" class="nd-title">Parser theo cấu trúc &amp; giữ cây mục lục</text>

      <line x1="190" y1="62" x2="190" y2="80" class="ln-accent" marker-end="url(#cv-teal)" />

      <!-- Center: PostgreSQL 16 -->
      <rect x="20" y="84" width="340" height="54" rx="10" class="bx-hub" />
      <text x="190" y="106" text-anchor="middle" class="hub-title">PostgreSQL 16</text>
      <text x="190" y="124" text-anchor="middle" class="hub-ver">Lưu cây phân cấp, chỉ mục ngữ nghĩa &amp; đồ thị</text>

      <line x1="190" y1="144" x2="190" y2="162" class="ln-sem" marker-start="url(#cv-sem)" marker-end="url(#cv-sem)" />

      <!-- Bottom: Coding Agent -->
      <rect x="20" y="168" width="340" height="50" rx="10" class="bx-sem" />
      <text x="36" y="188" class="nd-tag sem">2 · PHA THỰC THI</text>
      <text x="36" y="206" class="nd-title">Coding Agent chủ động tra cứu &amp; đối chiếu nguồn</text>
    </svg>
  </div>
</template>

<style scoped>
.hero-card {
  background-color: var(--color-bg-surface);
  border-radius: var(--radius-lg);
  padding: 0.8rem 0.95rem;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.hero-caption {
  font-size: 0.66rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  color: var(--color-accent-strong);
}

.hero-svg {
  width: 100%;
  height: auto;
  display: block;
}

.mk-accent {
  fill: var(--color-accent-solid);
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

.bx-hub {
  fill: var(--color-accent-solid);
}

.ln-accent {
  stroke: var(--color-accent-solid);
  stroke-width: 2;
}

.ln-sem {
  stroke: var(--color-sem-solid);
  stroke-width: 2;
}

.nd-tag {
  font-family: var(--font-sans);
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.05em;
}

.nd-tag.accent {
  fill: var(--color-accent-strong);
}

.nd-tag.sem {
  fill: var(--color-sem-strong);
}

.nd-title {
  font-family: var(--font-sans);
  font-size: 12.5px;
  font-weight: 700;
  fill: var(--color-text-primary);
}

.hub-title {
  font-family: var(--font-sans);
  font-size: 13.5px;
  font-weight: 700;
  fill: var(--color-text-on-solid);
}

.hub-ver {
  font-family: var(--font-sans);
  font-size: 10px;
  fill: var(--color-accent-badge);
}
</style>
