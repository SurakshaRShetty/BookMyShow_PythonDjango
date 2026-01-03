from django.contrib import admin
from .models import Movie, Seat, Booking


admin.site.register(Movie)
admin.site.register(Seat)
admin.site.register(Booking)
