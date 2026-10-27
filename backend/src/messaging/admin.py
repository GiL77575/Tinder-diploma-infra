"""Адмінка чату: діалоги, повідомлення, push-підписки."""

from django.contrib import admin

from messaging.models import Conversation, Message, MessageReaction, PushSubscription


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    fields = ('sender', 'text', 'image_url', 'created_at', 'read_at')
    readonly_fields = ('created_at',)
    ordering = ('created_at',)


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'match', 'mode', 'participants', 'created_at', 'last_activity')
    list_filter = ('match__mode',)
    search_fields = (
        'match__user_a__email', 'match__user_a__username',
        'match__user_b__email', 'match__user_b__username',
    )
    inlines = [MessageInline]
    autocomplete_fields = ('match',)

    @admin.display(description='Режим')
    def mode(self, obj):
        return obj.mode

    @admin.display(description='Учасники')
    def participants(self, obj):
        return f'{obj.match.user_a} \u2194 {obj.match.user_b}'

    @admin.display(description='Остання активність')
    def last_activity(self, obj):
        last = obj.messages.order_by('-created_at').first()
        return last.created_at if last else obj.created_at


class MessageReactionInline(admin.TabularInline):
    model = MessageReaction
    extra = 0
    autocomplete_fields = ('user',)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'sender', 'short_text', 'has_image', 'created_at', 'read_at')
    list_filter = ('conversation__match__mode',)
    search_fields = ('text', 'sender__email', 'sender__username')
    autocomplete_fields = ('conversation', 'sender')
    inlines = (MessageReactionInline,)

    @admin.display(description='Текст')
    def short_text(self, obj):
        if obj.text:
            return obj.text[:60]
        if obj.image_url:
            return '📷 Фото'
        return '—'

    @admin.display(description='Фото', boolean=True)
    def has_image(self, obj):
        return bool(obj.image_url)


@admin.register(MessageReaction)
class MessageReactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'message', 'user', 'emoji', 'created_at')
    search_fields = ('emoji', 'user__email', 'user__username')
    autocomplete_fields = ('message', 'user')


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'created_at')
    search_fields = ('user__email', 'user__username', 'endpoint')
