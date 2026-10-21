import logging
from html import escape

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import BufferedInputFile, LabeledPrice, LinkPreviewOptions

import database as db
import instagram
import visual
from config import (
    ADMIN_GROUP_ID,
    ADMIN_USERNAME,
    CARD_NUMBER,
    CARD_OWNER,
    CHANNEL_ID,
    CHANNEL_LINK,
    FINDER_SHARE,
    PAYMENT_EXPIRE_HOURS,
    PAYMENT_PROVIDER_TOKEN,
    SERVICE_FEE,
)
from docnumber import fingerprint, numbers_in_text
from i18n import t, user_lang
from images import blurred_photo
from keyboards import channel_post_kb, dispute_kb, handover_kb, lost_match_kb, payout_kb
from matching import is_match
from utils import (
    category_label,
    channel_post_text,
    is_document,
    item_code,
    lost_code,
    lost_match_text,
    money,
    safe_send,
    user_link,
)

logger = logging.getLogger(__name__)

# Bu hujjatlarda faqat yuz rasmi xiralashadi, qolganlarida (bank karta va h.k.) — butun rasm
FACE_BLUR_CATEGORIES = {"passport", "id_card", "driver"}


def default_mode(item: dict) -> str:
    """Hujjatlar xira rasm bilan, qolganlari oddiy rasm bilan chiqadi."""
    return "blur" if is_document(item["category"]) else "photo"


