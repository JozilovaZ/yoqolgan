# 🚀 Serverga joylash

## Server talablari

| | Minimum |
|---|---|
| OS | Ubuntu 22.04 / 24.04 |
| RAM | **2 GB** (OCR modeli ~1 GB ishlatadi) |
| Disk | 10 GB |
| CPU | 1–2 yadro |

---

## 1. Serverga Docker o'rnatish

```bash
ssh root@SERVER_IP

curl -fsSL https://get.docker.com | sh
docker --version
docker compose version
```

## 2. Loyihani serverga ko'chirish

**Variant A — GitHub orqali** (tavsiya):
```bash
git clone https://github.com/USERNAME/yoqolgan.git
cd yoqolgan
```

**Variant B — kompyuterdan to'g'ridan-to'g'ri** (Windows PowerShell'da):
```powershell
scp -r D:\topshiriqlar\yoqolgan root@SERVER_IP:/root/
```
> `.env` va `bot.db` ham ko'chadi. GitHub orqali bo'lsa — ular yuklanmaydi (`.gitignore`), qo'lda yaratasiz.

## 3. `.env` faylini tayyorlash

```bash
cd /root/yoqolgan
cp .env.example .env     # agar .env yo'q bo'lsa
nano .env                # BOT_TOKEN, ADMIN_GROUP_ID, CHANNEL_ID, CARD_NUMBER ...
```

## 4. ⚠️ Kompyuterdagi botni to'xtating!

Bitta bot bir vaqtda faqat **bitta joyda** ishlashi mumkin. Kompyuterda `python main.py` ishlab turgan bo'lsa — **to'xtating** (PyCharm'da ⏹ yoki terminalda `Ctrl+C`).
Aks holda xato chiqadi: `TelegramConflictError: terminated by other getUpdates request`.

---

## 5-A. Oddiy ishga tushirish (nginx'siz) — tavsiya etiladi

Domen, SSL kerak emas. Bot o'zi Telegram'dan yangiliklarni so'rab turadi (polling).

```bash
docker compose up -d --build
```

Birinchi build **5–10 daqiqa** davom etadi (torch va OCR modeli yuklanadi). Keyingilari tez.

Tekshirish:
```bash
docker compose logs -f bot
# "Bot ishga tushdi (polling)" chiqishi kerak. Chiqish: Ctrl+C
```

---

## 5-B. Nginx + SSL + webhook bilan (domen kerak)

Telegram xabarlarni o'zi serverga yuboradi. Domen kerak (masalan `bot.izla.uz`).

**1) DNS:** domen provayderida `A` yozuv qo'shing: `bot.izla.uz → SERVER_IP`. Tekshirish:
```bash
ping bot.izla.uz      # SERVER_IP chiqishi kerak
```

**2) `.env` ga qo'shing:**
```env
DOMAIN=bot.izla.uz
LETSENCRYPT_EMAIL=sizning@email.com
WEBHOOK_URL=https://bot.izla.uz
WEBHOOK_SECRET=istalgan_uzun_maxfiy_soz_123
```

**3) Portlarni oching** (agar firewall yoqilgan bo'lsa):
```bash
ufw allow 80 && ufw allow 443 && ufw allow OpenSSH
```

**4) SSL sertifikat oling** (bir marta, bepul Let's Encrypt):
```bash
sh deploy/get-ssl.sh
```

**5) Ishga tushiring:**
```bash
docker compose --profile webhook up -d --build
```

**6) Tekshiring:**
```bash
curl https://bot.izla.uz/health        # "ok" chiqishi kerak
docker compose logs -f bot             # "Bot ishga tushdi (webhook)"
```

Sertifikat har 12 soatda avtomatik tekshiriladi va muddati tugashidan oldin yangilanadi.

> **Webhook'dan polling'ga qaytish:** `.env` dagi `WEBHOOK_URL=` ni bo'shating va
> `docker compose --profile webhook down && docker compose up -d`

---

## 🛠 Kundalik buyruqlar

| Vazifa | Buyruq |
|---|---|
| Loglarni ko'rish | `docker compose logs -f bot` |
| Qayta ishga tushirish | `docker compose restart bot` |
| To'xtatish | `docker compose down` |
| Holatini ko'rish | `docker compose ps` |
| Kodni yangilash | `git pull && docker compose up -d --build` |
| `.env` o'zgardi | `docker compose up -d` (qayta yaratadi) |

> Webhook rejimida har bir buyruqqa `--profile webhook` qo'shing.

## 💾 Ma'lumotlar bazasi zaxirasi

Baza Docker volume'da saqlanadi — konteyner o'chsa ham, qayta build qilinsa ham yo'qolmaydi.

```bash
# Zaxira nusxa olish
docker compose cp bot:/app/data/bot.db ./backup-$(date +%F).db

# Kompyuterdagi eski bazani serverga ko'chirish (birinchi marta)
docker compose cp ./bot.db bot:/app/data/bot.db && docker compose restart bot
```

**Telegram'ga avtomatik zaxira (tavsiya):** bot har kuni soat 03:00 da bazani siqilgan fayl (`.db.gz`) qilib admin guruhga yuboradi. Alohida yopiq kanalga yuborish uchun `.env` ga `BACKUP_CHAT_ID=-100...` yozing (botni kanalga admin qiling). Qo'lda olish: admin guruhda `/backup`.

### Zaxiradan tiklash

```bash
# 1. Telegram'dan izla-backup-....db.gz faylini serverga yuklang (masalan, scp bilan), keyin:
gunzip izla-backup-2026-10-15-0300.db.gz
docker compose stop bot
docker compose cp izla-backup-2026-10-15-0300.db bot:/app/data/bot.db
docker compose start bot
```

Serverda ham zaxira (cron, soat 03:00):
```bash
crontab -e
# Qo'shing:
0 3 * * * cd /root/yoqolgan && docker compose cp bot:/app/data/bot.db ./backups/bot-$(date +\%F).db
```
(Avval `mkdir -p /root/yoqolgan/backups`)

## ❓ Muammolar

| Xato | Yechim |
|---|---|
| `TelegramConflictError` | Bot boshqa joyda ham ishlayapti — kompyuterdagini to'xtating |
| `Killed` yoki konteyner qayta-qayta o'chadi | RAM yetmayapti — 2 GB+ server yoki swap qo'shing (pastda) |
| `get-ssl.sh` xato beradi | DNS hali tarqalmagan (10–60 daqiqa kuting) yoki 80-port yopiq |
| Kalendarda sana noto'g'ri | `TZ=Asia/Tashkent` Dockerfile'da bor — `docker compose up -d --build` |

**Swap qo'shish** (1 GB RAM'li server uchun):
```bash
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```
