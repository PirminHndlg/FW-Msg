from django.contrib import admin
from django.contrib.admin import SimpleListFilter

from .models import ChatDirect, ChatGroup, ChatMessageDirect, ChatMessageGroup


class ReadFilter(SimpleListFilter):
    title = 'Gelesen'
    parameter_name = 'read_filter'

    def lookups(self, request, model_admin):
        return [
            ('read', 'Gelesen'),
            ('unread', 'Ungelesen'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'read':
            return queryset.filter(read=True)
        if self.value() == 'unread':
            return queryset.filter(read=False)
        return queryset


class ChatMessageDirectInline(admin.TabularInline):
    model = ChatMessageDirect
    extra = 0
    readonly_fields = ('user', 'message', 'created_at', 'read')
    can_delete = False


class ChatMessageGroupInline(admin.TabularInline):
    model = ChatMessageGroup
    extra = 0
    readonly_fields = ('user', 'message', 'created_at')
    can_delete = False


@admin.register(ChatDirect)
class ChatDirectAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'org', 'created_at', 'updated_at', 'unread_count')
    list_filter = ('org',)
    search_fields = ('users__username', 'users__first_name', 'users__last_name')
    filter_horizontal = ('users',)
    readonly_fields = ('created_at', 'updated_at', 'identifier')
    inlines = [ChatMessageDirectInline]

    def unread_count(self, obj):
        return ChatMessageDirect.objects.filter(chat=obj, read=False).count()
    unread_count.short_description = 'Ungelesen'


@admin.register(ChatGroup)
class ChatGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'org', 'created_at', 'updated_at', 'member_count')
    list_filter = ('org',)
    search_fields = ('name', 'users__username', 'users__first_name', 'users__last_name')
    filter_horizontal = ('users',)
    readonly_fields = ('created_at', 'updated_at', 'identifier')
    inlines = [ChatMessageGroupInline]

    def member_count(self, obj):
        return obj.users.count()
    member_count.short_description = 'Mitglieder'


@admin.register(ChatMessageDirect)
class ChatMessageDirectAdmin(admin.ModelAdmin):
    list_display = ('user', 'chat', 'short_message', 'read', 'created_at')
    list_filter = ('org', ReadFilter, 'created_at')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'message')
    readonly_fields = ('created_at', 'updated_at')

    def short_message(self, obj):
        return obj.message[:60] + ('…' if len(obj.message) > 60 else '')
    short_message.short_description = 'Nachricht'


@admin.register(ChatMessageGroup)
class ChatMessageGroupAdmin(admin.ModelAdmin):
    list_display = ('user', 'chat', 'short_message', 'created_at', 'read_by_count')
    list_filter = ('org', 'created_at')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'message')
    filter_horizontal = ('read_by',)
    readonly_fields = ('created_at', 'updated_at')

    def short_message(self, obj):
        return obj.message[:60] + ('…' if len(obj.message) > 60 else '')
    short_message.short_description = 'Nachricht'

    def read_by_count(self, obj):
        return obj.read_by.count()
    read_by_count.short_description = 'Gelesen von'
