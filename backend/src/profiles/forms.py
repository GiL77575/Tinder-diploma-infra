"""Форма анкети профілю: валідація спільних полів, фото і тегів."""

from django import forms
from django.conf import settings

from profiles.models import (
    BffLookingFor,
    ChildrenStatus,
    Gender,
    HobbyLevel,
    LanguageLevel,
    LookingFor,
    Orientation,
    SearchMode,
    SmokingHabit,
    Tag,
    calculate_age,
)


class ProfileSetupForm(forms.Form):
    """Анкета профілю: спільні поля + окремі контури знайомств і друзів."""
    display_name = forms.CharField(max_length=100, label="Ім'я")
    birth_date = forms.DateField(
        label='Дата народження',
        widget=forms.DateInput(attrs={'type': 'date'}),
    )
    gender = forms.ChoiceField(choices=Gender.choices, label='Стать')
    orientation = forms.ChoiceField(choices=Orientation.choices, label='Орієнтація')
    city = forms.CharField(max_length=100, label='Місто')
    job = forms.CharField(max_length=100, required=False, label='Робота / навчання')
    height_cm = forms.IntegerField(
        required=False,
        min_value=120,
        max_value=230,
        label='Зріст (см)',
    )
    smoking = forms.ChoiceField(
        choices=[('', 'Не вказувати')] + list(SmokingHabit.choices),
        required=False,
        label='Куріння',
    )
    children = forms.ChoiceField(
        choices=[('', 'Не вказувати')] + list(ChildrenStatus.choices),
        required=False,
        label='Діти',
    )
    active_mode = forms.ChoiceField(
        choices=SearchMode.choices,
        initial=SearchMode.DATING,
        label='Основний режим',
    )
    dating_looking_for = forms.ChoiceField(
        choices=LookingFor.choices,
        label='Кого шукаєш',
    )
    min_age = forms.IntegerField(min_value=18, max_value=99, initial=18)
    max_age = forms.IntegerField(min_value=18, max_value=99, initial=35)
    dating_bio = forms.CharField(
        max_length=500,
        widget=forms.Textarea,
        label='Про себе в режимі знайомств',
    )
    dating_interests = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.none(),
        required=False,
    )
    bff_looking_for = forms.ChoiceField(
        choices=BffLookingFor.choices,
        label='Що шукаєш у пошуку друзів',
    )
    bff_bio = forms.CharField(
        max_length=500,
        widget=forms.Textarea,
        label='Про себе в пошуку друзів',
    )
    bff_interests = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.none(),
        required=False,
    )
    bff_hobbies = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.none(),
        required=False,
    )
    bff_languages = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.none(),
        required=False,
    )
    is_discoverable = forms.BooleanField(required=False, initial=True)

    def __init__(self, data=None, files=None, **kwargs):
        """Підставляє queryset тегів для чекбоксів інтересів, хобі та мов."""
        interest_qs = kwargs.pop('interest_qs', Tag.objects.none())
        hobby_qs = kwargs.pop('hobby_qs', Tag.objects.none())
        language_qs = kwargs.pop('language_qs', Tag.objects.none())
        self._photo_files = files.getlist('photos') if files else []
        super().__init__(data, files, **kwargs)
        self.fields['dating_interests'].queryset = interest_qs
        self.fields['bff_interests'].queryset = interest_qs
        self.fields['bff_hobbies'].queryset = hobby_qs
        self.fields['bff_languages'].queryset = language_qs

    def clean_birth_date(self):
        """Перевіряє, що користувачу 18–99 років."""
        value = self.cleaned_data['birth_date']
        age = calculate_age(value)
        if age < 18:
            raise forms.ValidationError('Реєстрація доступна з 18 років.')
        if age > 99:
            raise forms.ValidationError('Перевірте дату народження.')
        return value

    def clean_display_name(self):
        """Прибирає зайві пробіли в імені."""
        return self.cleaned_data['display_name'].strip()

    def clean_city(self):
        """Прибирає зайві пробіли в місті."""
        return self.cleaned_data['city'].strip()

    def _collect_levels(self, tags, field_name, prefix, allowed):
        """Збирає рівні для обраних хобі або мов; додає помилку, якщо рівень не вказано."""
        levels = {}
        for tag in tags or []:
            level = (self.data.get(f'{prefix}{tag.pk}') or '').strip()
            if level not in allowed:
                self.add_error(field_name, f'Оберіть рівень для «{tag.name}».')
            else:
                levels[tag.pk] = level
        return levels

    def first_error_step(self):
        """Крок wizard (1–4), де перша помилка; на валідній формі — 1."""
        if not self.errors:
            return 1
        if self.non_field_errors():
            return 1
        steps = (
            (2, {
                'display_name', 'birth_date', 'gender', 'orientation',
                'city', 'job', 'height_cm', 'smoking', 'children',
            }),
            (3, {
                'active_mode', 'dating_looking_for', 'min_age', 'max_age',
                'dating_bio', 'dating_interests',
            }),
            (4, {
                'bff_looking_for', 'bff_bio', 'bff_interests',
                'bff_hobbies', 'bff_languages', 'is_discoverable',
            }),
        )
        names = set(self.errors)
        for step, fields in steps:
            if names & fields:
                return step
        return 1

    def clean(self):
        """Перевіряє фото, віковий діапазон, інтереси та рівні хобі/мов."""
        cleaned = super().clean()
        photos = [item for item in self._photo_files if item]
        keep_ids = self.data.getlist('keep_photos')
        total_photos = len(photos) + len(keep_ids)
        if total_photos == 0:
            self.add_error(None, 'Додайте хоча б одне фото профілю.')
        elif total_photos > settings.MAX_PHOTOS_PER_PROFILE:
            self.add_error(None, 'Можна завантажити не більше 6 фото.')
        cleaned['photos'] = photos
        cleaned['keep_photo_ids'] = keep_ids

        min_age = cleaned.get('min_age')
        max_age = cleaned.get('max_age')
        if min_age and max_age and min_age > max_age:
            self.add_error('max_age', 'Максимальний вік має бути не меншим за мінімальний.')

        if not cleaned.get('dating_interests'):
            self.add_error('dating_interests', 'Оберіть хоча б один інтерес для знайомств.')
        if not cleaned.get('bff_hobbies'):
            self.add_error('bff_hobbies', 'Оберіть хоча б одне хобі для пошуку друзів.')

        cleaned['hobby_levels'] = self._collect_levels(
            cleaned.get('bff_hobbies'),
            'bff_hobbies',
            'hobby_level_',
            HobbyLevel.values,
        )
        cleaned['language_levels'] = self._collect_levels(
            cleaned.get('bff_languages'),
            'bff_languages',
            'language_level_',
            LanguageLevel.values,
        )
        return cleaned
