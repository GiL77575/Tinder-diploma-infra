"""Збереження профілю, фото та тегів у базу."""

import uuid
from pathlib import Path
from types import SimpleNamespace

from django.conf import settings

from profiles.models import (
    Photo,
    PhotoStatus,
    Profile,
    ProfileMode,
    ProfileTag,
    SearchMode,
    TagCategory,
)

ALLOWED_PHOTO_TYPES = {'image/jpeg', 'image/png', 'image/webp'}
MAX_PHOTO_BYTES = 5 * 1024 * 1024
DRAFT_PHOTOS_SESSION_KEY = 'profile_draft_photos'


def save_profile_photo(user_id, uploaded_file, order):
    """Завантажує фото в Cloudinary або локально; повертає (public_id, url)."""
    content_type = getattr(uploaded_file, 'content_type', '') or ''
    if content_type not in ALLOWED_PHOTO_TYPES:
        raise ValueError('Фото має бути JPEG, PNG або WebP.')
    if uploaded_file.size > MAX_PHOTO_BYTES:
        raise ValueError('Кожне фото має бути не більше 5 МБ.')

    if settings.CLOUDINARY_URL:
        import cloudinary.uploader

        result = cloudinary.uploader.upload(
            uploaded_file,
            folder=f'crushme/profiles/{user_id}',
            resource_type='image',
        )
        return result['public_id'], result['secure_url']

    ext = Path(uploaded_file.name or '').suffix.lower()
    if ext not in {'.jpg', '.jpeg', '.png', '.webp'}:
        ext = '.jpg'
    filename = f'{order}_{uuid.uuid4().hex}{ext}'
    rel_dir = Path('profiles') / str(user_id)
    dest_dir = Path(settings.MEDIA_ROOT) / rel_dir
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    uploaded_file.seek(0)
    with dest.open('wb+') as out:
        for chunk in uploaded_file.chunks():
            out.write(chunk)
    public_id = f'local:{rel_dir.as_posix()}/{filename}'
    url = f'{settings.MEDIA_URL}{rel_dir.as_posix()}/{filename}'
    return public_id, url


def get_draft_photos(session):
    """Чернетка фото анкети зі сесії (щоб пережити помилку валідації)."""
    return list(session.get(DRAFT_PHOTOS_SESSION_KEY) or [])


def clear_draft_photos(session):
    """Прибирає чернетку фото після успішного збереження профілю."""
    session.pop(DRAFT_PHOTOS_SESSION_KEY, None)
    session.modified = True


def sync_draft_photos(request, user):
    """Лишає keep_photos і додає нові файли в сесію; браузер не вміє повернути input[type=file]."""
    keep_ids = set(request.POST.getlist('keep_photos'))
    drafts = [
        item for item in get_draft_photos(request.session)
        if item['public_id'] in keep_ids
    ]
    for uploaded in request.FILES.getlist('photos'):
        if not uploaded:
            continue
        if len(drafts) >= settings.MAX_PHOTOS_PER_PROFILE:
            break
        public_id, url = save_profile_photo(user.pk, uploaded, len(drafts))
        drafts.append({'public_id': public_id, 'url': url})
    request.session[DRAFT_PHOTOS_SESSION_KEY] = drafts
    request.session.modified = True
    return drafts


def _renumber_photos(profile):
    """Ставить порядок 0..n і перше фото як головне."""
    for index, photo in enumerate(
        Photo.objects.filter(profile=profile).order_by('order', 'id')
    ):
        photo.order = index
        photo.is_primary = index == 0
        photo.save(update_fields=['order', 'is_primary'])


def _create_photo(profile, public_id, url, order):
    """Створює запис Photo у галереї профілю."""
    Photo.objects.create(
        profile=profile,
        cloudinary_public_id=public_id,
        url=url,
        order=order,
        is_primary=False,
        status=PhotoStatus.APPROVED,
    )


def _sync_photos(profile, user, data, draft_photos=None):
    """Оновлює галерею: keep_photos з БД або чернетки, плюс нові файли."""
    keep_ids = list(data.get('keep_photo_ids') or [])
    numeric_keep = [int(photo_id) for photo_id in keep_ids if str(photo_id).isdigit()]

    if numeric_keep:
        profile.photos.exclude(pk__in=numeric_keep).delete()
    else:
        profile.photos.all().delete()

    next_order = Photo.objects.filter(profile=profile).count()
    if draft_photos:
        keep_set = set(keep_ids) if keep_ids else {
            item['public_id'] for item in draft_photos
        }
        for draft in draft_photos:
            if draft['public_id'] not in keep_set:
                continue
            _create_photo(profile, draft['public_id'], draft['url'], next_order)
            next_order += 1
    else:
        for uploaded in data.get('photos') or []:
            public_id, url = save_profile_photo(user.pk, uploaded, next_order)
            _create_photo(profile, public_id, url, next_order)
            next_order += 1

    _renumber_photos(profile)


def _add_tags(profile, tags, mode, levels=None):
    """Прив'язує набір тегів до профілю в конкретному режимі."""
    levels = levels or {}
    for tag in tags or []:
        ProfileTag.objects.create(
            profile=profile,
            tag=tag,
            mode=mode,
            level=levels.get(tag.pk, ''),
        )


def _resolve_active_mode(data):
    """Основний режим не може вказувати на пропущений (порожній) контур."""
    active_mode = data['active_mode']
    if data.get('skip_bff') and active_mode == SearchMode.BFF:
        return SearchMode.DATING
    if data.get('skip_dating') and active_mode == SearchMode.DATING:
        return SearchMode.BFF
    return active_mode


def save_profile(user, data, draft_photos=None):
    """Створює або оновлює профіль, обидва контури (Dating/BFF) і теги."""
    profile, _ = Profile.objects.update_or_create(
        user=user,
        defaults={
            'display_name': data['display_name'],
            'birth_date': data['birth_date'],
            'gender': data['gender'],
            'orientation': data['orientation'],
            'job': data.get('job') or '',
            'city': data['city'],
            'height_cm': data.get('height_cm'),
            'smoking': data.get('smoking') or '',
            'children': data.get('children') or '',
            'alcohol': data.get('alcohol') or '',
            'sport': data.get('sport') or '',
            'pets': data.get('pets') or '',
            'zodiac_sign': data.get('zodiac_sign') or '',
            'active_mode': _resolve_active_mode(data),
            'is_discoverable': data.get('is_discoverable', True),
        },
    )
    _sync_photos(profile, user, data, draft_photos=draft_photos)

    if data.get('skip_dating'):
        ProfileMode.objects.filter(profile=profile, mode=SearchMode.DATING).delete()
    else:
        ProfileMode.objects.update_or_create(
            profile=profile,
            mode=SearchMode.DATING,
            defaults={
                'bio': data['dating_bio'],
                'looking_for': data['dating_looking_for'],
                'min_age': data['min_age'],
                'max_age': data['max_age'],
                'age_preference': data.get('dating_age_preference') or '',
                'relationship_goal': data.get('dating_relationship_goal') or '',
                'smoking_attitude': data.get('dating_smoking_attitude') or '',
                'alcohol_attitude': data.get('dating_alcohol_attitude') or '',
                'meeting_format': data.get('dating_meeting_format') or '',
            },
        )

    profile.profile_tags.filter(mode=SearchMode.BFF).delete()
    if data.get('skip_bff'):
        ProfileMode.objects.filter(profile=profile, mode=SearchMode.BFF).delete()
    else:
        ProfileMode.objects.update_or_create(
            profile=profile,
            mode=SearchMode.BFF,
            defaults={
                'bio': data['bff_bio'],
                # «Що шукаєш» — множинний вибір, зберігаємо через кому.
                'looking_for': ','.join(data.get('bff_looking_for') or []),
                'min_age': 18,
                'max_age': 99,
            },
        )

    profile.profile_tags.all().delete()
    if not data.get('skip_dating'):
        _add_tags(profile, data.get('dating_interests'), SearchMode.DATING)
    if not data.get('skip_bff'):
        _add_tags(profile, data.get('bff_interests'), SearchMode.BFF)
        _add_tags(
            profile,
            data.get('bff_hobbies'),
            SearchMode.BFF,
            levels=data.get('hobby_levels') or {},
        )
        _add_tags(
            profile,
            data.get('bff_languages'),
            SearchMode.BFF,
            levels=data.get('language_levels') or {},
        )

    user.is_profile_complete = True
    user.save(update_fields=['is_profile_complete'])
    return profile


