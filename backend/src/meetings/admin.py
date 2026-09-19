from django.contrib import admin

from meetings.models import Meeting, MeetingParticipant


class MeetingParticipantInline(admin.TabularInline):
    model = MeetingParticipant
    extra = 0


@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'creator', 'starts_at', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('title', 'location', 'creator__email')
    inlines = [MeetingParticipantInline]


@admin.register(MeetingParticipant)
class MeetingParticipantAdmin(admin.ModelAdmin):
    list_display = ('id', 'meeting', 'user', 'joined_at')
    search_fields = ('user__email', 'meeting__title')
