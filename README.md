# 🔎 Yo'qolgan narsalar boti

Topilgan narsalarni egasiga qaytarishga yordam beruvchi Telegram bot.

## Qanday ishlaydi

1. **Topuvchi** botga e'lon beradi: turi, rasmi, **lokatsiya** (manzil avtomatik aniqlanadi), mo'ljal, sana va kunning qismi, izoh, telefon va karta raqami. Telefon va karta raqami faqat adminga ko'rinadi.
2. E'lon darhol **kanalga** chiqadi: hujjatlar rasmsiz, boshqa narsalar rasm bilan. Postda xaritaga havola va **"🙋 Bu meniki"** tugmasi bo'ladi.
3. **Admin guruhga** e'lonning nusxasi keladi, admin kerak bo'lsa uni **🗑 o'chira** oladi. Agar `.env` da `AUTO_PUBLISH=false` bo'lsa, e'lon avval admin tasdig'idan o'tadi.
4. **Egasi** tugmani bosib egalikni isbotlaydi: hujjat bo'lsa ism-familiya va raqamning oxirgi 3 ta raqamini yozadi, narsa bo'lsa batafsil tavsif beradi.
5. **Hujjat bo'lsa**, bot asl rasmni OCR bilan o'qib, javobni o'zi solishtiradi. Ism-familiya **va** raqam mos kelsa, admin'siz tasdiqlanadi (admin guruhga "↩️ Bekor qilish" tugmasi bilan xabar boradi). Aks holda, yoki narsa bo'lsa, admin rasm bilan solishtirib qaror qiladi.
6. Egasi to'laydi: `PAYMENT_PROVIDER_TOKEN` bo'lsa **bot ichida Click/Payme orqali**, bo'lmasa kartaga o'tkazib **chek skrinshotini** yuboradi.
7. Onlayn to'lov tushishi bilan (chek bo'lsa, admin tasdiqlagach) bot ikki tomonga bir-birining kontaktini yuboradi, kanaldagi post "✅ EGASIGA QAYTARILDI" ga o'zgaradi. Adminga topuvchiga qancha suyunchi o'tkazish kerakligi haqida eslatma keladi.

### Yo'qotdim e'lonlari

Narsasini yo'qotgan odam **"Narsa yo'qotdim"** bo'limida turini tanlaydi va oxirgi topilganlarni ko'radi. Narsasi ro'yxatda bo'lmasa, **"🔔 Topilsa xabar bering"** tugmasini bosib e'lon qoldiradi: viloyat, taxminiy joy, sana va tavsif. Bu e'lon kanalga chiqmaydi.

Yangi topilgan narsa kanalga chiqqanda bot uni faol qidiruvlar bilan solishtiradi (`matching.py`). Turi bir xil, viloyati mos (ikkalasida ham ko'rsatilgan bo'lsa) va yo'qotilgan kundan keyin 60 kun ichida topilgan bo'lsa, egasiga **"🙋 Bu meniki"** tugmasi bilan xabar boradi. Qidiruvlarni **"🔔 Qidiruvlarim"** bo'limida ko'rish va to'xtatish mumkin. Narsa egasiga qaytarilsa, qidiruv avtomatik yopiladi.

### Mening e'lonlarim (`handlers/mine.py`)

**"📋 Mening e'lonlarim"** bo'limida foydalanuvchi o'zi bergan e'lonlarni va qilgan murojaatlarini holati bilan ko'radi. Raqamni bossa, batafsil karta ochiladi.

- **Topuvchi:** kanaldagi postga havola, nechta murojaat ko'rib chiqilayotgani, suyunchi holati (kutilmoqda / o'tkazilgan). E'lon izohini o'zgartira oladi: kanaldagi post yangilanadi, adminga eski va yangi matn boradi. "🤝 Egasiga o'zim qaytardim" yoki "🗑 E'lonni olib tashlash" bilan e'lonni yopadi (ikki marta bosib tasdiqlanadi). Murojaat ko'rib chiqilayotgan bo'lsa, e'lonni yopib bo'lmaydi.
- **Egasi:** murojaat holati. To'lov kutilayotgan bo'lsa, to'lov ma'lumotlarini qayta oladi. To'lovdan keyin topuvchi kontakti va "✅ Narsamni oldim" tugmasi ko'rinadi.

