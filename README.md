# 🔎 Yo'qolgan narsalar boti

Topilgan narsalarni egasiga qaytarishga yordam beruvchi Telegram bot.

## Qanday ishlaydi

1. **Topuvchi** botga e'lon beradi: turi, rasmi, **lokatsiya** (manzil avtomatik aniqlanadi), mo'ljal, sana va kunning qismi, izoh, telefon va karta raqami. Telefon va karta raqami faqat adminga ko'rinadi.
2. E'lon darhol **kanalga** chiqadi: hujjatlar rasmsiz, boshqa narsalar rasm bilan. Postda xaritaga havola va **"🙋 Bu meniki"** tugmasi bo'ladi.
3. **Admin guruhga** e'lonning nusxasi keladi, admin kerak bo'lsa uni **🗑 o'chira** oladi. Agar `.env` da `AUTO_PUBLISH=false` bo'lsa, e'lon avval admin tasdig'idan o'tadi.
4. **Egasi** tugmani bosib egalikni isbotlaydi: hujjat bo'lsa ism-familiya va raqamning oxirgi 3 ta raqamini yozadi, narsa bo'lsa batafsil tavsif beradi.
5. Admin egasining javobini rasm bilan solishtiradi va tasdiqlaydi.
6. Egasi kartaga pul o'tkazib, **chek skrinshotini** yuboradi.
7. Admin to'lovni tasdiqlaydi. Bot ikki tomonga bir-birining kontaktini yuboradi, kanaldagi post "✅ EGASIGA QAYTARILDI" ga o'zgaradi. Adminga topuvchiga qancha suyunchi o'tkazish kerakligi haqida eslatma keladi.

## Sozlash

1. Kutubxonalarni o'rnating: `pip install -r requirements.txt`
2. [@BotFather](https://t.me/BotFather) da bot yarating va tokenni oling.
3. Telegram **kanal** oching va botni kanalga **admin** qilib qo'shing ("Xabar joylash" va "Tahrirlash" huquqlari bilan).
4. **Admin guruh** oching va botni guruhga qo'shing.
5. `.env.example` faylidan nusxa olib, nomini `.env` qiling va tokenni yozing.
6. Botni ishga tushiring: `python main.py`
7. Admin guruhda `/id` yozing. Chiqqan Chat ID ni `.env` dagi `ADMIN_GROUP_ID` ga yozing va botni qayta ishga tushiring.

## Serverga joylash

Docker, nginx va SSL bo'yicha to'liq qo'llanma: **[DEPLOY.md](DEPLOY.md)**

## Buyruqlar

| Buyruq | Qayerda | Vazifasi |
|---|---|---|
| `/start` | bot | Asosiy menyu |
| `/cancel` | bot | Jarayonni bekor qilish |
| `/id` | istalgan joyda | Chat ID ni bilish |
| `/stats` | admin guruh | Statistika |
| `/pending` | admin guruh | Kanalga chiqmay qolgan e'lonlar |

## Fayllar

- `main.py` – botni ishga tushirish
- `config.py` – sozlamalar, kategoriyalar va hududlar
- `database.py` – SQLite bazasi
- `keyboards.py` – tugmalar
- `utils.py` – post matnlari va yordamchi funksiyalar
- `services.py` – kanalga e'lon chiqarish
- `geo.py` – lokatsiyadan manzilni aniqlash (OpenStreetMap)
- `handlers/found.py` – narsa topgan odam uchun bo'lim
- `handlers/claim.py` – egasi murojaati va to'lov cheki
- `handlers/admin.py` – admin tugmalari
- `handlers/start.py` – menyu, qoidalar, qidiruv

## Rejadagi ishlar

- [ ] Instagramga avtomatik joylash (Meta Graph API)
- [ ] Payme/Click orqali avtomatik to'lov
- [ ] "Yo'qotdim" e'lonlari va topilgan narsalar bilan avtomatik moslashtirish
