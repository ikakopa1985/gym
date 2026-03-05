from django.contrib import admin
from .models import *

# Register your models here.

admin.site.register(Client)
admin.site.register(Membership)
admin.site.register(ClientMembership)
admin.site.register(Payment)
admin.site.register(CheckIn)
