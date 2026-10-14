from aiogram import Router

from . import admin, claim, found, start


def get_routers() -> list[Router]:
    # start birinchi turadi: "Bekor qilish" har qanday holatda ishlashi kerak
    return [start.router, admin.router, found.router, claim.router]
