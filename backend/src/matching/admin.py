"""Адмінка матчінгу: лайки, матчі, блоки, скарги."""

from django.contrib import admin

from matching.models import Block, Like, Match, Report


@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    list_display = ('id', 'from_user', 'to_user', 'mode', 'is_positive', 'created_at')
    list_filter = ('mode', 'is_positive')
    search_fields = ('from_user__email', 'from_user__username', 'to_user__email', 'to_user__username')
    autocomplete_fields = ('from_user', 'to_user')


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_a', 'user_b', 'mode', 'created_at', 'has_conversation')
    list_filter = ('mode',)
    search_fields = ('user_a__email', 'user_a__username', 'user_b__email', 'user_b__username')
    autocomplete_fields = ('user_a', 'user_b')

    @admin.display(description='Є чат', boolean=True)
    def has_conversation(self, obj):
        return hasattr(obj, 'conversation')


@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = ('id', 'blocker', 'blocked', 'created_at')
    search_fields = ('blocker__email', 'blocker__username', 'blocked__email', 'blocked__username')
    autocomplete_fields = ('blocker', 'blocked')


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'reporter', 'reported', 'reason', 'status', 'created_at')
    list_filter = ('reason', 'status')
    search_fields = ('reporter__email', 'reported__email', 'details')
    autocomplete_fields = ('reporter', 'reported')
