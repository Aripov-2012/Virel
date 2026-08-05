from django.contrib import admin
from django.urls import path,include
from django.conf.urls.static import static
from django.views.static import serve
from django.urls import re_path

# urlpatterns = [

# ]


from django.conf import settings
from django.conf.urls.static import static
from blog.views import LoginWithStats

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/profile/login/', LoginWithStats.as_view(), name='login'),
    path('accounts/profile/', include('django.contrib.auth.urls')),
    path('', include('blog.urls')),
    path('accounts/', include('allauth.urls')),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]