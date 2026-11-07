export interface DemoScenarioQuestion {
  id: string;
  order: string;
  title: string;
  trapSummary: string;
  docs: string[];
  question: string;
}

export const BAOHIEM_DEMO_QUESTIONS: readonly DemoScenarioQuestion[] = [
  {
    id: 'bh01',
    order: '01',
    title:
      'Ngân hàng bán bảo hiểm liên kết đơn vị sau giải ngân 20 ngày và cách tính 21 ngày cân nhắc',
    trapSummary:
      'Bắc cầu NĐ 46 (liên kết đơn vị thuộc liên kết đầu tư) + TT 67 (cấm bán 60 ngày trước/sau giải ngân, bắt buộc ghi âm, 21 ngày tính từ bản giấy) + Luật KDBH (Điều 35, Điều 25).',
    docs: ['Luật 08/2022', 'NĐ 46/2023', 'TT 67/2023'],
    question:
      'Tôi vừa được ngân hàng giải ngân toàn bộ khoản vay mua nhà cách đây 20 ngày thì nhân viên ngân hàng tư vấn và cho tôi ký luôn hợp đồng bảo hiểm liên kết đơn vị 15 năm, lúc ký không hề ghi âm. Công ty bảo hiểm gửi hợp đồng bản PDF qua email cho tôi từ ngày 01/10, nhưng đến tận ngày 25/10 mới giao bản giấy tận tay. Hôm nay là ngày 05/11 (tức là đã 35 ngày từ lúc nhận email nhưng mới 11 ngày từ lúc nhận bản giấy), tôi phát hiện ra mình bị ép mua nên muốn hủy hợp đồng đòi lại tiền thì công ty bảo hiểm bảo đã quá 21 ngày cân nhắc kể từ ngày gửi email nên không hoàn phí. Công ty bảo hiểm và ngân hàng làm vậy đúng hay sai, và tôi có đòi lại được tiền không?',
  },
  {
    id: 'bh02',
    order: '02',
    title:
      'Tự tử sau 9 tháng khôi phục hợp đồng nhân thọ và quyền lợi khi đồng thụ hưởng đầu độc',
    trapSummary:
      'Thời hạn loại trừ tự tử 02 năm tính lại từ ngày khôi phục hiệu lực nhưng vẫn hoàn giá trị hoàn lại theo thừa kế (Điều 40); đồng thụ hưởng không ghi tỷ lệ được chia đều 50% (Điều 41).',
    docs: ['Luật 08/2022'],
    question:
      'Ông A mua bảo hiểm nhân thọ từ năm 2020 và đã đóng phí đều đặn 3 năm. Giữa năm 2023 do kẹt tiền, ông A ngừng đóng phí quá 60 ngày gia hạn nên bị công ty bảo hiểm đơn phương chấm dứt hợp đồng. Tháng 01/2025 (tức là vẫn trong hạn 2 năm), ông A đóng bù đủ phí và được khôi phục hợp đồng. Đến tháng 10/2025, có 2 giả thiết xảy ra:\n1. Nếu ông A tự tử vào tháng 10/2025 (tức là đã 5 năm kể từ ngày đóng phí đầu tiên năm 2020, nhưng mới 9 tháng từ ngày khôi phục hợp đồng) thì công ty bảo hiểm có phải trả tiền bảo hiểm không hay mất trắng?\n2. Nếu ông A không tự tử mà hợp đồng chỉ định 2 người con là B và C cùng thụ hưởng nhưng không ghi tỷ lệ, sau đó B cố ý đầu độc làm ông A tử vong thì C có được nhận tiền bảo hiểm không và nhận bao nhiêu?',
  },
  {
    id: 'bh03',
    order: '03',
    title:
      'Khấu trừ giá trị hoàn lại và khởi kiện đòi nợ phí: Bảo hiểm nhân thọ đối chiếu bảo hiểm cháy nổ',
    trapSummary:
      'Đối lập giữa bảo hiểm nhân thọ cá nhân (cấm tự ý khấu trừ giá trị hoàn lại, cấm khởi kiện đòi phí tại khoản 4 Điều 37) và bảo hiểm tài sản (phải đóng đủ phí đến ngày chấm dứt tại khoản 1 Điều 27).',
    docs: ['Luật 08/2022', 'TT 67/2023'],
    question:
      'Tôi mua 2 hợp đồng bảo hiểm: một hợp đồng bảo hiểm nhân thọ cá nhân và một hợp đồng bảo hiểm cháy nổ kho hàng (đóng phí theo kỳ). Do khó khăn tài chính nên tôi trễ đóng phí kỳ tiếp theo của cả 2 hợp đồng và dẫn đến bị đơn phương chấm dứt hợp đồng. Phía bảo hiểm nhân thọ dọa sẽ tự động trích từ giá trị hoàn lại của tôi để trừ nợ phí hoặc khởi kiện tôi ra tòa để đòi số phí chưa đóng; còn phía bảo hiểm tài sản thì bắt tôi phải đóng đủ tiền phí tính đến ngày chấm dứt hợp đồng dù chưa xảy ra cháy nổ gì. Yêu cầu của bên nào đúng luật, bên nào phạm luật?',
  },
  {
    id: 'bh04',
    order: '04',
    title:
      'Mua bảo hiểm trùng vượt giá trị kho hàng và quyền thế quyền đòi bồi hoàn khi con ruột làm cháy',
    trapSummary:
      'Bồi thường bảo hiểm trùng theo tỷ lệ và không vượt quá thiệt hại thực tế (Điều 49); cấm thế quyền đòi cha, mẹ, vợ, chồng, con của người được bảo hiểm trừ khi cố ý (khoản 3 Điều 54).',
    docs: ['Luật 08/2022'],
    question:
      'Kho hàng của tôi có giá thị trường là 10 tỷ đồng. Tôi mua cùng lúc 2 hợp đồng bảo hiểm cháy nổ cho kho hàng này tại Công ty X (số tiền bảo hiểm 8 tỷ đồng) và Công ty Y (số tiền bảo hiểm 12 tỷ đồng) với cùng phạm vi và thời hạn. Tháng trước, con trai ruột của tôi trong lúc trông coi kho đã vô ý làm chập điện gây cháy thiệt hại thực tế 5 tỷ đồng. Tôi yêu cầu cả 2 công ty trả đủ tổng cộng 20 tỷ theo 2 hợp đồng, nhưng họ chỉ chịu trả tổng cộng 5 tỷ theo tỷ lệ và còn bắt tôi ký giấy chuyển quyền để họ khởi kiện đòi con trai tôi bồi hoàn lại 5 tỷ đó, nếu tôi không chịu ký thì họ sẽ khấu trừ tiền bồi thường. Cách giải quyết của tôi và của 2 công ty bảo hiểm đúng sai thế nào?',
  },
  {
    id: 'bh05',
    order: '05',
    title:
      'Thời hạn 1 năm nộp hồ sơ bảo hiểm trách nhiệm dân sự và nghĩa vụ trả lãi chậm trả theo chỉ dẫn',
    trapSummary:
      'Thời hạn 01 năm tính từ ngày người thứ ba yêu cầu (khoản 3 Điều 30); người thứ ba không được đòi trực tiếp hãng bảo hiểm (khoản 2 Điều 58); hãng phải trả chi phí tranh chấp và lãi chậm trả theo chỉ dẫn (khoản 3 Điều 59).',
    docs: ['Luật 08/2022'],
    question:
      'Công ty vận tải của tôi có mua hợp đồng bảo hiểm trách nhiệm dân sự đối với người thứ ba (giới hạn trách nhiệm 5 tỷ đồng). Sự cố làm hư hỏng hàng hóa của đối tác (người thứ ba) xảy ra từ tháng 01/2024, nhưng đến tận tháng 03/2025 (tức là sau 14 tháng) đối tác mới chính thức gửi văn bản yêu cầu công ty tôi bồi thường 2 tỷ đồng. Khi tôi nộp hồ sơ yêu cầu bảo hiểm vào tháng 04/2025 và làm theo chỉ dẫn của công ty bảo hiểm là tạm hoãn chi trả để chờ thương lượng dẫn đến phát sinh thêm 150 triệu đồng tiền lãi chậm trả và chi phí giải quyết tranh chấp, công ty bảo hiểm lại từ chối toàn bộ vì cho rằng sự cố đã quá hạn 1 năm kể từ ngày xảy ra tai nạn, đồng thời bảo đối tác tự đi mà kiện đòi trực tiếp công ty bảo hiểm. Lập luận của công ty bảo hiểm có đúng luật không và khoản 150 triệu kia ai phải chịu?',
  },
  {
    id: 'bh06',
    order: '06',
    title:
      'Bán bảo hiểm liên kết đơn vị và hưu trí 100% trực tuyến trên sàn TMĐT không qua tư vấn ghi âm',
    trapSummary:
      'Giới hạn sản phẩm được bán toàn bộ quy trình trên mạng (khoản 3, 4 Điều 4 và Điều 5 TT 67); bắt buộc tư vấn trực tiếp hoặc cuộc gọi kết nối có ghi âm; thông báo Bộ Tài chính trong 07 ngày làm việc (Điều 6 TT 67).',
    docs: ['TT 67/2023'],
    question:
      'Một doanh nghiệp bảo hiểm nhân thọ hợp tác với một sàn giao dịch thương mại điện tử để bán trọn gói 100% quy trình trực tuyến (từ giới thiệu, thẩm định, thanh toán đến phát hành hợp đồng điện tử chỉ bằng thao tác bấm nút đồng ý, không cần nhân viên gọi điện hay gặp mặt tư vấn) đối với 2 sản phẩm là Bảo hiểm liên kết đơn vị và Bảo hiểm hưu trí. Sau khi vận hành chính thức được 30 ngày, doanh nghiệp này mới gửi văn bản thông báo cho Bộ Tài chính về việc cung cấp sản phẩm trên môi trường mạng. Hãy chỉ rõ các điểm vi phạm pháp luật trong cách triển khai trên.',
  },
  {
    id: 'bh07',
    order: '07',
    title:
      'Môi giới bảo hiểm giữ phí quá 30 ngày khi xảy ra cháy xưởng và đòi 20% hoa hồng kèm thù lao thu hộ',
    trapSummary:
      'Nghĩa vụ đóng phí của khách hoàn thành ngay khi đóng cho môi giới được ủy quyền (điểm b khoản 2 Điều 54 TT 67); cấm nhận thù lao ủy quyền thu phí/trả tiền (điểm d khoản 2 Điều 54); trần hoa hồng môi giới gốc 15% (khoản 3 Điều 55).',
    docs: ['TT 67/2023'],
    question:
      'Doanh nghiệp bảo hiểm phi nhân thọ A ký văn bản ủy quyền cho Công ty môi giới bảo hiểm B thu phí bảo hiểm và chi trả tiền bồi thường cho các hợp đồng do B thu xếp. Khách hàng C đã đóng đủ phí bảo hiểm đúng hạn cho Công ty môi giới B, nhưng B giữ tiền đến ngày thứ 40 vẫn chưa chuyển về cho A thì nhà xưởng của C bị cháy. Công ty bảo hiểm A từ chối bồi thường với lý do tại thời điểm cháy A vẫn chưa nhận được tiền phí từ B. Mặt khác, Công ty môi giới B còn yêu cầu A phải thanh toán 20% hoa hồng môi giới bảo hiểm gốc cộng thêm 3% khoản thù lao cho công việc thu hộ phí bảo hiểm theo ủy quyền. Hãy phân tích đúng sai của cả A và B.',
  },
  {
    id: 'bh08',
    order: '08',
    title:
      'Giảm phí bảo hiểm vật chất xe cơ giới xuống dưới phí thuần và tự ý tăng phí thuần sau 4 tháng',
    trapSummary:
      'Giảm phí trực tiếp không được vượt trần hoa hồng đại lý và không được thấp hơn phí thuần (điểm d khoản 1 Điều 25 TT 67); cấm đổi phí thuần trong 12 tháng kế tiếp (điểm b khoản 2 Điều 25); giả định chi phí và lợi nhuận tối đa 50% phí bảo hiểm (khoản 4 Điều 25).',
    docs: ['TT 67/2023'],
    question:
      'Khi xây dựng biểu phí bảo hiểm vật chất xe cơ giới cho thời hạn 1 năm, một doanh nghiệp bảo hiểm phi nhân thọ thiết kế cơ cấu phí gồm 40% là phí bảo hiểm thuần và 60% là chi phí triển khai cộng lợi nhuận dự kiến. Khi bán trực tiếp cho khách hàng không qua đại lý, doanh nghiệp này tung chương trình giảm giá trực tiếp 65% trên tổng phí bảo hiểm. Sau 4 tháng triển khai thấy tỷ lệ bồi thường cao, doanh nghiệp lập tức ra thông báo điều chỉnh tăng mức phí bảo hiểm thuần đối với đúng dòng xe và nhóm khách hàng đó. Doanh nghiệp bảo hiểm này đã vi phạm những quy định nào về phương pháp, cơ sở tính phí bảo hiểm xe cơ giới?',
  },
  {
    id: 'bh09',
    order: '09',
    title:
      'Quỹ liên kết đơn vị đầu tư vàng, bất động sản và xử lý sai lệch định giá NAV cổ phiếu 0,6%',
    trapSummary:
      'Hạn mức đầu tư trực tiếp vàng/bất động sản là 0% (điểm d khoản 2 Điều 108 NĐ 46); ngưỡng sai sót định giá quỹ cổ phiếu từ 0,5% NAV trở lên (điểm a khoản 5 Điều 109); khoản đền bù dưới 100.000 đồng phải đưa vào quỹ và cấm hạch toán chi phí đền bù vào quỹ (khoản 6, 7 Điều 109).',
    docs: ['NĐ 46/2023'],
    question:
      'Một doanh nghiệp bảo hiểm nhân thọ quản lý Quỹ liên kết đơn vị đầu tư cổ phiếu (tỷ trọng cổ phiếu chiếm 80% tài sản quỹ) đã dùng 10% tài sản của quỹ để đầu tư trực tiếp vào vàng và bất động sản. Ngoài ra, trong một kỳ giao dịch, giá trị tài sản ròng (NAV) trên một đơn vị quỹ bị định giá sai lệch ở mức 0,6%. Doanh nghiệp bảo hiểm cho rằng mức sai lệch dưới 1% nên không phải đền bù; hoặc nếu phải đền bù thì những khách hàng có số tiền sai lệch dưới 100.000 đồng doanh nghiệp sẽ giữ lại không trả, và toàn bộ chi phí đền bù cho các khách hàng trên 100.000 đồng sẽ được hạch toán trừ thẳng vào chi phí của Quỹ liên kết đơn vị. Các quyết định trên của doanh nghiệp bảo hiểm vi phạm quy định pháp luật như thế nào và thời hạn báo cáo Bộ Tài chính, đền bù là bao lâu?',
  },
  {
    id: 'bh10',
    order: '10',
    title:
      'Rút trước hạn tài khoản bảo hiểm hưu trí trả nợ tiêu dùng và thu phí khi chuyển sang công ty mới',
    trapSummary:
      'Điều kiện rút trước hạn tài khoản hưu trí: suy giảm lao động từ 61% trở lên hoặc trả khoản vay ngân hàng trừ vay tiêu dùng có hiệu lực ít nhất 24 tháng (Điều 119 NĐ 46); chuyển tài khoản sang hãng mới trong 05 ngày làm việc và cấm hãng nhận tính phí ban đầu (khoản 3, 5 Điều 120 NĐ 46).',
    docs: ['NĐ 46/2023'],
    question:
      'Anh M tham gia hợp đồng bảo hiểm hưu trí nhóm tại Công ty bảo hiểm P. Năm nay anh M chưa đến tuổi nghỉ hưu, bị tai nạn suy giảm 45% khả năng lao động và đang có một khoản vay tiêu dùng cá nhân tại ngân hàng đã ký được 30 tháng nên anh M làm đơn yêu cầu rút trước hạn 50% giá trị tài khoản bảo hiểm hưu trí để trả nợ ngân hàng nhưng bị Công ty P từ chối. Sau đó anh M nghỉ việc chuyển sang công ty mới có hợp đồng bảo hiểm hưu trí nhóm tại Công ty bảo hiểm Q và yêu cầu chuyển toàn bộ tài khoản hưu trí của mình từ P sang Q; Công ty P ngâm hồ sơ 20 ngày mới chuyển tiền, còn Công ty Q khi nhận tiền lại khấu trừ 5% phí ban đầu trên giá trị tài khoản chuyển sang. Việc làm của Công ty P và Công ty Q đúng hay sai ở từng khâu?',
  },
] as const;
