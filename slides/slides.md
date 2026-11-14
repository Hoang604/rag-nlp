---
theme: default
title: Kiến trúc RAG Phân cấp Động & Knowledge Graph cho Coding Agent
colorSchema: light
aspectRatio: 16/9
canvasWidth: 980
highlighter: shiki
lineNumbers: false
selectable: true
fonts:
  sans: Be Vietnam Pro
  mono: Cascadia Mono
  weights: '400,500,600,700'
  provider: none
layout: deck-cover
eyebrow: BÁO CÁO BÀI TẬP LỚN CUỐI KỲ · XỬ LÝ NGÔN NGỮ TỰ NHIÊN
subtitle: Hệ thống truy xuất phân cấp theo cấu trúc tài liệu và điều tra đa bước trên PostgreSQL 16.
course: CSE703065-N01 (NLP 2027.1.1) · Năm học 2025–2026
group: 'Nhóm 16: Đinh Việt Hoàng (23010051) · Phạm Hồng Đức (23010338)'
advisor: 'GVHD: ThS. Nguyễn Văn Sơn'
repo: github.com/Hoang604/rag-nlp
---

# Kiến trúc RAG Phân cấp & Knowledge Graph cho Coding Agent

---
layout: section-slide
section: 01 · Bối cảnh & Bài toán
title: Hai điểm nghẽn căn bản của kiến trúc RAG tĩnh
subtitle: Một logic cắt dùng chung cho mọi định dạng và ép LLM trả lời trong một lượt ngữ cảnh.
---

<StaticRagProblem />

---
layout: section-slide
section: 01 · Kiến trúc Hệ thống
title: Kiến trúc RAG động hai đầu cho Coding Agent
subtitle: Chuẩn hóa cấu trúc khi nạp vào PostgreSQL 16 và trao quyền điều tra chủ động ở pha chạy.
---

<ArchFlowDiagram />

---
layout: section-slide
section: 02 · Pha Ingestion & Hợp đồng Dữ liệu
title: Hợp đồng Parser & Biên kiểm định Đầu ra
subtitle: Cổng hệ thống khóa đặc tả, đường dẫn ltree và biên dòng không trùng; Parser AST giữ trọn cấu trúc miền.
---

<ParserContractVisual />

---
layout: section-slide
section: 02 · Pha Ingestion Đa miền
title: Một hợp đồng chạy trên 3 kho dữ liệu khác hẳn nhau (5.975 chunks)
subtitle: Áp dụng thống nhất từ tài liệu kỹ thuật tiếng Anh sang văn bản pháp quy tiếng Việt.
---

<ParserDomainGrid />

---
layout: section-slide
section: 02 · Ví dụ Miền Pháp luật
title: Ví dụ trực quan dạng dữ liệu miền Pháp luật Bảo hiểm VN
subtitle: Ánh xạ nguyên văn Nghị định 46/2023/NĐ-CP sang cây ltree đầy đủ Chương – Mục – Tiểu mục – Điều.
---

<InsuranceDataExample />

---
layout: section-slide
section: 03 · Lõi Truy xuất & Biểu diễn Ngữ cảnh
title: Tách biệt biểu diễn lúc Indexing và lúc Trả kết quả cho Agent
subtitle: Khử nhập nhằng mục con khi tìm kiếm nhưng không lặp lại tiền tố thừa khi Agent đọc.
---

<ContextSplitDemo />

---
layout: section-slide
section: 03 · Đường ống Kênh Ngữ nghĩa
title: Đường ống Truy xuất Ngữ nghĩa & Hợp nhất RRF
subtitle: Phối hợp tìm theo ý nghĩa câu hỏi, khớp từ khóa nguyên vẹn và gộp thứ hạng.
---

<SemanticPipelineVisual />

---
layout: section-slide
section: 03 · Phân hoạch Kênh đôi Venn
title: Phân hoạch Kênh đôi Venn cứu ký hiệu đặc thù
subtitle: Giao hai kênh đứng đầu ưu tiên; kênh nguyên văn cứu các truy vấn chứa mã ký hiệu hiếm.
---

<VennPartitionVisual />

---
layout: section-slide
section: 03 · Kiểm soát Độ tin cậy
title: Ma trận Cổng Kiểm soát Tin cậy
subtitle: Phối hợp độ khớp ngữ nghĩa, xác nhận từ khóa và Reranker để xuất 4 mức tin cậy cho Agent.
---

