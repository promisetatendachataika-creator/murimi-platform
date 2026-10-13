from django.urls import path

from . import api

urlpatterns = [
    path("health/", api.health),
    path("auth/register/", api.register),
    path("auth/login/", api.login_view),
    path("auth/logout/", api.logout_view),
    path("me/", api.me),
    path("me/steps/", api.set_step),
    path("me/saved/", api.set_saved),
    path("me/phone/send-code/", api.phone_send_code),
    path("me/phone/confirm/", api.phone_confirm),
    path("auth/password/forgot/", api.password_forgot),
    path("auth/password/reset/", api.password_reset),
]
