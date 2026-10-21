"""«Mening e'lonlarim»: topuvchining e'lonlari va egasining murojaatlari — holati, tahrirlash, yopish."""
import logging
from html import escape

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, LinkPreviewOptions, Message

import database as db
import instagram
from config import ADMIN_GROUP_ID, ADMIN_USERNAME, CHANNEL_ID, FINDER_SHARE, PAYMENT_PROVIDER_TOKEN, SERVICE_FEE
from i18n import t
from keyboards import BUTTONS, cancel_kb, main_menu, my_claim_kb, my_item_kb, my_list_kb
from services import mark_post_returned, post_link, refresh_post, request_payment
from utils import category_label, cut, is_document, item_code, local_time, location_text, money_text, safe_send, user_link

logger = logging.getLogger(__name__)

router = Router()
router.message.filter(F.chat.type == ChatType.PRIVATE)

NO_PREVIEW = LinkPreviewOptions(is_disabled=True)
EDITABLE = ("pending", "published")


class EditForm(StatesGroup):
    description = State()


def _claim_status(claim: dict, lang: str) -> str:
    if claim["status"] == "completed":
        return t(f"handover_status.{claim['handover'] or 'none'}", lang)
    return t(f"claim_status.{claim['status']}", lang)


# ---------- ro'yxat ----------

async def _list_view(user_id: int, lang: str) -> tuple[str, object] | None:
    items = await db.list_user_items(user_id)
    claims = await db.list_user_claims(user_id)
    if not items and not claims:
        return None
    lines = [t("mine.title", lang)]
    if items:
        lines += ["", t("mine.found", lang)]
        lines += [
            f"#{item_code(item['id'])} · {category_label(item['category'], lang)} · "
            f"{t('item_status.' + item['status'], lang)}"
            for item in items
        ]
    if claims:
        lines += ["", t("mine.claims", lang)]
        for claim in claims:
            item = await db.get_item(claim["item_id"])
            status = _claim_status(claim, lang)
            status = status[:1].upper() + status[1:]
            lines.append(f"#{item_code(claim['item_id'])} · {category_label(item['category'], lang)} · {status}")
    lines += ["", t("mine.hint", lang)]
    return "\n".join(lines), my_list_kb(items, claims)


@router.message(StateFilter(None), F.text.in_(BUTTONS["my_items"]))
async def my_items(message: Message, lang: str):
    view = await _list_view(message.from_user.id, lang)
    if not view:
        await message.answer(t("mine.empty", lang, found=t("btn.found", lang), lost=t("btn.lost", lang)))
        return
    text, keyboard = view
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data == "my:list")
async def back_to_list(callback: CallbackQuery, lang: str):
    await callback.answer()
    view = await _list_view(callback.from_user.id, lang)
    if view:
        text, keyboard = view
        await callback.message.edit_text(text, reply_markup=keyboard)


# ---------- topuvchining e'loni ----------

def _payout_text(deal: dict, lang: str) -> str:
    amount = f"<b>{money_text(SERVICE_FEE * FINDER_SHARE // 100, lang)}</b>"
    if deal["handover"] is None:
        return t("mine.payout_waiting", lang, amount=amount)
    if deal["handover"] == "disputed":
        return t("mine.payout_disputed", lang)
    if deal["handover"] == "refunded":
        return t("mine.payout_refunded", lang)
    if deal["payout_at"]:
        return t("mine.payout_done", lang, amount=amount, date=local_time(deal["payout_at"]))
    return t("mine.payout_soon", lang, amount=amount)


async def _item_card(item: dict, lang: str) -> str:
    lines = [
        f"📦 <b>{category_label(item['category'], lang)}</b> | #{item_code(item['id'])}",
        location_text(item, 200, lang),
        f"📅 {escape(item['found_date'] or '')}",
        f"📝 {escape(cut(item['description'], 400)) or '—'}",
        "",
        t("mine.status", lang, status=t(f"item_status.{item['status']}", lang)),
    ]
    if item["status"] == "published":
        link = post_link(item["channel_msg_id"])
        if link:
            lines.append(f"👉 {link}")
        open_claims = await db.count_open_claims(item["id"])
        if open_claims:
            lines.append(t("mine.open_claims", lang, count=open_claims))
    deal = await db.get_item_deal(item["id"])
    if deal:
        lines.append(_payout_text(deal, lang))
    return "\n".join(lines)


