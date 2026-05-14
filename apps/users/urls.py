from django.urls import path

from . import views, sso_views

urlpatterns = [
    # Classic auth
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),

    # Password reset
    path('password-reset/', views.RpPasswordResetView.as_view(), name='password_reset'),
    path('password-reset/done/', views.RpPasswordResetDoneView.as_view(), name='password_reset_done'),
    path(
        'password-reset/confirm/<uidb64>/<token>/',
        views.RpPasswordResetConfirmView.as_view(),
        name='password_reset_confirm',
    ),
    path(
        'password-reset/complete/',
        views.RpPasswordResetCompleteView.as_view(),
        name='password_reset_complete',
    ),

    # SSO — OAuth2
    path('sso/oauth2/login/', sso_views.oauth2_login, name='sso_oauth2_login'),
    path('sso/oauth2/callback/', sso_views.oauth2_callback, name='sso_oauth2_callback'),

    # SSO — SAML 2.0
    path('sso/saml/login/', sso_views.saml_login, name='sso_saml_login'),
    path('sso/saml/acs/', sso_views.saml_acs, name='sso_saml_acs'),
    path('sso/saml/metadata/', sso_views.saml_metadata, name='sso_saml_metadata'),
]
