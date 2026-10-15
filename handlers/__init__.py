from aiogram import Router

from . import admin, chat, claim, found, handover, lookup, lost, mine, panel, payments, start, terms


def get_routers() -> list[Router]:
    # start birinchi turadi: "Bekor qilish" har qanday holatda ishlashi kerak.
    # lookup oxirida (claim faqat rasmni ushlaydi): tanilmagan matnga javob beradi
    return [start.router, terms.router, admin.router, panel.router, found.router, lost.router, mine.router, chat.router, handover.router, payments.router, lookup.router, claim.router]