async def publish_item(bot: Bot, item: dict, mode: str) -> int:
    """E'lonni kanalga chiqaradi.

    mode: 'photo' — rasm bilan, 'blur' — xiralashtirilgan rasm bilan, 'text' — rasmsiz.
    Xato bo'lsa TelegramAPIError ko'taradi (masalan, bot kanalda admin emas).
    """
    me = await bot.me()
    text = channel_post_text(item)
    keyboard = channel_post_kb(me.username, item["id"])
    if mode == "photo":
        post = await bot.send_photo(CHANNEL_ID, item["photo_id"], caption=text, reply_markup=keyboard)
    elif mode == "blur":
        faces_only = item["category"] in FACE_BLUR_CATEGORIES
        photo = BufferedInputFile(await blurred_photo(bot, item["photo_id"], faces_only), filename="photo.jpg")
        post = await bot.send_photo(CHANNEL_ID, photo, caption=text, reply_markup=keyboard)
    else:
        post = await bot.send_message(
            CHANNEL_ID, text, reply_markup=keyboard, link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
    await db.update_item(item["id"], status="published", publish_mode=mode, channel_msg_id=post.message_id)
    # Instagram'ga kanaldagi rasmning o'zi ketadi (xiralashtirilgan bo'lsa — xiralashtirilgani)
    await instagram.enqueue(bot, item["id"], post.photo[-1].file_id if post.photo else None)
    # Rasm barmoq izi — "yo'qotdim" e'lonlaridagi rasmlar bilan solishtirish uchun (hujjatlarda — raqam bo'yicha)
    if mode == "photo" and not is_document(item["category"]):
        embedding = await visual.embed(bot, item["photo_id"])
        if embedding:
            await db.update_item(item["id"], embedding=embedding)
            item = {**item, "embedding": embedding}
    try:
        await notify_lost_owners(bot, item, post.message_id)
        await notify_document_owners(bot, item["id"])  # OCR hali tugamagan bo'lsa — tugagach verify.py chaqiradi
    except Exception as error:  # xabar yuborilmasa ham e'lon kanalda qoladi
        logger.error("Yo'qotganlarga xabar yuborilmadi: %s", error)
    return post.message_id


async def notify_lost_owners(bot: Bot, item: dict, message_id: int) -> None:
    """Yangi e'longa mos keladigan "yo'qotdim" e'lonlari egalariga xabar beradi."""
    notified: set[int] = set()
    for report in await db.list_active_lost_reports(item["category"]):
        if report["owner_id"] in notified or not is_match(report, item):
            continue
        notified.add(report["owner_id"])
        lang = await user_lang(report["owner_id"])
        photo_level = visual.level(visual.similarity(item.get("embedding"), report["embedding"]))
        await safe_send(
            bot,
            report["owner_id"],
            lost_match_text(item, report, lang, photo_level=photo_level),
            reply_markup=lost_match_kb(item["id"], report["id"], post_link(message_id), lang),
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
    if notified:
        logger.info("#%s: %d ta yo'qotganga xabar berildi", item["id"], len(notified))


async def _send_document_match(bot: Bot, item: dict, report: dict) -> None:
    """Hujjat raqami mos keldi. Har bir (qidiruv, e'lon) jufti uchun bir marta."""
    if report["owner_id"] == item["finder_id"] or not await db.add_doc_hit(report["id"], item["id"]):
        return
    lang = await user_lang(report["owner_id"])
    await safe_send(
        bot,
        report["owner_id"],
        lost_match_text(item, report, lang, by_number=True),
        reply_markup=lost_match_kb(item["id"], report["id"], post_link(item["channel_msg_id"]), lang),
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )
    logger.info("#%s: hujjat raqami %s qidiruviga mos keldi", item["id"], lost_code(report["id"]))


async def notify_document_owners(bot: Bot, item_id: int) -> None:
    """Topilgan hujjatdagi raqam (OCR) "yo'qotdim" e'lonidagi raqamga mos kelsa — egasiga darhol xabar.

    Viloyat va sana hisobga olinmaydi: raqam mos kelishi o'zi yetarli. OCR tugaganda ham, e'lon kanalga
    chiqqanda ham chaqiriladi — qaysi biri keyin bo'lsa, o'shanda xabar ketadi.
    """
    item = await db.get_item(item_id)
    if not item or item["status"] != "published" or not item["ocr_text"]:
        return
    numbers = numbers_in_text(item["ocr_text"].split("\n"))
    for report in await db.find_lost_reports_by_doc([fingerprint(number) for number in numbers]):
        await _send_document_match(bot, item, report)


async def match_report_documents(bot: Bot, report: dict) -> None:
    """Yangi qidiruv: kanalda allaqachon turgan hujjatlar orasida shu raqamlisi bormi."""
    if not report["doc_hash"]:
        return
    for item in await db.list_published_documents():
        if report["doc_hash"] in {fingerprint(number) for number in numbers_in_text(item["ocr_text"].split("\n"))}:
            await _send_document_match(bot, item, report)


def post_link(message_id: int) -> str:
    return f"{CHANNEL_LINK}/{message_id}" if CHANNEL_LINK else ""


# ---------- to'lov ----------

async def request_payment(bot: Bot, claim: dict, item: dict, intro: str = "") -> None:
    """Egasi tasdiqlangach to'lov so'raladi: onlayn (Click/Payme) yoki karta + chek.

    intro — boshidagi matn (sukut bo'yicha tabrik; eslatmada boshqacha).
    """
    code = item_code(item["id"])
    lang = await user_lang(claim["owner_id"])
    category = category_label(item["category"], lang)
    intro = intro or t("pay.congrats", lang, code=code, category=category)
    text = intro + t("pay.body", lang, fee=money(SERVICE_FEE), share=FINDER_SHARE, hours=PAYMENT_EXPIRE_HOURS)
    if PAYMENT_PROVIDER_TOKEN:
        try:
            await bot.send_invoice(
                claim["owner_id"],
                title=t("pay.invoice_title", lang, code=code),
                description=t("pay.invoice_description", lang, category=category),
                payload=f"claim:{claim['id']}",
                provider_token=PAYMENT_PROVIDER_TOKEN,
                currency="UZS",
                prices=[LabeledPrice(label=t("pay.invoice_label", lang), amount=SERVICE_FEE * 100)],  # tiyinda
            )
            await safe_send(bot, claim["owner_id"], text + t("pay.online", lang))
            return
        except TelegramAPIError as error:
            logger.error("Invoice yuborilmadi, karta orqali to'lovga o'tildi: %s", error)

    await safe_send(
        bot,
        claim["owner_id"],
        text + t("pay.card", lang, card=escape(CARD_NUMBER), owner=escape(CARD_OWNER)),
    )


async def _edit_post(bot: Bot, item: dict, text: str, keyboard) -> None:
    try:
        if item["publish_mode"] in ("photo", "blur"):
            await bot.edit_message_caption(
                chat_id=CHANNEL_ID, message_id=item["channel_msg_id"], caption=text, reply_markup=keyboard
            )
        else:
            await bot.edit_message_text(
                text,
                chat_id=CHANNEL_ID,
                message_id=item["channel_msg_id"],
                reply_markup=keyboard,
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )
    except TelegramAPIError as error:
        logger.warning("Kanal posti yangilanmadi: %s", error)


async def mark_post_returned(bot: Bot, item: dict) -> None:
    """Kanaldagi post "✅ EGASIGA QAYTARILDI" ga o'zgaradi, "Bu meniki" tugmasi olib tashlanadi."""
    await _edit_post(bot, item, channel_post_text(item, returned=True), None)


async def refresh_post(bot: Bot, item: dict) -> None:
    """E'lon tahrirlangandan keyin kanaldagi post matni yangilanadi ("Bu meniki" tugmasi qoladi)."""
    me = await bot.me()
    await _edit_post(bot, item, channel_post_text(item), channel_post_kb(me.username, item["id"]))


async def complete_claim(bot: Bot, claim: dict, item: dict, charge_id: str = "") -> None:
    """To'lov tasdiqlangach: ikki tomonga kontakt, kanal posti yangilanadi, adminga suyunchi eslatmasi.

    charge_id — onlayn to'lov bo'lsa, to'lov tizimidagi ID si.
    """
    code = item_code(item["id"])
    await db.mark_claim_completed(claim["id"])
    await db.close_item(item["id"], "returned")
    await db.close_owner_lost_reports(claim["owner_id"], item["category"])
    share = SERVICE_FEE * FINDER_SHARE // 100

    # Egasiga topuvchining kontakti
    owner_lang = await user_lang(claim["owner_id"])
    await safe_send(
        bot,
        claim["owner_id"],
        t(
            "deal.owner",
            owner_lang,
            code=code,
            category=category_label(item["category"], owner_lang),
            finder=user_link(item["finder_id"], item["finder_name"], item["finder_username"]),
            phone=escape(item["finder_phone"] or ""),
        ),
        reply_markup=handover_kb(claim["id"], "o", owner_lang),
    )

    # Topuvchiga egasining kontakti
    finder_lang = await user_lang(item["finder_id"])
    finder_text = t(
        "deal.finder",
        finder_lang,
        code=code,
        owner=user_link(claim["owner_id"], claim["owner_name"], claim["owner_username"]),
        phone=escape(claim["owner_phone"] or ""),
        amount=money(share),
    )
    if item["finder_card"]:
        finder_text += t("deal.finder_card", finder_lang, card=escape(item["finder_card"]))
    else:
        finder_text += t("deal.finder_no_card", finder_lang)
        finder_text += f": {ADMIN_USERNAME}." if ADMIN_USERNAME else "."
    finder_text += t("deal.finder_footer", finder_lang)
    await safe_send(bot, item["finder_id"], finder_text, reply_markup=handover_kb(claim["id"], "f", finder_lang))

    await mark_post_returned(bot, item)

    admin_text = ""
    if charge_id:
        admin_text = (
            f"💳 <b>Onlayn to'lov qabul qilindi</b> | murojaat №{claim['id']}\n"
            f"To'lov ID: <code>{escape(charge_id)}</code>\n\n"
        )
    admin_text += (
        f"🤝 <b>Ikki tomon bog'landi</b> | #{code}, murojaat №{claim['id']}\n\n"
        "Egasi narsani olganini tasdiqlagach, suyunchi o'tkazish so'raladi."
    )
    await safe_send(bot, ADMIN_GROUP_ID, admin_text)


async def request_payout(bot: Bot, claim: dict, item: dict, note: str) -> None:
    """Narsa topshirilgani tasdiqlandi — admin guruhga suyunchi o'tkazish so'rovi."""
    await safe_send(
        bot,
        ADMIN_GROUP_ID,
        f"{note}\n\n"
        f"💸 <b>Suyunchi o'tkazish kerak</b> | #{item_code(item['id'])}\n\n"
        f"Summa: <b>{money(SERVICE_FEE * FINDER_SHARE // 100)} so'm</b>\n"
        f"Kimga: {user_link(item['finder_id'], item['finder_name'], item['finder_username'])}\n"
        f"Karta: <code>{escape(item['finder_card'] or 'kiritilmagan')}</code>",
        reply_markup=payout_kb(claim["id"]),
    )


ANSWERS = {
    "o": {"yes": "✅ oldim", "no": "⚠️ topuvchi bilan bog'lana olmayapti", None: "javob bermagan"},
    "f": {"yes": "✅ topshirdim", "no": "⚠️ egasi kelmadi / bog'lanmadi", None: "javob bermagan"},
}


async def report_dispute(bot: Bot, claim_id: int, reason: str) -> None:
    """Narsa topshirilmagan bo'lishi mumkin — admin guruhga ikki tomon kontaktlari va qaror tugmalari bilan."""
    claim = await db.get_claim(claim_id)
    item = await db.get_item(claim["item_id"])
    chat_messages = await db.count_chat_messages(claim_id)
    chat_note = f"💬 Bot orqali yozishma: {chat_messages} ta xabar\n\n" if chat_messages else ""
    await safe_send(
        bot,
        ADMIN_GROUP_ID,
        f"⚠️ <b>NIZO</b> | #{item_code(item['id'])}, murojaat №{claim['id']}\n"
        f"{reason}\n\n"
        f"👤 Egasi: {user_link(claim['owner_id'], claim['owner_name'], claim['owner_username'])} "
        f"📞 {escape(claim['owner_phone'] or '—')}\n"
        f"   └ {ANSWERS['o'][claim['owner_answer']]}\n"
        f"👤 Topuvchi: {user_link(item['finder_id'], item['finder_name'], item['finder_username'])} "
        f"📞 {escape(item['finder_phone'] or '—')}\n"
        f"   └ {ANSWERS['f'][claim['finder_answer']]}\n\n"
        f"{chat_note}Ikki tomon bilan bog'lanib, hal qiling 👇",
        reply_markup=dispute_kb(claim["id"], chat_messages),
    )