async def _own_item(callback: CallbackQuery, lang: str) -> dict | None:
    item = await db.get_item(int(callback.data.split(":")[2]))
    if not item or item["finder_id"] != callback.from_user.id:
        await callback.answer(t("mine.not_found", lang), show_alert=True)
        return None
    return item


async def _show_item(callback: CallbackQuery, item: dict, lang: str, confirm: str = "") -> None:
    deal = await db.get_item_deal(item["id"])
    await callback.message.edit_text(
        await _item_card(item, lang), reply_markup=my_item_kb(item, deal, confirm, lang), link_preview_options=NO_PREVIEW
    )


@router.callback_query(F.data.startswith("my:i:"))
async def show_item(callback: CallbackQuery, lang: str):
    item = await _own_item(callback, lang)
    if item:
        await callback.answer()
        await _show_item(callback, item, lang)


async def _closable(callback: CallbackQuery, item: dict, statuses: tuple, lang: str) -> bool:
    """E'lonni egasi o'zi yopa oladimi: holati mos va hali ko'rib chiqilayotgan murojaat yo'q."""
    if item["status"] not in statuses:
        await callback.answer(t("mine.already_closed", lang), show_alert=True)
        await _show_item(callback, item, lang)
        return False
    if await db.count_open_claims(item["id"]):
        text = t("mine.has_claims", lang)
        if ADMIN_USERNAME:
            text += " " + t("common.questions", lang, admin=ADMIN_USERNAME)
        await callback.answer(text, show_alert=True)
        return False
    return True


@router.callback_query(F.data.startswith("my:ret:") | F.data.startswith("my:del:"))
async def ask_close(callback: CallbackQuery, lang: str):
    item = await _own_item(callback, lang)
    if not item:
        return
    action = callback.data.split(":")[1]
    if not await _closable(callback, item, ("published",) if action == "ret" else EDITABLE, lang):
        return
    await callback.answer(t("mine.confirm", lang))
    await _show_item(callback, item, lang, confirm=action)


@router.callback_query(F.data.startswith("my:ret2:"))
async def mark_returned(callback: CallbackQuery, bot: Bot, lang: str):
    """Narsa bot tashqarisida egasiga qaytarilgan — e'lon yopiladi, kanaldagi post yangilanadi."""
    item = await _own_item(callback, lang)
    if not item or not await _closable(callback, item, ("published",), lang):
        return
    await db.close_item(item["id"], "returned")
    await mark_post_returned(bot, item)
    await callback.answer(t("mine.closed_toast", lang))
    await _show_item(callback, await db.get_item(item["id"]), lang)
    await callback.message.answer(t("mine.thanks_returned", lang), reply_markup=main_menu(lang))
    await safe_send(
        bot,
        ADMIN_GROUP_ID,
        f"🤝 #{item_code(item['id'])}: topuvchi narsani egasiga o'zi qaytarganini belgiladi — e'lon yopildi.\n"
        f"👤 {user_link(item['finder_id'], item['finder_name'], item['finder_username'])}",
    )


@router.callback_query(F.data.startswith("my:del2:"))
async def remove_item(callback: CallbackQuery, bot: Bot, lang: str):
    item = await _own_item(callback, lang)
    if not item or not await _closable(callback, item, EDITABLE, lang):
        return
    note = ""
    if item["status"] == "published":
        try:
            await bot.delete_message(CHANNEL_ID, item["channel_msg_id"])
        except TelegramAPIError as error:
            logger.warning("Kanaldan o'chmadi: %s", error)
            note = f"\n⚠️ Kanaldagi post o'chmadi, qo'lda o'chiring: {post_link(item['channel_msg_id'])}"
    await db.close_item(item["id"], "removed")
    await callback.answer(t("mine.removed_toast", lang))
    await _show_item(callback, await db.get_item(item["id"]), lang)
    await safe_send(
        bot,
        ADMIN_GROUP_ID,
        f"🗑 #{item_code(item['id'])}: topuvchi e'lonini o'zi olib tashladi.\n"
        f"👤 {user_link(item['finder_id'], item['finder_name'], item['finder_username'])}{note}"
        + instagram.removal_note(item),
        link_preview_options=NO_PREVIEW,
    )


# ---------- izohni tahrirlash ----------

