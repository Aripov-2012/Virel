from django.contrib import admin
from django.urls import path,include

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
