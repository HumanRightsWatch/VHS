from django.contrib import admin

from video_downloading_platform.core.models import (
    Batch,
    DownloadRequest,
    DownloadReport,
    DownloadedContent
)


class BatchAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')


admin.site.register(Batch, BatchAdmin)


class DownloadRequestAdmin(admin.ModelAdmin):
    pass


admin.site.register(DownloadRequest, DownloadRequestAdmin)


class DownloadReportAdmin(admin.ModelAdmin):
    pass


admin.site.register(DownloadReport, DownloadReportAdmin)


class DownloadedContentAdmin(admin.ModelAdmin):
    list_display = ('name', 'mime_type')


admin.site.register(DownloadedContent, DownloadedContentAdmin)