<ConfidenceGateVisual />

---
layout: section-slide
section: 04 · Pha Runtime & Giao thức MCP
title: Bộ 6 Công cụ MCP Cho Coding Agent
subtitle: Trao quyền tìm kiếm, duyệt cây phân cấp, truy vết đồ thị và kiểm chứng trích dẫn chủ động.
---

<WarmMcpChart />

---
layout: section-slide
section: 04 · Quản trị Đồ thị & Chống Ảo giác
title: Chặn Trích dẫn Sai trong Vòng lặp MCP
subtitle: Mọi yêu cầu sai phạm vi bị cổng MCP từ chối tức thì trước khi chạm vào PostgreSQL 16.
---

<McpTrajectoryFlow />

---
layout: section-slide
section: 05 · Giao diện Quan sát & Kiểm chứng
title: Giao diện Hỏi đáp có Kiểm chứng Trích dẫn
subtitle: Đối chiếu trực tiếp câu trả lời của Agent với từng dòng điều khoản nguyên văn từ PostgreSQL.
---

<div class="split-38-62">
<SurfaceCard variant="subtle" eyebrow="CÁCH ĐỌC MÀN HÌNH KIỂM CHỨNG" title="Minh bạch từng câu trả lời">

- **Bên trái:** Câu hỏi người dùng kèm đáp án tổng hợp của Agent.
- **Thẻ trích dẫn:** Hiển thị đường dẫn phân cấp và khoảng dòng `L534–536` đã xác thực.
- **Đối chiếu tức thì:** Nhấp vào thẻ để mở nguyên văn văn bản gốc mà không phải đoán.

</SurfaceCard>
<FigureFrame
src="/figures/ui_grounded_qa_crop.png"
alt="Giao diện Grounded Q&A trả lời Điều 35 Luật Kinh doanh bảo hiểm 2022 kèm thẻ Validated Citations dòng L534-536"
caption="Hỏi đáp Điều 35 Luật Kinh doanh bảo hiểm 2022 kèm thẻ trích dẫn xác thực dòng L534–536"
badge="L534–536 Verified"
maxHeight="340px"
/>
</div>

---
layout: section-slide
section: 05 · Giao diện Khám phá Cây Tri thức
title: Bản đồ Tư duy Tương tác trên Cây Phân cấp
subtitle: Duyệt trực quan cấu trúc Văn bản → Chương → Mục → Điều bằng tiêu đề tiếng Việt có dấu.
---

<div class="stack-sm">
<FigureFrame
src="/figures/ui_explorer_tree.png"
alt="Cây phân cấp tương tác Luật Kinh doanh bảo hiểm 08/2022/QH15 từ gốc văn bản xuống 7 Chương và 4 Mục của Chương II"
caption="Sơ đồ cây ltree Luật 08/2022/QH15: tự động dựng nút tiếng Việt có dấu và nhảy thẳng tới nguyên văn từng Điều"
badge="Mind Map"
maxHeight="345px"
/>
</div>

---
layout: section-slide
section: 06 · Thiết kế Thực nghiệm Khách quan
title: Giao thức Đánh giá 3 Pha Cách ly Mù
subtitle: Tách riêng người đặt câu hỏi, người lập truy vấn và người chấm đáp án để tránh thiên lệch từ vựng.
---

<BlindEvalProtocol />

---
layout: section-slide
section: 06 · Kết quả Định lượng Truy xuất
title: Biểu đồ Độ phủ & Chất lượng Xếp hạng
subtitle: Đạt 100% trên toàn bộ miền Node.js (50/50) và 100% trên 97/97 câu lọc đúng phạm vi.
---

<EvalResultsPanel />

---
layout: section-slide
section: 06 · Nghiên cứu Ablation
title: Phân tích Ablation 7 Cấu hình Truy xuất
subtitle: Lượng hóa đóng góp của ngữ cảnh cha, hợp nhất RRF và nhánh cứu hộ nguyên văn Venn.
---

<AblationChart />

---
layout: section-slide
section: 07 · Tổng kết & Hướng Phát triển
title: Đóng góp Cốt lõi & Lộ trình Phát triển
subtitle: Khép kín vòng lặp RAG phân cấp động từ hợp đồng nạp dữ liệu đến kiểm chứng trích dẫn đầu ra.
---

<ConclusionVisual />
