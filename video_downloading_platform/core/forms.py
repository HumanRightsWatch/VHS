from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from video_downloading_platform.core.models import Batch, BatchRequest, BatchTeam


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


class BatchRequestForm(forms.ModelForm):
    class Meta:
        model = BatchRequest
        fields = [
            'batch',
            'urls',
            'type'
        ]
        labels = {
            'batch': 'Collection',
        }

    def __init__(self, *args, **kwargs):
        super(BatchRequestForm, self).__init__(*args, **kwargs)
        self.fields['batch'].empty_label = None

    def set_user(self, connected_user):
        if connected_user:
            self.instance.owner = connected_user
            self.fields['batch'].queryset = Batch.get_users_open_batches(connected_user)

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
            'description'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2, 'cols': 20}),
        }


def validate_batch(batch_id):
    if not Batch.objects.filter(id=batch_id).exists():
        raise ValidationError("Selected collection does not exists")


class UploadForm(forms.Form):
    batch = forms.ChoiceField(label=_('Collection'))
    name = forms.CharField(label=_('Filename'), max_length=100)
    description = forms.CharField(
        label=_('Description'),
        max_length=200,
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'cols': 20}))
    file = forms.FileField()

    def clean_batch(self):
        batch_id = self.cleaned_data["batch"]
        if not Batch.objects.filter(id=batch_id).exists():
            raise ValidationError("Selected collection does not exists")
        return Batch.objects.get(id=batch_id)

    def set_user(self, connected_user):
        if connected_user:
            self.fields['batch'].choices = [(c.id, c.name) for c in Batch.get_users_open_batches(connected_user)]
