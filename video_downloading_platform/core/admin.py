from django.contrib import admin

from video_downloading_platform.core.models import (
    Batch,
    DownloadRequest,
    DownloadReport,
    DownloadedContent, UploadRequest, PlatformCredentials
)


class BatchAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')


admin.site.register(Batch, BatchAdmin)


class DownloadRequestAdmin(admin.ModelAdmin):
    pass


admin.site.register(DownloadRequest, DownloadRequestAdmin)


class DownloadReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'archive')


admin.site.register(DownloadReport, DownloadReportAdmin)


class DownloadedContentAdmin(admin.ModelAdmin):
    list_display = ('name', 'mime_type')


admin.site.register(DownloadedContent, DownloadedContentAdmin)


class UploadRequestAdmin(admin.ModelAdmin):
    list_display = ('name', 'path')


admin.site.register(UploadRequest, UploadRequestAdmin)


class PlatformCredentialsAdmin(admin.ModelAdmin):
    list_display = ('name',)


admin.site.register(PlatformCredentials, PlatformCredentialsAdmin)
