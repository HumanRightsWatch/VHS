from django import forms
from django.conf import settings
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from video_downloading_platform.core.models import Batch, BatchRequest, BatchTeam, DownloadRequest, UploadRequest
from video_downloading_platform.core.utils import transform_hl_results


class BatchTeamForm(forms.ModelForm):
    class Meta:
        model = BatchTeam
        fields = [
            'contributors'
        ]
        widgets = {
            'contributors': FilteredSelectMultiple(is_stacked=False, verbose_name=_('Contributors')),
        }

    class Media:
        css = {
            'all': ('/static/admin/css/widgets.css',),
        }
        js = ('/admin/jsi18n',)


class DownloadRequestLightForm(forms.ModelForm):
    class Meta:
        model = DownloadRequest
        fields = [
            'tags',
            'content_warning',
        ]


class BatchRequestForm(forms.ModelForm):
    class Meta:
        model = BatchRequest
        fields = [
            # 'batch',
            'urls',
            'content_warning',
            'type',
        ]
        labels = {
            'batch': 'Collection',
        }
        widgets = {
            'content_warning': forms.Textarea(attrs={'rows': 2, 'cols': 20}),
        }

    def __init__(self, *args, **kwargs):
        super(BatchRequestForm, self).__init__(*args, **kwargs)

    def set_batch(self, batch):
        self.instance.batch = batch

    def set_user(self, connected_user):
        if connected_user:
            self.instance.owner = connected_user
            # self.fields['batch'].queryset = Batch.get_users_open_batches(connected_user)

    def clean_urls(self):
        cleaned_urls = []
        urls = self.cleaned_data.get('urls').splitlines()
        for url in urls:
            striped_url = url.strip()
            if len(striped_url) > 0:
                cleaned_urls.append(striped_url)
        cleaned_urls = list(set(cleaned_urls))
        return '\n'.join(cleaned_urls)


class BatchForm(forms.ModelForm):
    class Meta:
        model = Batch
        fields = [
            'name',
            'description',
            'tags'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2, 'cols': 20}),
        }


def validate_batch(batch_id):
    if not Batch.objects.filter(id=batch_id).exists():
        raise ValidationError("Selected collection does not exists")


class UploadForm(forms.Form):
    upload_request = forms.CharField(
        max_length=64,
        required=True,
        widget=forms.HiddenInput()
    )
    description = forms.CharField(
        label=_('Description'),
        max_length=2000,
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'cols': 20}))
    content_warning = forms.CharField(
        label=_('Content warning'),
        max_length=200,
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'cols': 20}))

    def clean_upload_request(self):
        request_id = self.cleaned_data["upload_request"]
        if not UploadRequest.objects.filter(id=request_id).exists():
            raise ValidationError("Selected upload request does not exists")
        return UploadRequest.objects.get(id=request_id)


class SearchForm(forms.Form):
    q = forms.CharField(
        max_length=128,
        label=_('Search among downloaded contents')
    )

    def do_search(self, indexes=['c.*']):
        q = self.cleaned_data['q']

        query = {
            "query": {
                "query_string": {
                    "default_field": "sha256",
                    "query": q
                }
            },
            "highlight": {
                "fields": {
                    "*": {"pre_tags": ["<mark>"], "post_tags": ["</mark>"]}
                }
            },
            "_source": [
                "collection_id", "collection_name", "created_at", "mimetype", "origin", "owner", "platform",
                "post.description", "post.title", "post.upload_date", "post.uploader", "sha256", "stats.comment_count",
                "stats.like_count", "stats.view_count", "status", "tags", "thumbnail_content_id", "type", "is_hidden",
                "request_id"
            ],
            "sort": {"created_at": "desc"},
            "size": 250,
        }

        from elasticsearch import Elasticsearch
        es = Elasticsearch(settings.ELASTICSEARCH_HOSTS)
        try:
            raw_results = es.search(index=indexes, body=query)
            results = transform_hl_results(raw_results)
            return results
        except Exception:
            return []