@router.callback_query(F.data.startswith("my:edit:"))
async def start_edit(callback: CallbackQuery, state: FSMContext, lang: str):
    item = await _own_item(callback, lang)
    if not item:
        return
    if item["status"] not in EDITABLE:
        await callback.answer(t("mine.not_editable", lang), show_alert=True)
        return
    await callback.answer()
    await state.set_state(EditForm.description)
    await state.update_data(item_id=item["id"])
    text = t("mine.q_edit", lang, code=item_code(item["id"]))
    if is_document(item["category"]):
        text += t("mine.edit_doc_warning", lang)
    await callback.message.answer(text, reply_markup=cancel_kb(lang))


@router.message(EditForm.description, F.text)
async def got_new_description(message: Message, state: FSMContext, bot: Bot, lang: str):
    description = message.text.strip()
    if len(description) > 500:
        await message.answer(t("common.description_too_long", lang))
        return
    data = await state.get_data()
    await state.clear()
    item = await db.get_item(data["item_id"])
    if not item or item["finder_id"] != message.from_user.id or item["status"] not in EDITABLE:
        await message.answer(t("mine.inactive", lang), reply_markup=main_menu(lang))
        return

    await db.update_item(item["id"], description=description)
    updated = await db.get_item(item["id"])
    if updated["status"] == "published":
        await refresh_post(bot, updated)
    await message.answer(t("mine.edited", lang, code=item_code(item["id"])), reply_markup=main_menu(lang))
    await safe_send(
        bot,
        ADMIN_GROUP_ID,
        f"✏️ <b>Izoh o'zgartirildi</b> | #{item_code(item['id'])} — {category_label(item['category'])}\n\n"
        f"Eski: <i>{escape(cut(item['description'], 300)) or '—'}</i>\n"
        f"Yangi: <i>{escape(cut(description, 300))}</i>",
    )


@router.message(EditForm.description)
async def description_required(message: Message, lang: str):
    await message.answer(t("mine.text_required", lang))


# ---------- egasining murojaati ----------

def _claim_card(claim: dict, item: dict, lang: str) -> str:
    lines = [
        t("mine.claim_title", lang, id=claim["id"], code=item_code(item["id"]),
          category=category_label(item["category"], lang)),
        f"📅 {local_time(claim['created_at'])}",
        "",
        t("mine.status", lang, status=t(f"claim_status.{claim['status']}", lang)),
    ]
    if claim["status"] == "checking":
        lines.append(t("mine.claim_checking", lang))
    elif claim["status"] == "awaiting_payment":
        lines.append(t("mine.claim_fee", lang, fee=money_text(SERVICE_FEE, lang)))
    elif claim["status"] == "payment_review":
        lines.append(t("mine.claim_receipt", lang))
    elif claim["status"] == "completed":
        lines.append(t("mine.claim_item", lang, status=_claim_status(claim, lang)))
        if claim["handover"] != "refunded" and item["finder_phone"]:
            finder = user_link(item["finder_id"], item["finder_name"], item["finder_username"])
            lines += ["", t("mine.finder", lang, finder=finder), f"📞 <b>{escape(item['finder_phone'])}</b>"]
    return "\n".join(lines)


@router.callback_query(F.data.startswith("my:c:"))
async def show_claim(callback: CallbackQuery, lang: str):
    claim = await db.get_claim(int(callback.data.split(":")[2]))
    if not claim or claim["owner_id"] != callback.from_user.id:
        await callback.answer(t("mine.claim_not_found", lang), show_alert=True)
        return
    await callback.answer()
    item = await db.get_item(claim["item_id"])
    await callback.message.edit_text(
        _claim_card(claim, item, lang), reply_markup=my_claim_kb(claim, bool(PAYMENT_PROVIDER_TOKEN), lang)
    )


@router.callback_query(F.data.startswith("my:pay:"))
async def pay_again(callback: CallbackQuery, bot: Bot, lang: str):
    """To'lov xabari yo'qolib ketgan bo'lsa — qaytadan yuboriladi."""
    claim = await db.get_claim(int(callback.data.split(":")[2]))
    if not claim or claim["owner_id"] != callback.from_user.id or claim["status"] != "awaiting_payment":
        await callback.answer(t("mine.no_payment", lang), show_alert=True)
        return
    item = await db.get_item(claim["item_id"])
    if item["status"] != "published":
        await callback.answer(t("mine.item_inactive", lang), show_alert=True)
        return
    await callback.answer()
    intro = t("pay.again_intro", lang, code=item_code(item["id"]), category=category_label(item["category"], lang))
    await request_payment(bot, claim, item, intro=intro)
