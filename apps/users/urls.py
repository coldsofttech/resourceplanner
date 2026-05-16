from django.urls import path

from . import views, sso_views

urlpatterns = [
    # Dashboard (root)
    path('', views.dashboard_view, name='dashboard'),

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

    # Profile
    path('profile/', views.profile_view, name='profile'),
    path('profile/change-password/', views.force_change_password_view, name='force_change_password'),

    # Admin user management
    path('users/', views.user_list_view, name='user_list'),
    path('users/new/', views.user_create_view, name='user_create'),
    path('users/<int:pk>/', views.user_detail_view, name='user_detail'),

    # User Groups
    path('user-groups/', views.group_list_view, name='group_list'),
    path('user-groups/new/', views.group_create_view, name='group_create'),
    path('user-groups/<int:pk>/', views.group_detail_view, name='group_detail'),
    path('user-groups/<int:pk>/edit/', views.group_edit_view, name='group_edit'),

    # Privacy / Cookie policy
    path('privacy/', views.privacy_view, name='privacy'),

    # SSO — OAuth2
    path('sso/oauth2/login/', sso_views.oauth2_login, name='sso_oauth2_login'),
    path('sso/oauth2/callback/', sso_views.oauth2_callback, name='sso_oauth2_callback'),

    # SSO — SAML 2.0
    path('sso/saml/login/', sso_views.saml_login, name='sso_saml_login'),
    path('sso/saml/acs/', sso_views.saml_acs, name='sso_saml_acs'),
    path('sso/saml/metadata/', sso_views.saml_metadata, name='sso_saml_metadata'),
]
