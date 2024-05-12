from django.contrib import admin
from .models import Assignment, Submission

# Register your models here.
@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ['title', 'description', 'deadline', 'weight', 'points']

@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ['assignment', 'author', 'grader', 'file', 'score']