### E'lon raqami bo'yicha tez qidiruv (`handlers/lookup.py`)

Foydalanuvchi botga kanaldagi e'lon raqamini yozsa (`T0012`, `#T12`, kirillcha `Т0012` ham bo'ladi) yoki kanal postini botga forward qilsa, bot o'sha e'lonni **"🙋 Bu meniki"** va **"👀 Kanalda ko'rish"** tugmalari bilan ko'rsatadi. Hujjatlarning aniq rasmi ko'rsatilmaydi. O'z e'lonini yozsa, "Mening e'lonlarim" kartasi ochiladi. `Y0003` yozilsa, o'zining qidiruvi ochiladi. Tanilmagan matnga bot javobsiz qolmaydi: qanday foydalanishni tushuntiradi.

### Bot orqali yozishma (`handlers/chat.py`)

To'lovdan keyin egasi va topuvchi **"💬 Bot orqali yozish"** tugmasi bilan bir-biriga yozadi: matn, rasm, ovozli xabar, lokatsiya va boshqalar ikkinchi tomonga yetkaziladi va bazada saqlanadi (nizo bo'lsa admin ko'radi). Yozishma to'lovdan keyin `CHAT_DAYS` (standart 14) kun ochiq turadi.

### Ikki til: o'zbekcha va ruscha (`i18n.py`, `locales/`)

