from django.urls import path
from . import views

app_name = 'pagos'
urlpatterns = [
    path('', views.checkout_queue, name='queue'),
    path('<int:pk>/', views.checkout_detail, name='checkout_detail'),
    path('<int:pk>/receipt/', views.payment_receipt, name='receipt'),
    path('<int:pk>/pay/', views.register_payment, name='register_payment'),
]
