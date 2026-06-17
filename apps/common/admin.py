# -*- coding: utf-8 -*-
from django.contrib import admin

from apps.common.models import Feedback


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("created_at", "category", "status", "rating", "created_by", "page", "short_message")
    list_filter = ("category", "status", "created_at")
    search_fields = ("message", "page", "created_by__username")
    list_editable = ("status",)
    readonly_fields = ("created_at", "updated_at", "created_by", "page", "category", "rating", "message")
    ordering = ("-id",)

    @admin.display(description="Message")
    def short_message(self, obj):
        return (obj.message or "")[:80]
