import notifications.urls
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.urls import include, path
from django.views import defaults as default_views
from django.views.generic import TemplateView
from django.views.i18n import JavaScriptCatalog
from notifications.views import UnreadNotificationsList
from rest_framework.authtoken.views import obtain_auth_token

from video_downloading_platform.core.views import (
    home_view,
    close_batch_view,
    batch_details_view,
    get_downloaded_content_view,
    my_batches_view,
    get_downloaded_file_view, archive_batch_view, get_report_archive_view, get_batch_status_view,
    reopen_batch_view, BatchTeamUpdateView, download_collection_zip_view,
    hide_download_request_view, show_download_request_view, mark_all_notification_read_view,
)

urlpatterns = [
                  path("", home_view, name="home"),
                  path(
                      "about/", login_required(TemplateView.as_view(template_name="pages/about.html")), name="about"
                  ),
                  # Notifications
                  path('inbox/notifications/', include(notifications.urls, namespace='notifications')),

                  # Django Admin, use {% url 'admin:index' %}
                  path(settings.ADMIN_URL, admin.site.urls),
                  # User management
                  path("users/", include("video_downloading_platform.users.urls", namespace="users")),
                  path("accounts/", include("allauth.urls")),

                  # path("notifications", get_unread_notifications_view, name="get_unread_notifications"),

                  path(r'jsi18n/', JavaScriptCatalog.as_view(), name='jsi18n'),
                  path("inbox/list", UnreadNotificationsList.as_view(), name="get_notification_list"),
                  path("inbox/read_all", mark_all_notification_read_view, name="mark_all_notification_read"),
                  path("batch/list", my_batches_view, name="batch_list"),
                  path("batch/statuses", get_batch_status_view, name="get_batch_status"),
                  path("batch/<str:batch_id>/close", close_batch_view, name="close_batch"),
                  path("batch/<str:batch_id>/reopen", reopen_batch_view, name="reopen_batch"),
                  path("batch/<str:batch_id>/archive", archive_batch_view, name="archive_batch"),
                  path("batch/<str:batch_id>/download", download_collection_zip_view, name="download_batch_archive"),
                  path("batch/<str:batch_id>/details", batch_details_view, name="batch_details"),
                  path("batch_team/<int:pk>", BatchTeamUpdateView.as_view(), name="edit_batch_team"),
                  path("request/<str:request_id>/hide", hide_download_request_view, name="hide_download_request"),
                  path("request/<str:request_id>/show", show_download_request_view, name="show_download_request"),
                  path("content/<str:content_id>", get_downloaded_file_view, name="get_downloaded_file"),
                  path("content/<str:content_id>/download", get_downloaded_content_view, name="get_downloaded_content"),
                  path("report/<str:report_id>/download", get_report_archive_view, name="get_report_archive"),
              ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# API URLS
urlpatterns += [
    # API base url
    path("api/", include("config.api_router")),
    # DRF auth token
    path("auth-token/", obtain_auth_token),
]

if settings.DEBUG:
    # This allows the error pages to be debugged during development, just visit
    # these url in browser to see how these error pages look like.
    urlpatterns += [
        path(
            "400/",
            default_views.bad_request,
            kwargs={"exception": Exception("Bad Request!")},
        ),
        path(
            "403/",
            default_views.permission_denied,
            kwargs={"exception": Exception("Permission Denied")},
        ),
        path(
            "404/",
            default_views.page_not_found,
            kwargs={"exception": Exception("Page not Found")},
        ),
        path("500/", default_views.server_error),
    ]
    if "debug_toolbar" in settings.INSTALLED_APPS:
        import debug_toolbar

        urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns
