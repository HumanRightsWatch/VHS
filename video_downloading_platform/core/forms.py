from django import forms

from video_downloading_platform.core.models import Batch, BatchRequest


class BatchRequestForm(forms.ModelForm):
    class Meta:
        model = BatchRequest
        fields = [
            'batch',
            'urls'
        ]
        labels = {
            'batch': 'Collection',
        }

    def set_user(self, connected_user):
        if connected_user:
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
