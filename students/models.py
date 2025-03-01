from django.urls import reverse
from django.db import models
from django.conf import settings

import datetime, os

# Create your models here.

# class StudentDetails(models.Model):
#     user = models.ForeignKey(settings.AUTH_USER_MODEL,related_name='attandence', on_delete=models.CASCADE)
#     login_date = models.DateField(auto_now_add=True)
#     login_time = models.TimeField(auto_now_add=True)
