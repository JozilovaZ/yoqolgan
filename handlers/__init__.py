from aiogram import Router

from . import admin, claim, found, handover, lost, panel, payments, start, terms


def get_routers() -> list[Router]:
    # start birinchi turadi: "Bekor qilish" har qanday holatda ishlashi kerak
    return [start.router, terms.router, admin.router, panel.router, found.router, lost.router, handover.router, payments.router, claim.router]
