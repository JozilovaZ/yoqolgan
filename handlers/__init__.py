from aiogram import Router

from . import admin, claim, found, lost, panel, payments, start


def get_routers() -> list[Router]:
    # start birinchi turadi: "Bekor qilish" har qanday holatda ishlashi kerak
    return [start.router, admin.router, panel.router, found.router, lost.router, payments.router, claim.router]
