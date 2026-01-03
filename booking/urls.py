from django.urls import path
from . import views

urlpatterns = [
    path('', views.movie_list, name='movie_list'),
    path('movie/<int:id>/', views.movie_detail, name='movie_detail'),
    path('reserve-seat/<int:seat_id>/', views.reserve_seat, name='reserve_seat'),
    path('pay/<int:movie_id>/', views.create_checkout_session, name='pay'),
    path('payment-success/', views.payment_success, name='payment_success'),
    path('payment-cancel/', views.payment_cancel, name='payment_cancel'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),

]
