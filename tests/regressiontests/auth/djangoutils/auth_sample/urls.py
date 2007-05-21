from django.conf.urls.defaults import *

from views import *

urlpatterns = patterns('',
     (r'^login/$', login),
     (r'^nologin/$', no_login),
     (r'^logged/$', logged_only),
     (r'^post/$', post_data),
)
