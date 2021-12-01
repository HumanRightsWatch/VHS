from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views import defaults as default_views
from django.views.generic import TemplateView
from rest_framework.authtoken.views import obtain_auth_token

from video_downloading_platform.core.views import (
    home_view,
    close_batch_view,
    batch_details_view,
    get_downloaded_content_view,
    my_batches_view,
    get_downloaded_file_view, archive_batch_view,
)

urlpatterns = [
                  path("", home_view, name="home"),
                  path(
                      "about/", TemplateView.as_view(template_name="pages/about.html"), name="about"
                  ),
                  # Django Admin, use {% url 'admin:index' %}
                  path(settings.ADMIN_URL, admin.site.urls),
                  # User management
                  path("users/", include("video_downloading_platform.users.urls", namespace="users")),
                  path("accounts/", include("allauth.urls")),

                  path("batch/list", my_batches_view, name="batch_list"),
                  path("batch/<str:batch_id>/close", close_batch_view, name="close_batch"),
                  path("batch/<str:batch_id>/archive", archive_batch_view, name="archive_batch"),
                  path("batch/<str:batch_id>/details", batch_details_view, name="batch_details"),
                  path("content/<str:content_id>", get_downloaded_file_view, name="get_downloaded_file"),
                  path("content/<str:content_id>/download", get_downloaded_content_view, name="get_downloaded_content"),
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