def form_initial_from_profile(profile):
    """Словник initial для форми редагування зі збереженого профілю."""
    dating = profile.get_mode(SearchMode.DATING)
    bff = profile.get_mode(SearchMode.BFF)
    return {
        'display_name': profile.display_name,
        'birth_date': profile.birth_date,
        'gender': profile.gender,
        'orientation': profile.orientation,
        'city': profile.city,
        'job': profile.job,
        'height_cm': profile.height_cm,
        'smoking': profile.smoking,
        'children': profile.children,
        'alcohol': profile.alcohol,
        'sport': profile.sport,
        'pets': profile.pets,
        'zodiac_sign': profile.zodiac_sign,
        'active_mode': profile.active_mode,
        'is_discoverable': profile.is_discoverable,
        'dating_looking_for': dating.looking_for if dating else '',
        'min_age': dating.min_age if dating else 18,
        'max_age': dating.max_age if dating else 35,
        'dating_age_preference': dating.age_preference if dating else '',
        'dating_relationship_goal': dating.relationship_goal if dating else '',
        'dating_smoking_attitude': dating.smoking_attitude if dating else '',
        'dating_alcohol_attitude': dating.alcohol_attitude if dating else '',
        'dating_meeting_format': dating.meeting_format if dating else '',
        'dating_bio': dating.bio if dating else '',
        'dating_interests': [
            item.tag_id
            for item in profile.tags_for(SearchMode.DATING, TagCategory.INTEREST)
        ],
        'bff_looking_for': bff.looking_for.split(',') if bff and bff.looking_for else [],
        'bff_bio': bff.bio if bff else '',
        'bff_interests': [
            item.tag_id
            for item in profile.tags_for(SearchMode.BFF, TagCategory.INTEREST)
        ],
        'bff_hobbies': [
            item.tag_id
            for item in profile.tags_for(SearchMode.BFF, TagCategory.HOBBY)
        ],
        'bff_languages': [
            item.tag_id
            for item in profile.tags_for(SearchMode.BFF, TagCategory.LANGUAGE)
        ],
    }


def _photo_slots(photos):
    """6 слотів галереї з існуючих фото або порожніх місць."""
    return [
        {'index': index, 'photo': photos[index] if index < len(photos) else None}
        for index in range(settings.MAX_PHOTOS_PER_PROFILE)
    ]


def photo_slots_for_form(request, profile=None):
    """Слоти фото: профіль / keep_photos на редагуванні, чернетка сесії на анкеті."""
    if profile is not None:
        if request.method == 'POST':
            keep_ids = request.POST.getlist('keep_photos')
            by_id = {
                str(photo.pk): photo
                for photo in profile.photos.filter(pk__in=keep_ids)
            }
            photos = [by_id[photo_id] for photo_id in keep_ids if photo_id in by_id]
        else:
            photos = list(profile.photos.all()[:settings.MAX_PHOTOS_PER_PROFILE])
        return _photo_slots(photos)

    drafts = get_draft_photos(request.session)
    photos = [
        SimpleNamespace(url=item['url'], id=item['public_id'])
        for item in drafts[:settings.MAX_PHOTOS_PER_PROFILE]
    ]
    return _photo_slots(photos)
