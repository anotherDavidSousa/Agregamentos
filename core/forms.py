from django import forms


class UploadArquivoForm(forms.Form):
    arquivo = forms.FileField(
        label="Selecione o arquivo",
        help_text="Formatos aceitos: .xls, .xlsx, .csv",
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.xls,.xlsx,.csv'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        return cleaned_data

