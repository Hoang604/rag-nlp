export type IngestionStage =
  | 'IDLE'
  | 'NORMALIZING'
  | 'AST_STRUCTURING'
  | 'BREADCRUMB_SYNTHESIS'
  | 'WAL_GENESIS'
  | 'COMPLETED'
  | 'ERROR';

export interface IngestionUploadResponse {
  status: 'SUCCESS' | 'ERROR';
  doc_slug: string;
  title: string;
  total_chunks: number;
  total_edges: number;
  total_lines: number;
  tables_count: number;
  created_at: string;
}

export interface IngestionStageInfo {
  stage: IngestionStage;
  label: string;
  description: string;
}

export const INGESTION_STAGES: IngestionStageInfo[] = [
  {
    stage: 'NORMALIZING',
    label: 'Chuẩn Hóa Đa Định Dạng',
    description: 'Chuyển đổi PDF, DOCX, Markdown hoặc HTML thành văn bản UTF-8 chuẩn tắc',
  },
  {
    stage: 'AST_STRUCTURING',
    label: 'Bóc Tách Cây Phân Cấp AST',
    description: 'Xây dựng cây ltree H1..H6, bảo toàn khối bảng biểu và tọa độ dòng 1-indexed',
  },
  {
    stage: 'BREADCRUMB_SYNTHESIS',
    label: 'Tổng Hợp Phả Hệ & Trích Xuất Quan Hệ',
    description: 'Sinh ngữ cảnh tổ tiên và trích xuất quan hệ đồ thị với độ chính xác 100%',
  },
  {
    stage: 'WAL_GENESIS',
    label: 'Ghi Nhật Ký WAL Genesis (LSN 0)',
    description: 'Lưu trữ snapshot ban đầu vào vùng đệm Staging sẵn sàng cho Agent và Studio',
  },
];
