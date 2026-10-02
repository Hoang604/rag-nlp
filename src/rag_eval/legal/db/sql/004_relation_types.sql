CREATE TABLE IF NOT EXISTS relation_types (
    code VARCHAR(32) PRIMARY KEY,
    description TEXT NOT NULL,
    is_symmetric BOOLEAN NOT NULL
);

INSERT INTO relation_types (code, description, is_symmetric) VALUES
    ('REFERENCES', 'Dẫn nguồn, tham chiếu thông tin trung lập', FALSE),
    ('SUPPORTS', 'Cung cấp bằng chứng, số liệu, củng cố luận điểm cho nút đích', FALSE),
    ('CONTRADICTS', 'Mâu thuẫn, phản bác hoặc xung đột thông tin với nút đích', TRUE),
    ('DEFINES', 'Định nghĩa thuật ngữ, khái niệm hoặc thực thể được sử dụng ở nút đích', FALSE),
    ('EXTENDS', 'Mở rộng, bổ sung chi tiết hoặc phát triển thêm ý từ nút đích', FALSE),
    ('EXEMPLIFIES', 'Cung cấp ví dụ thực tế hoặc ca nghiên cứu minh họa cho nút đích', FALSE),
    ('DEPENDS_ON', 'Phụ thuộc điều kiện tiên quyết logic hoặc kỹ thuật vào nút đích', FALSE),
    ('SUPERSEDES', 'Thay thế, bãi bỏ hoặc làm lỗi thời nội dung ở nút đích', FALSE),
    ('SEE_ALSO', 'Liên kết liên tưởng ngữ cảnh, nội dung tham khảo thêm', TRUE)
ON CONFLICT (code) DO NOTHING;
