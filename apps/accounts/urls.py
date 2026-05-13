from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.TwoFactorLoginView.as_view(), name="login"),
    path("login/2fa/", views.two_factor_verify, name="two_factor_verify"),
    path("security/", views.two_factor_settings, name="two_factor_settings"),
    path("security/enable/", views.two_factor_enable, name="two_factor_enable"),
    path("security/disable/", views.two_factor_disable, name="two_factor_disable"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("signup/", views.signup, name="signup"),
    # Password change (logged in)
    path(
        "password/change/",
        auth_views.PasswordChangeView.as_view(
            success_url=reverse_lazy("accounts:password_change_done")
        ),
        name="password_change",
    ),
    path(
        "password/change/done/",
        auth_views.PasswordChangeDoneView.as_view(),
        name="password_change_done",
    ),
    # Password reset (logged out)
    path(
        "password/reset/",
        auth_views.PasswordResetView.as_view(
            email_template_name="registration/password_reset_email.html",
            success_url=reverse_lazy("accounts:password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "password/reset/done/",
        auth_views.PasswordResetDoneView.as_view(),
        name="password_reset_done",
    ),
    path(
        "password/reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            success_url=reverse_lazy("accounts:password_reset_complete")
        ),
        name="password_reset_confirm",
    ),
    path(
        "password/reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(),
        name="password_reset_complete",
    ),
]
