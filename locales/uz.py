"""O'zbekcha matnlar (asosiy til). Yangi kalit qo'shsangiz, ru.py ga ham qo'shing — tests/test_i18n.py tekshiradi."""

WEEKDAYS = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]
WEEKDAYS_SHORT = ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"]
MONTHS = [
    "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
    "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr",
]

TEXTS = {
    # ---------- tugmalar ----------
    "btn.found": "📦 Narsa topdim",
    "btn.lost": "🔍 Narsa yo'qotdim",
    "btn.my_searches": "🔔 Qidiruvlarim",
    "btn.my_items": "📋 Mening e'lonlarim",
    "btn.rules": "ℹ️ Qoidalar",
    "btn.lang": "🌐 Til / Язык",
    "btn.cancel": "❌ Bekor qilish",
    "btn.skip": "⏭ O'tkazib yuborish",
    "btn.manual_address": "✍️ Manzilni qo'lda kiritish",
    "btn.chat_exit": "🚪 Chatdan chiqish",
    "btn.send_location": "📍 Hozir turgan joyimni yuborish",
    "btn.send_phone": "📞 Raqamni yuborish",
    "kb.unknown": "🤷 Aniq bilmayman",
    "kb.today": "Bugun",
    "kb.yesterday": "Kecha",
    "kb.offer_text": "📄 Oferta matni",
    "kb.agree": "✅ Roziman",
    "kb.send": "✅ Yuborish",
    "kb.cancel": "❌ Bekor qilish",
    "kb.save": "✅ Saqlash",
    "kb.claim": "🙋 Bu meniki",
    "kb.subscribe": "🔔 Topilsa xabar bering",
    "kb.view_channel": "👀 Kanalda ko'rish",
    "kb.stop_search": "🔕 Qidiruvni to'xtatish",
    "kb.stop_search_code": "🔕 #{code} — to'xtatish",
    "kb.owner_yes": "✅ Narsamni oldim",
    "kb.owner_no": "⚠️ Topuvchi bilan bog'lana olmayapman",
    "kb.finder_yes": "✅ Egasiga topshirdim",
    "kb.finder_no": "⚠️ Egasi kelmadi / bog'lanmadi",
    "kb.chat": "💬 Bot orqali yozish",
    "kb.chat_owner": "💬 Egasiga bot orqali yozish",
    "kb.chat_finder": "💬 Topuvchiga bot orqali yozish",
    "kb.chat_reply": "↩️ Javob yozish",
    "kb.edit": "✏️ Izohni o'zgartirish",
    "kb.returned": "🤝 Egasiga o'zim qaytardim",
    "kb.returned_confirm": "⚠️ Ha, egasiga qaytardim — yopish",
    "kb.remove": "🗑 E'lonni olib tashlash",
    "kb.remove_confirm": "⚠️ Ha, olib tashlash",
    "kb.back": "◀️ Ro'yxatga qaytish",
    "kb.pay_online": "💳 To'lash",
    "kb.pay_card": "💳 To'lov ma'lumotlari",
    "kb.open_item": "📋 E'lonni ochish",

    # ---------- umumiy ----------
    "sum": "so'm",
    "common.cancelled": "Bekor qilindi. Asosiy menyu 👇",
    "common.cancelled_toast": "Bekor qilindi",
    "common.post_cancelled": "E'lon bekor qilindi. Asosiy menyu 👇",
    "common.too_long": "Juda uzun. Iltimos, qisqaroq yozing ({limit} belgigacha).",
    "common.too_long_500": "Juda uzun. Iltimos, 500 belgigacha yozing.",
    "common.description_too_long": "Izoh juda uzun. Iltimos, 500 belgigacha yozing.",
    "common.region_required": "Iltimos, yuqoridagi ro'yxatdan <b>viloyatni tanlang</b> 👆",
    "common.date_required": "Iltimos, yuqoridagi <b>kalendardan</b> kunni tanlang 👆",
    "common.future_day": "Kelajakdagi kunni tanlab bo'lmaydi",
    "common.phone_invalid": "Raqam noto'g'ri. Tugmani bosing yoki +998901234567 ko'rinishida yozing.",
    "common.almost_ready": "Deyarli tayyor ✅",
    "common.check_header": "📋 <b>E'loningizni tekshiring:</b>\n\n",
    "common.questions": "Savollar uchun: {admin}",
    "common.if_mistake": "Xato deb o'ylasangiz: {admin}",
    "common.error": "⚠️ Kutilmagan xatolik yuz berdi. Admin xabardor qilindi — biroz kutib, qayta urinib ko'ring.",
    "common.banned": "⛔ Siz botdan foydalanishdan cheklangansiz.",
    "loc.map_marked": "Xaritada belgilangan",
    "loc.on_map": "Xaritada ko'rish",
    "loc.unknown": "aniq emas",
    "time.at_hour": ", soat {hour}:00 atrofida",

    # ---------- start ----------
    "start.welcome": (
        "Assalomu alaykum, {name}! 👋\n\n"
        "Bu bot <b>yo'qolgan narsalarni egasiga qaytarishga</b> yordam beradi.\n\n"
        "📦 Biror narsa topdingizmi? — <b>«Narsa topdim»</b>\n"
        "🔍 Biror narsangizni yo'qotdingizmi? — <b>«Narsa yo'qotdim»</b>\n\n"
        "🔢 Kanaldagi e'lon raqamini (masalan, <b>T0012</b>) yozsangiz, o'sha e'lonni ochaman."
    ),
    "lang.choose": "🌐 Tilni tanlang / Выберите язык:",
    "lang.set": "✅ Til: o'zbekcha",
    "rules.text": (
        "ℹ️ <b>Bot qanday ishlaydi?</b>\n\n"
        "1️⃣ Narsa topgan odam bot orqali e'lon beradi.\n"
        "2️⃣ Admin tekshiradi va e'lon kanalga chiqadi.\n"
        "3️⃣ Egasi kanalda narsasini ko'rib, <b>«Bu meniki»</b> tugmasini bosadi.\n"
        "4️⃣ Egalikni isbotlash uchun narsa haqida savollarga javob beradi.\n"
        "5️⃣ Xizmat haqi to'lanadi va bot ikki tomonni bog'lab beradi.\n\n"
        "🔔 Narsangiz hali topilmagan bo'lsa, <b>«Narsa yo'qotdim»</b> bo'limida e'lon qoldiring — "
        "o'xshash narsa topilishi bilan bot sizga xabar beradi.\n\n"
        "💰 Xizmat haqi: <b>{fee} so'm</b>\n"
        "🎁 Shundan <b>{share}%</b> narsani topgan insonga suyunchi sifatida beriladi.\n\n"
        "🔐 <b>Maxfiylik</b>\n"
        "• Pasport va boshqa hujjatlardagi shaxsiy ma'lumotlar kanalda e'lon qilinmaydi.\n"
        "• Telefon va karta raqamingizni faqat admin ko'radi, ikkinchi tomonga faqat to'lovdan keyin beriladi.\n"
        "• E'lon yopilgach {days} kun o'tib telefon, karta va hujjat ma'lumotlari bazadan o'chiriladi."
        "\n\n📜 To'liq shartlar (ommaviy oferta): /oferta"
    ),
    "rules.questions": "\n❓ Savollar uchun: {admin}",

    # ---------- oferta ----------
    "terms.summary": (
        "📜 <b>Davom etishdan oldin — foydalanish shartlari</b>\n\n"
        "• E'lon berish va murojaat qilish bepul. Xizmat haqi (<b>{fee} so'm</b>) faqat egasi "
        "tasdiqlangandan keyin to'lanadi.\n"
        "• Shundan <b>{share}%</b> topuvchiga suyunchi — egasi narsani olganini tasdiqlagach.\n"
        "• Narsa topuvchi aybi bilan topshirilmasa — pul qaytariladi.\n"
        "• Telefon va karta raqamingizni faqat admin ko'radi, ikkinchi tomonga faqat to'lovdan keyin beriladi.\n"
        "• E'lon yopilgach {days} kun o'tib shaxsiy ma'lumotlaringiz o'chiriladi.\n"
        "• Yolg'on ma'lumot va firibgarlik — bloklash.\n\n"
        "To'liq matn — <b>«📄 Oferta matni»</b>. Davom etish uchun <b>«✅ Roziman»</b> ni bosing."
    ),
    "terms.thanks": "Rahmat! ✅",
    "terms.via_bot": "Bot orqali",

    # ---------- narsa topdim ----------
    "found.thanks": "Rahmat, siz yaxshi ish qilyapsiz! 🙌\nBir nechta savolga javob bering.",
    "found.q_category": "1/8. <b>Nima topdingiz?</b> Turini tanlang:",
    "found.category_chosen": "1/8. Tanlandi: <b>{category}</b>",
    "found.q_photo": "2/8. 📸 <b>Topilgan narsaning rasmini yuboring.</b>",
    "found.photo_doc_note": (
        "\n\n🔐 Kanalga rasm <b>xiralashtirilgan</b> holda chiqadi — ism va raqamlar o'qilmaydi. "
        "Aniq rasmni faqat admin ko'radi va u orqali haqiqiy egasini tekshiradi."
    ),
    "found.q_location": (
        "3/8. 📍 <b>Qayerda topdingiz? Lokatsiyani yuboring.</b>\n\n"
        "• Hozir o'sha joyda bo'lsangiz — pastdagi tugmani bosing.\n"
        "• Boshqa joyda bo'lsangiz — 📎 (skrepka) → <b>Joylashuv</b> → xaritadan joyni belgilang.\n"
        "• Yoki <b>«Manzilni qo'lda kiritish»</b> tugmasini bosing."
    ),
    "found.photo_required": "Iltimos, narsaning <b>rasmini</b> yuboring 📸",
    "found.locating": "⏳ Manzil aniqlanmoqda...",
    "found.map_point": "Xaritada belgilangan joy",
    "found.address": "✅ Manzil: <b>{address}</b>",
    "found.location_required": (
        "Iltimos, <b>lokatsiya</b> yuboring yoki <b>«Manzilni qo'lda kiritish»</b> tugmasini bosing 📍"
    ),
    "found.manual": "✍️ Qo'lda kiritamiz.",
    "found.q_region": "3/8. 🗺 <b>Qaysi viloyatda topdingiz?</b>",
    "found.region_chosen": "3/8. 🗺 Viloyat: <b>{region}</b>",
    "found.q_place": (
        "📍 <b>Tuman, ko'cha yoki mo'ljalni yozing:</b>\n"
        "<i>Masalan: Chilonzor tumani, Bunyodkor ko'chasi, «Novza» metrosi yonida</i>"
    ),
    "found.q_landmark": (
        "4/8. 🏠 <b>Aniq mo'ljal</b> (ixtiyoriy)\n"
        "<i>Masalan: «Novza» metrosi chiqishida, avtobus bekatida</i>"
    ),
    "found.q_date": (
        "5/8. 📅 <b>Qaysi kuni topdingiz?</b> Kalendardan tanlang:\n"
        "<i>◀️ tugmasi bilan oldingi oylarga o'tish mumkin</i>"
    ),
    "found.q_time": "5/8. 📅 Sana: <b>{date}</b>\n\n🕐 <b>Soat nechada topdingiz?</b> Taxminiy vaqtni tanlang:",
    "found.time_chosen": "5/8. 📅 Topilgan vaqt: <b>{when}</b>",
    "found.time_required": "Iltimos, yuqoridagi tugmalardan <b>soatni</b> tanlang 👆",
    "found.q_description": "6/8. 📝 <b>Qisqacha izoh yozing.</b>\nBu matn kanalda chiqadi: rangi, holati va h.k.",
    "found.doc_warning": (
        "\n\n⚠️ <b>Hujjatdagi ism-familiya, raqam va boshqa shaxsiy ma'lumotlarni YOZMANG!</b> "
        "Masalan: «Ko'k muqovali pasport, ichida bank karta bor»."
    ),
    "found.q_phone": (
        "7/8. 📞 <b>Telefon raqamingizni yuboring.</b>\n\n"
        "🔒 Raqamingiz <b>kanalda chiqmaydi</b> — uni faqat admin ko'radi. "
        "Egasi topilib, to'lov qilgandan keyingina unga beriladi."
    ),
    "found.q_card": (
        "8/8. 💳 <b>Suyunchi uchun karta raqamingiz</b>\n\n"
        "Egasi topilsa, xizmat haqining <b>{share}%</b> qismi (<b>{amount} so'm</b>) kartangizga o'tkaziladi.\n"
        "🔒 Karta raqami ham faqat adminga ko'rinadi.\n\n"
        "16 xonali karta raqamini yozing yoki o'tkazib yuboring."
    ),
    "found.card_invalid": "Karta raqami 16 ta raqamdan iborat bo'lishi kerak. Qaytadan yozing:",
    "found.private": "🔒 <i>faqat adminga ko'rinadi</i>",
    "found.summary": "<b>{category}</b>\n{location}\n📅 {date}\n📝 {description}\n\n📞 {phone} — {private}\n💳 {card}",
    "found.blurring": "⏳ Rasmdagi shaxsiy ma'lumotlar yashirilmoqda, biroz kuting...",
    "found.published": "✅ E'loningiz kanalga chiqdi! Raqami: <b>#{code}</b>\n",
    "found.published_footer": "\nEgasi topilsa, sizga darhol xabar beramiz. Rahmat! 🙏",
    "found.accepted": (
        "✅ E'loningiz qabul qilindi! Raqami: <b>#{code}</b>\n\n"
        "Admin tekshirgandan so'ng kanalga chiqadi. Egasi topilsa, sizga xabar beramiz. Rahmat! 🙏"
    ),

    # ---------- narsa yo'qotdim ----------
    "lost.intro": "🔍 <b>Narsangizni yo'qotdingizmi?</b>\n\n",
    "lost.channel": "Barcha topilgan narsalar kanalimizda: {link}\n\n",
    "lost.choose": (
        "Quyida turini tanlang — oxirgi topilganlarni ko'rsataman. "
        "Topilmagan bo'lsa, e'lon qoldirasiz va o'xshash narsa topilishi bilan sizga xabar beraman 👇"
    ),
    "lost.list": (
        "{category} — oxirgi topilganlar.\n"
        "Kanalda e'lon raqamini (masalan, <b>T0012</b>) ko'rsangiz, uni botga yozing — o'sha e'lonni ochaman.\n"
        "Narsangiz bo'lsa, ustiga bosing 👇\n\n"
        "Ro'yxatda yo'qmi? <b>«🔔 Topilsa xabar bering»</b> tugmasini bosing."
    ),
    "lost.empty": (
        "{category} bo'yicha hozircha e'lon yo'q 😔\n\n"
        "<b>«🔔 Topilsa xabar bering»</b> tugmasini bosing — o'xshash narsa topilishi bilan sizga darhol yozaman."
    ),
    "lost.max_searches": (
        "Sizda allaqachon {max} ta faol qidiruv bor.\n"
        "Keraksizlarini <b>«{button}»</b> bo'limida to'xtatib, keyin yangisini qo'shing."
    ),
    "lost.report_intro": (
        "🔔 <b>{category}</b> uchun e'lon qoldiramiz.\n"
        "🔒 U kanalga chiqmaydi — faqat mos narsa topilganda sizga xabar berish uchun kerak."
    ),
    "lost.q_region": "1/4. 🗺 <b>Qaysi viloyatda yo'qotdingiz?</b>",
    "lost.region_chosen": "1/4. 🗺 Viloyat: <b>{region}</b>",
    "lost.region_unknown": "aniq bilmayman",
    "lost.q_place": (
        "2/4. 📍 <b>Taxminan qayerda yo'qotdingiz?</b> (ixtiyoriy)\n"
        "<i>Masalan: Chilonzor tumani, 45-avtobusda, «Novza» metrosi atrofida</i>"
    ),
    "lost.q_date": (
        "3/4. 📅 <b>Qaysi kuni yo'qotdingiz?</b> Taxminiy kunni tanlang:\n"
        "<i>◀️ tugmasi bilan oldingi oylarga o'tish mumkin</i>"
    ),
    "lost.date_chosen": "3/4. 📅 Sana: <b>{date}</b>",
    "lost.q_description": (
        "4/4. 📝 <b>Narsangizni qisqacha tasvirlang</b> (ixtiyoriy)\n"
        "<i>Rangi, markasi, o'ziga xos belgilari. Bu matn hech qayerda e'lon qilinmaydi.</i>"
    ),
    "lost.saved": (
        "✅ E'loningiz saqlandi: <b>#{code}</b>\n\n"
        "🔔 O'xshash narsa topilishi bilan sizga darhol xabar beraman.\n"
        "Qidiruvni <b>«{button}»</b> bo'limida to'xtatishingiz mumkin."
    ),
    "lost.matches_now": "👀 Hozirning o'zida <b>{count}</b> ta o'xshash e'lon bor. Narsangiz bo'lsa, ustiga bosing 👇",
    "lost.no_searches": (
        "Sizda faol qidiruv yo'q.\n\n"
        "Biror narsangiz yo'qolgan bo'lsa, <b>«{button}»</b> bo'limida e'lon qoldiring — "
        "o'xshash narsa topilishi bilan sizga xabar beraman 🔔"
    ),
    "lost.my_searches": "🔔 <b>Faol qidiruvlaringiz:</b>\n\n",
    "lost.my_searches_footer": "\n\nNarsangiz topilgan bo'lsa, qidiruvni to'xtating 👇",
    "lost.already_stopped": "Bu qidiruv allaqachon to'xtatilgan",
    "lost.stopped_toast": "Qidiruv to'xtatildi",
    "lost.stopped": "🔕 #{code} qidiruvi to'xtatildi.",
    "match.title": "🔔 <b>Siz qidirayotgan narsaga o'xshash narsa topildi!</b>",
    "match.footer": "Qidiruvingiz: #{code}\nNarsangiz bo'lsa, <b>«🙋 Bu meniki»</b> tugmasini bosing 👇",

    # ---------- murojaat ----------
    "claim.not_available": "Bu e'lon topilmadi yoki egasiga allaqachon qaytarilgan.",
    "claim.own": "Bu o'zingiz bergan e'lon 🙂",
    "claim.already_approved": "Siz bu narsa uchun allaqachon tasdiqlangansiz. To'lov chekini (skrinshot) shu yerga yuboring 📸",
    "claim.in_review": "Murojaatingiz ko'rib chiqilmoqda. Iltimos, kuting ⏳",
    "claim.q_proof_doc": (
        "🔐 <b>Egalikni isbotlang:</b>\n"
        "Hujjat egasining <b>to'liq ism-familiyasini</b> va "
        "hujjat raqamining <b>oxirgi 3 ta raqamini</b> yozing."
    ),
    "claim.q_proof_item": (
        "🔐 <b>Egalikni isbotlang:</b>\n"
        "Narsangizni batafsil tasvirlab bering: rangi, markasi, o'ziga xos belgilari, "
        "ichida nima bor edi va h.k. Kanalda yozilmagan tafsilotlar qanchalik ko'p bo'lsa, shuncha yaxshi."
    ),
    "claim.intro": "Siz <b>#{code}</b> — {category} e'loniga murojaat qilyapsiz.\n\n",
    "claim.q_phone": "📞 <b>Telefon raqamingizni yuboring</b> — tasdiqlangandan keyin topuvchiga beriladi.",
    "claim.inactive": "Afsuski, bu e'lon endi faol emas.",
    "claim.verifying": "⏳ Ma'lumotlaringiz hujjat bilan solishtirilmoqda...",
    "claim.auto_ok": "✅ Ma'lumotlaringiz hujjat bilan mos keldi!",
    "claim.sent": (
        "✅ Murojaatingiz adminga yuborildi.\n"
        "Tekshiruvdan so'ng sizga to'lov ma'lumotlari yuboriladi. Iltimos, kuting ⏳"
    ),
    "claim.unknown_photo": "Rasmni nima uchun yuborganingizni tushunmadim 🤔\nQuyidagi menyudan foydalaning.",
    "claim.receipt_item_gone": (
        "⚠️ #{code} e'loni endi faol emas — narsa boshqa egaga qaytarilgan.\n"
        "Agar to'lov qilib qo'ygan bo'lsangiz, admin bilan bog'laning."
    ),
    "claim.receipt_ok": "✅ Chek qabul qilindi. Admin tekshirgach, topuvchi bilan bog'lab beramiz ⏳",

    # ---------- to'lov ----------
    "pay.congrats": "🎉 <b>Tabriklaymiz!</b> #{code} — {category} sizniki ekanligi tasdiqlandi.\n\n",
    "pay.body": (
        "Topuvchi bilan bog'lanish uchun xizmat haqini to'lang: <b>{fee} so'm</b>\n"
        "🎁 Shundan {share}% narsangizni topgan insonga suyunchi sifatida beriladi.\n"
        "⏳ To'lov uchun {hours} soat vaqt bor, keyin murojaat yopiladi.\n\n"
    ),
    "pay.invoice_title": "Xizmat haqi #{code}",
    "pay.invoice_description": "{category} topgan inson bilan bog'lanish",
    "pay.invoice_label": "Xizmat haqi",
    "pay.online": (
        "💳 Yuqoridagi <b>«To'lash»</b> tugmasini bosing — to'lov tushishi bilan "
        "topuvchining kontaktini darhol yuboraman."
    ),
    "pay.card": (
        "💳 Karta: <code>{card}</code>\n👤 {owner}\n\n"
        "📸 To'lovdan so'ng <b>chek skrinshotini shu yerga yuboring.</b>"
    ),
    "pay.again_intro": "💳 #{code} — {category}\n\n",
    "pay.err_inactive": "Bu to'lov endi amalda emas.",
    "pay.err_returned": "Afsuski, bu narsa boshqa egaga qaytarilgan.",
    "pay.err_fee": "Xizmat haqi o'zgargan. E'londagi «Bu meniki» tugmasini qaytadan bosing.",
    "pay.refund_notice": "⚠️ To'lovingiz qabul qilindi, lekin murojaatingiz endi faol emas. Pulingiz qaytariladi.",
    "deal.owner": (
        "✅ <b>To'lov tasdiqlandi!</b>\n\n"
        "#{code} — {category} topgan inson bilan bog'laning:\n\n"
        "👤 {finder}\n"
        "📞 <b>{phone}</b>\n\n"
        "Narsangizni olishda omad! 🍀\n"
        "💬 Uchrashuvni bot orqali ham kelishib olishingiz mumkin — pastdagi tugma.\n\n"
        "📦 Narsani qo'lingizga olgach, <b>«✅ Narsamni oldim»</b> tugmasini bosing. "
        "Topuvchi bilan bog'lana olmasangiz — pastdagi ikkinchi tugmani bosing, admin yordam beradi."
    ),
    "deal.finder": (
        "🎉 <b>#{code} e'loningiz egasi topildi!</b>\n\n"
        "👤 {owner}\n"
        "📞 <b>{phone}</b>\n\n"
        "U siz bilan bog'lanadi. Narsani topshirishda shaxsini tekshirib oling.\n\n"
        "🎁 Suyunchi: <b>{amount} so'm</b> — egasi narsani olganini tasdiqlagach "
    ),
    "deal.finder_card": "kartangizga ({card}) o'tkaziladi.",
    "deal.finder_no_card": "beriladi. Olish uchun karta raqamingizni adminga yuboring",
    "deal.finder_footer": "\n\nNarsani topshirgach, pastdagi tugmani bosing. Yaxshilik qilganingiz uchun rahmat! 🙏",

    # ---------- narsa topshirildimi ----------
    "ho.not_active": "Bu so'rov endi amalda emas",
    "ho.already_closed": "Bu murojaat allaqachon yopilgan ✅",
    "ho.finder_confirmed": (
        "🎉 #{code}: narsa egasiga topshirilgani tasdiqlandi. Suyunchingiz tez orada o'tkaziladi. Rahmat! 🙏"
    ),
    "ho.owner_yes": "🎉 Ajoyib! Narsangiz qo'lingizga tekkanidan xursandmiz.\nBotimizdan foydalanganingiz uchun rahmat! 🙏",
    "ho.finder_yes": "Rahmat! 🙏 Egasi ham narsani olganini tasdiqlagach, suyunchingiz o'tkaziladi.",
    "ho.ask_owner": (
        "📦 Topuvchi #{code} — {category} narsani sizga topshirganini aytdi.\n"
        "Narsangizni olgan bo'lsangiz, tasdiqlang 👇"
    ),
    "ho.owner_no": (
        "😔 Tushunarli. Admin siz bilan bog'lanib, yordam beradi.\n\n"
        "Topuvchi: {finder} 📞 <b>{phone}</b>\n\n"
        "Narsani olsangiz, pastdagi tugmani bosing 👇"
    ),
    "ho.finder_no": (
        "Tushunarli, admin xabardor qilindi.\n"
        "Egasi bog'lanib, narsani topshirsangiz — pastdagi tugmani bosing 👇"
    ),
    "ho.admin_ok_owner": "✅ #{code}: admin narsa sizga topshirilganini tasdiqladi. Rahmat! 🙏",
    "ho.refund_owner": "↩️ #{code} bo'yicha to'lovingiz qaytarildi. Noqulaylik uchun uzr so'raymiz.",
    "ho.refund_finder": (
        "#{code} bo'yicha kelishuv bekor qilindi — narsa egasiga topshirilmagani uchun suyunchi berilmaydi."
    ),

    # ---------- eslatmalar ----------
    "sch.expired": (
        "⌛ #{code} bo'yicha murojaatingiz {hours} soat ichida to'lov qilinmagani uchun yopildi.\n\n"
        "Narsa hali egasini kutayotgan bo'lsa, kanaldagi <b>«🙋 Bu meniki»</b> tugmasini qaytadan bosishingiz mumkin."
    ),
    "sch.remind": (
        "⏰ <b>Eslatma:</b> #{code} — {category} uchun to'lov hali qilinmagan.\n"
        "Taxminan <b>{left} soat</b> ichida to'lanmasa, murojaat yopiladi.\n\n"
    ),
    "sch.ask_owner": "📦 #{code} — {category}: <b>narsangizni oldingizmi?</b>",
    "sch.ask_finder": "📦 #{code}: <b>narsani egasiga topshirdingizmi?</b>\nSuyunchi topshirilgani tasdiqlangach o'tkaziladi.",
    "sch.search_expired": (
        "⌛ #{code} — {category} qidiruvingiz muddati tugadi ({days} kun).\n\n"
        "Narsangiz hali topilmagan bo'lsa, <b>«{button}»</b> bo'limida yangi e'lon qoldiring."
    ),

    # ---------- admin qarorlari (foydalanuvchiga) ----------
    "adm.removed": "😔 #{code} e'loningiz admin tomonidan olib tashlandi.",
    "adm.rejected": "😔 #{code} e'loningiz admin tomonidan rad etildi.",
    "adm.published": "📢 #{code} e'loningiz kanalga chiqdi! Egasi topilsa, sizga darhol xabar beramiz.",
    "adm.undo": (
        "😔 #{code} e'loni bo'yicha murojaatingiz admin tomonidan qayta ko'rib chiqildi "
        "va tasdiqlanmadi. Iltimos, to'lov qilmang."
    ),
    "adm.claim_rejected": "😔 #{code} e'loni bo'yicha murojaatingiz tasdiqlanmadi. Ma'lumotlar mos kelmadi.",
    "adm.payment_missing": "⚠️ #{code} bo'yicha to'lovingiz topilmadi.\nIltimos, to'lovni tekshirib, chekni qaytadan yuboring.",
    "adm.closed_claimant": (
        "😔 #{code} e'loni yopildi — narsa egasiga qaytarilgan.\n"
        "Agar to'lov qilib qo'ygan bo'lsangiz, admin bilan bog'laning."
    ),
    "adm.closed_finder": "✅ #{code} e'loningiz yopildi — narsa egasiga qaytarildi. Rahmat! 🙏",
    "adm.banned": "⛔ Siz botdan foydalanishdan cheklandingiz.",
    "adm.ban_reason": "\nSabab: {reason}",
    "adm.unbanned": "✅ Cheklov olib tashlandi. Botdan yana foydalanishingiz mumkin: /start",

    # ---------- holatlar ----------
    "item_status.pending": "⏳ Tekshiruvda",
    "item_status.published": "📢 Kanalda",
    "item_status.returned": "✅ Egasiga qaytarildi",
    "item_status.removed": "🗑 O'chirilgan",
    "item_status.rejected": "❌ Rad etilgan",
    "claim_status.checking": "⏳ Egasi tekshirilmoqda",
    "claim_status.awaiting_payment": "💳 To'lov kutilmoqda",
    "claim_status.payment_review": "🧾 Chek tekshirilmoqda",
    "claim_status.completed": "✅ Yakunlangan",
    "claim_status.rejected": "❌ Rad etilgan",
    "claim_status.expired": "⌛ Muddati o'tgan",
    "handover_status.none": "⏳ topshirilishi kutilmoqda",
    "handover_status.confirmed": "🤝 topshirildi",
    "handover_status.disputed": "⚠️ nizo",
    "handover_status.refunded": "↩️ pul qaytarilgan",

    # ---------- Mening e'lonlarim ----------
    "mine.empty": (
        "Sizda hali e'lon yoki murojaat yo'q.\n\n"
        "📦 Biror narsa topsangiz — <b>«{found}»</b>\n"
        "🔍 Narsangizni yo'qotgan bo'lsangiz — <b>«{lost}»</b>"
    ),
    "mine.title": "📋 <b>Mening e'lonlarim</b>",
    "mine.found": "📦 <b>Topgan narsalarim:</b>",
    "mine.claims": "🙋 <b>Murojaatlarim:</b>",
    "mine.hint": "Batafsil ko'rish va boshqarish uchun raqamni bosing 👇",
    "mine.status": "Holati: <b>{status}</b>",
    "mine.open_claims": "🙋 {count} ta murojaat ko'rib chiqilmoqda",
    "mine.payout_waiting": "🎁 Suyunchi ({amount}): egasi narsani olganini tasdiqlagach o'tkaziladi",
    "mine.payout_disputed": "🎁 Suyunchi: ⚠️ admin vaziyatni ko'rib chiqmoqda",
    "mine.payout_refunded": "🎁 Suyunchi: berilmaydi — kelishuv bekor qilingan",
    "mine.payout_done": "🎁 Suyunchi ({amount}): ✅ o'tkazilgan, {date}",
    "mine.payout_soon": "🎁 Suyunchi ({amount}): ⏳ tez orada o'tkaziladi",
    "mine.not_found": "E'lon topilmadi",
    "mine.already_closed": "Bu e'lon allaqachon yopilgan",
    "mine.has_claims": "Bu e'longa murojaat ko'rib chiqilmoqda — hozir yopib bo'lmaydi.",
    "mine.confirm": "Tasdiqlash uchun yana bir bor bosing",
    "mine.closed_toast": "E'lon yopildi ✅",
    "mine.thanks_returned": "🙏 Narsani egasiga qaytarganingiz uchun rahmat!",
    "mine.removed_toast": "E'lon olib tashlandi",
    "mine.not_editable": "Yopilgan e'lonni tahrirlab bo'lmaydi",
    "mine.q_edit": "✏️ #{code} uchun <b>yangi izohni yozing</b> (500 belgigacha).\nKanaldagi e'lon ham yangilanadi.",
    "mine.edit_doc_warning": "\n\n⚠️ <b>Hujjatdagi ism-familiya, raqam va boshqa shaxsiy ma'lumotlarni YOZMANG!</b>",
    "mine.inactive": "Bu e'lon endi faol emas.",
    "mine.edited": "✅ #{code} izohi yangilandi.",
    "mine.text_required": "Iltimos, yangi izohni <b>matn</b> ko'rinishida yozing ✍️",
    "mine.claim_title": "🙋 <b>Murojaat №{id}</b> | #{code} — {category}",
    "mine.claim_checking": "Admin ma'lumotlaringizni tekshirmoqda — natija shu yerga keladi.",
    "mine.claim_fee": "Topuvchi bilan bog'lanish uchun xizmat haqi: <b>{fee}</b>",
    "mine.claim_receipt": "To'lov chekingiz tekshirilmoqda.",
    "mine.claim_item": "Narsa: <b>{status}</b>",
    "mine.finder": "Topuvchi: {finder}",
    "mine.claim_not_found": "Murojaat topilmadi",
    "mine.no_payment": "Bu murojaat bo'yicha to'lov kutilmayapti",
    "mine.item_inactive": "Bu e'lon endi faol emas",

    # ---------- e'lon raqami bo'yicha qidiruv ----------
    "lookup.own": "#{code} — bu o'zingiz bergan e'lon. Uni <b>«{button}»</b> bo'limida boshqarasiz 👇",
    "lookup.not_found": "🤷 #{code} raqamli e'lon topilmadi.\nRaqamni tekshirib, qaytadan yozing (masalan: <b>T0012</b>).",
    "lookup.returned": "✅ #{code} — {category} egasiga allaqachon qaytarilgan.",
    "lookup.press": "Bu narsa sizniki bo'lsa, <b>«🙋 Bu meniki»</b> tugmasini bosing 👇",
    "lookup.search_not_found": "🤷 #{code} raqamli faol qidiruvingiz topilmadi.",
    "lookup.search": "🔔 <b>Qidiruvingiz:</b>\n\n",
    "lookup.not_understood": (
        "🤔 Tushunmadim.\n\n"
        "🔢 Kanaldagi e'lon raqamini bilsangiz, shunchaki yozing — masalan: <b>T0012</b>.\n"
        "Kanaldagi postni botga forward qilsangiz ham bo'ladi.\n\n"
        "Yoki pastdagi menyudan foydalaning: narsangizni yo'qotgan bo'lsangiz — <b>«{button}»</b> 👇"
    ),

    # ---------- chat ----------
    "chat.closed": "Bu yozishma yopilgan",
    "chat.to_finder": "topuvchiga",
    "chat.to_owner": "narsa egasiga",
    "chat.started": (
        "💬 <b>#{code} — {category}</b>\n\n"
        "Endi yozgan xabaringiz {other} bot orqali yetkaziladi: matn, rasm, ovozli xabar, lokatsiya.\n"
        "🔒 Yozishma saqlanadi — kelishmovchilik bo'lsa, admin ko'rib chiqadi.\n\n"
        "Tugatgach, <b>«{button}»</b> tugmasini bosing."
    ),
    "chat.exited": "Chatdan chiqdingiz. Asosiy menyu 👇",
    "chat.closed_menu": "Bu yozishma yopilgan. Asosiy menyu 👇",
    "chat.unsupported": "Bu turdagi xabarni yuborib bo'lmaydi. Matn, rasm, ovozli xabar yoki lokatsiya yuboring.",
    "chat.from_owner": "Narsa egasi",
    "chat.from_finder": "Topuvchi",
    "chat.not_delivered": "⚠️ Xabar yetkazilmadi — ikkinchi tomon botni to'xtatgan bo'lishi mumkin. Telefon orqali bog'laning",
    "chat.write_admin": " yoki adminga yozing: {admin}",
}
