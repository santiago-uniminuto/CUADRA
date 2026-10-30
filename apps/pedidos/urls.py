from django.urls import path
from . import views

app_name = 'pedidos'
urlpatterns = [
    path('manage/', views.manage_tables, name='manage_tables'),
    path('manage/create/', views.create_table, name='create_table'),
    path('manage/<int:table_id>/toggle/', views.toggle_table, name='toggle_table'),
    path('', views.tables, name='tables'),
    path('tables/<int:table_id>/open/', views.open_order, name='open_order'),
    path('tables/<int:table_id>/release/', views.release_table, name='release_table'),
    path('<int:pk>/', views.order_detail, name='order_detail'),
    path('<int:pk>/add/', views.add_product, name='add_product'),
    path('<int:pk>/items/<int:detail_id>/remove/', views.remove_product, name='remove_product'),
    path('<int:pk>/discard/', views.discard_empty, name='discard_empty'),
    path('<int:pk>/items/<int:detail_id>/edit/', views.edit_item, name='edit_item'),
    path('<int:pk>/save/', views.save_order, name='save_order'),
    path('<int:pk>/cancel/', views.cancel_order, name='cancel_order'),
]