Birinchi `/start` da til Telegram ilovasi tilidan aniqlanadi (`ru` → ruscha, qolgani o'zbekcha) va o'zgartirish taklif qilinadi. Keyin `/lang` yoki menyudagi til tugmasi bilan almashtiriladi, tanlov bazada saqlanadi. Boshqa foydalanuvchiga boradigan xabarlar (to'lov, yozishma, eslatmalar) **qabul qiluvchining** tilida yuboriladi. Admin guruh va kanal postlari o'zbekcha qoladi. Ofertaning ruscha matni — `OFERTA_RU.md`.

Yangi matn qo'shganda kalitni `locales/uz.py` va `locales/ru.py` ikkalasiga ham qo'shing — `test_i18n.py` kalitlar va `{...}` o'rinlari bir xilligini tekshiradi.

### Narsa qo'lga tekkanini tasdiqlash (`handlers/handover.py`)

To'lovdan so'ng egasi **"✅ Narsamni oldim"**, topuvchi **"✅ Egasiga topshirdim"** tugmasini oladi. **Suyunchi faqat egasi tasdiqlagach** so'raladi (admin guruhga "💸 Suyunchi o'tkazish kerak" xabari va `/payouts`).

- 24 soatda javob bo'lmasa, bot javob bermagan tomondan o'zi so'raydi. Yana 48 soatda egasi javob bermasa, adminga xabar boradi.
- "⚠️ bog'lana olmayapman" bosilsa, adminga **nizo** xabari boradi: ikkala tomon kontakti va **"✅ Topshirildi"** (suyunchiga ruxsat) yoki **"↩️ Pul qaytarildi"** (suyunchi berilmaydi, tushumdan chiqariladi) tugmalari.
- `/stats` da "topshirilishi kutilmoqda" va "nizolar" soni ko'rinadi.

### Eslatmalar va maxfiylik (`scheduler.py`, har 15 daqiqada)

- Egasi tasdiqlangandan keyin **24 soat** to'lamasa, eslatma oladi. **48 soatda** murojaat yopiladi va narsa boshqalar uchun yana ochiladi.
- Murojaat yoki chek **3 soat** ko'rib chiqilmasa, admin guruhga umumiy eslatma boradi.
- Muddati (60 kun) o'tgan "yo'qotdim" qidiruvlari yopiladi va egasiga xabar beriladi.
- E'lon yopilishi bilan hujjatdan OCR o'qigan matn o'chiriladi. Yopilganiga **90 kun** bo'lgan e'lon va murojaatlardan telefon, karta, isbot va chek o'chiriladi, yopiq qidiruvlar butunlay o'chiriladi.

Muddatlarni `.env` da o'zgartirish mumkin: `PAYMENT_REMIND_HOURS`, `PAYMENT_EXPIRE_HOURS`, `ADMIN_REMIND_HOURS`, `DATA_RETENTION_DAYS`.

> Admin guruhdagi rasmlar Telegram'da saqlanadi, bot ularni o'chira olmaydi. Guruh sozlamalarida **"Xabarlarni avtomatik o'chirish"** ni (masalan, 1 oy) yoqing.

### Ommaviy oferta (`OFERTA.md`)

Foydalanuvchi birinchi marta e'lon bermoqchi, murojaat qilmoqchi yoki qidiruv ochmoqchi bo'lganda bot shartlarning qisqa mazmunini ko'rsatadi va **"✅ Roziman"** ni so'raydi. Rozilikdan keyin foydalanuvchi to'xtagan joyidan davom etadi. To'liq matn: `/oferta`.

- **Ishga tushirishdan oldin** `OFERTA.md` dagi `[...]` joylarni (F.I.Sh./MChJ, STIR, manzil, hisob raqam, telefon) to'ldiring va matnni yuristga ko'rsating.
- `{fee}` kabi joylarga bot `.env` dagi qiymatlarni o'zi qo'yadi (xizmat haqi, suyunchi foizi, muddatlar).
- Matnni o'zgartirsangiz, birinchi qatordagi `Tahrir:` sanasini yangilang. Shunda bot hammadan rozilikni qaytadan so'raydi.
- Click/Payme oferta **havolasini** so'rasa: matnni telegra.ph sahifasiga joylab, havolani `.env` dagi `OFFER_URL` ga yozing.

### Onlayn to'lovni ulash (Click / Payme)

1. Click yoki Payme'da merchant (YaTT/MChJ) sifatida ro'yxatdan o'ting.
2. @BotFather → botingiz → **Payments** → Click yoki Payme'ni tanlang va ko'rsatmalarga amal qiling.
3. Berilgan tokenni `.env` dagi `PAYMENT_PROVIDER_TOKEN` ga yozing va botni qayta ishga tushiring.

Avval **test** tokeni bilan sinab ko'ring (BotFather ikkalasini ham beradi).

## Sozlash

1. Kutubxonalarni o'rnating: `pip install -r requirements.txt`
2. [@BotFather](https://t.me/BotFather) da bot yarating va tokenni oling.
3. Telegram **kanal** oching va botni kanalga **admin** qilib qo'shing ("Xabar joylash" va "Tahrirlash" huquqlari bilan).
4. **Admin guruh** oching va botni guruhga qo'shing.
5. `.env.example` faylidan nusxa olib, nomini `.env` qiling va tokenni yozing.
6. Botni ishga tushiring: `python main.py`
7. Admin guruhda `/id` yozing. Chiqqan Chat ID ni `.env` dagi `ADMIN_GROUP_ID` ga yozing va botni qayta ishga tushiring.

## Testlar

Har bir o'zgarishdan keyin (ayniqsa serverga yuklashdan oldin) testlarni ishga tushiring:

```bash
pip install -r requirements-dev.txt   # bir marta
pytest                                # ~5 soniya
pytest -m ocr                         # + haqiqiy OCR testi (sekin, ~30 soniya)
```

Testlar haqiqiy bot kodini aiogram Dispatcher orqali ishlatadi, lekin Telegram'ga hech narsa yuborilmaydi (`tests/fakes.py`) va har bir test alohida bo'sh bazada ishlaydi. `.env` dagi sozlamalar testlarga ta'sir qilmaydi.

| Fayl | Nimani tekshiradi |
|---|---|
| `test_flows.py` | "Yo'qotdim" e'loni, mos narsa chiqqanda xabar, hujjatni avtomatik tasdiqlash, onlayn to'lov |
| `test_handover.py` | Narsa topshirilishini tasdiqlash, nizolar, suyunchi faqat tasdiqdan keyin |
| `test_chat.py` | Egasi va topuvchi o'rtasidagi yozishma |
| `test_i18n.py` | Lug'atlar to'liqligi, ruscha foydalanuvchi yo'li, har tomonga o'z tilida xabar |
| `test_lookup.py` | E'lon raqami va forward bo'yicha qidiruv, tanilmagan matnga javob |
| `test_mine.py` | "Mening e'lonlarim": ro'yxat, izohni tahrirlash, e'lonni yopish, murojaat holati |
| `test_panel.py` | Admin panel: `/find`, ban, `/payouts`, `/export`, `/broadcast` |
| `test_stats.py` | `/stats` tugmalari, grafik, matn va grafik raqamlari bir xilligi |
| `test_scheduler.py` | Eslatmalar, muddati o'tganlarni yopish |
| `test_database.py` | Eski bazadan ko'chish, shaxsiy ma'lumotlarni tozalash |
| `test_backup_alerts.py` | Zaxira nusxa, xatolar haqida adminga xabar |
| `test_verify.py`, `test_matching.py` | OCR tekshiruvi, yo'qotilgan va topilganni moslashtirish |

## Serverga joylash

Docker, nginx va SSL bo'yicha to'liq qo'llanma: **[DEPLOY.md](DEPLOY.md)**

## Buyruqlar

| Buyruq | Qayerda | Vazifasi |
|---|---|---|
| `/start` | bot | Asosiy menyu |
| `/cancel` | bot | Jarayonni bekor qilish |
| `/lang` | bot | Tilni o'zgartirish (o'zbekcha / ruscha) |
| `/oferta` | bot | Foydalanish shartlari |
| `/id` | istalgan joyda | Chat ID ni bilish |
| `/help` | admin guruh | Admin panel buyruqlari |
| `/find` | admin guruh | Qidirish: `T0012` (e'lon), `m15` (murojaat), `Y0003` (qidiruv), telefon, `@username` yoki ID. Kartochkada tugmalar: rasm, kanaldan o'chirish, "qaytarildi" deb yopish, bloklash |
| `/stats` | admin guruh | Bugun / 7 kun / 30 kun / jami: e'lonlar, qaytarilganlar, tushum; eng ko'p turlar va hududlar |
| `/payouts` | admin guruh | O'tkazilmagan suyunchilar va "✅ O'tkazildi" tugmalari |
| `/export` | admin guruh | Bazani Excel (.xlsx) faylga |
| `/ban`, `/unban` | admin guruh | `/ban @username sabab` — bloklangan foydalanuvchi botdan foydalana olmaydi |
| `/broadcast` | admin guruh | Guruhdagi xabarga **reply** qilib yozing — barcha foydalanuvchilarga yuboriladi |
| `/pending` | admin guruh | Kanalga chiqmay qolgan e'lonlar |
| `/backup` | admin guruh | Bazaning zaxira nusxasi (har kuni soat 03:00 da avtomatik ham keladi) |

## Fayllar

- `main.py` – botni ishga tushirish
- `config.py` – sozlamalar, kategoriyalar va hududlar
- `database.py` – SQLite bazasi
- `keyboards.py` – tugmalar
- `utils.py` – post matnlari va yordamchi funksiyalar
- `services.py` – kanalga e'lon chiqarish va yo'qotganlarga xabar berish
- `matching.py` – yo'qotilgan va topilgan narsalarni moslashtirish
- `geo.py` – lokatsiyadan manzilni aniqlash (OpenStreetMap)
- `handlers/found.py` – narsa topgan odam uchun bo'lim
- `handlers/claim.py` – egasi murojaati va to'lov cheki
- `handlers/payments.py` – Click/Payme orqali onlayn to'lov
- `verify.py` – hujjat egasini OCR bilan avtomatik tekshirish
- `handlers/admin.py` – admin tugmalari
- `handlers/start.py` – menyu, qoidalar
- `handlers/lost.py` – qidiruv, "yo'qotdim" e'lonlari, qidiruvlarim
- `handlers/mine.py` – "Mening e'lonlarim"
- `handlers/lookup.py` – e'lon raqami va forward bo'yicha qidiruv
- `handlers/chat.py` – egasi va topuvchi o'rtasidagi yozishma
- `i18n.py`, `locales/uz.py`, `locales/ru.py` – ikki tildagi matnlar

## Rejadagi ishlar

- [ ] Instagramga avtomatik joylash (Meta Graph API)
- [x] Payme/Click orqali avtomatik to'lov
- [x] "Yo'qotdim" e'lonlari va topilgan narsalar bilan avtomatik moslashtirish
