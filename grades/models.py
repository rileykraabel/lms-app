from django.db import models
from django.contrib.auth.models import User, Group
from django.core.validators import MaxValueValidator, MinValueValidator
from django.utils import timezone

# Create your models here.
class Assignment(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    deadline = models.DateTimeField()
    weight = models.IntegerField()
    points = models.IntegerField()

    def is_due(self):
        return self.deadline < timezone.now()

class Submission(models.Model):
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    grader = models.ForeignKey(User, related_name='graded_set', on_delete=models.SET_NULL, null=True, blank=True)
    file = models.FileField()
    score = models.FloatField(null=True, blank=True, validators=[
            MaxValueValidator(100),
            MinValueValidator(0)
        ])

    @property
    def is_graded(self):
        return self.score is not None

    @property
    def is_past_due(self):
        return self.assignment.is_due()