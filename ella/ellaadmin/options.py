from django.contrib import admin
from django import newforms as forms

from ella.ellaadmin import widgets


def mixin_ella_admin(admin_class):
    if admin_class == admin.ModelAdmin:
        return ExtendedModelAdmin

    if EllaAdminOptionsMixin in admin_class.__bases__:
        # TODO: recursive traversal to parents...
        return admin_class

    bases = list(admin_class.__bases__)
    admin_class.__bases__ = tuple([EllaAdminOptionsMixin] + bases)
    return admin_class

def register_ella_admin(func):
    def _register(self, model_or_iterable, admin_class=None, **options):
        admin_class = admin_class or admin.ModelAdmin
        admin_class = mixin_ella_admin(admin_class)
        for inline in admin_class.inlines:
            inline = mixin_ella_admin(inline)
        return func(self, model_or_iterable, admin_class, **options)
    return _register


class EllaAdminSite(admin.AdminSite):
    def __init__(self):
        self._registry = admin.site._registry
        for options in self._registry.values():
            options.__class__ = mixin_ella_admin(options.__class__)
            for inline in options.inlines:
                inline = mixin_ella_admin(inline)
        admin.AdminSite.register = register_ella_admin(admin.AdminSite.register)

class ContentTypeChoice(forms.ChoiceField):
    def __init__(self, choices=(), required=True, widget=None, label=None, initial=None, help_text=None, *args, **kwargs):
        super(ContentTypeChoice, self).__init__(choices, required, widget, label, initial, help_text, *args, **kwargs)
        print initial

    def clean(self, value):
        from django.contrib.contenttypes.models import ContentType
        value = super(ContentTypeChoice, self).clean(value)
        return ContentType.objects.get(pk=value)


class EllaAdminOptionsMixin(object):
    def formfield_for_dbfield(self, db_field, **kwargs):
        from ella.core.middleware import get_current_request
        from ella.ellaadmin.filterspecs import get_content_types
        if db_field.name == 'slug':
            return forms.RegexField('^[0-9a-z-]+$', max_length=255, **kwargs)

        elif db_field.name in ('target_ct', 'source_ct'):
            kwargs['widget'] = widgets.ContentTypeWidget
            return ContentTypeChoice(choices=[(u'', u"---------")] + [ (c.id, c) for c in get_content_types(get_current_request().user) ], **kwargs)

        elif db_field.name in ('target_id', 'source_id',):
            kwargs['widget'] = widgets.ForeignKeyRawIdWidget

        return super(EllaAdminOptionsMixin, self).formfield_for_dbfield(db_field, **kwargs)


    def queryset(self, request):
        from ella.ellaadmin import models
        from django.db.models import Q, query
        from django.db.models.fields import FieldDoesNotExist
        q = admin.ModelAdmin.queryset(self, request)

        if request.user.is_superuser:
            return q

        view_perm = self.opts.app_label + '.' + 'view_' + self.model._meta.module_name.lower()
        change_perm = self.opts.app_label + '.' + 'change_' + self.model._meta.module_name.lower()
        sites = None

        try:
            self.model._meta.get_field('site')
            sites = models.applicable_sites(request.user, view_perm) + models.applicable_sites(request.user, change_perm)
            q = q.filter(site__in=sites)
        except FieldDoesNotExist:
            pass

        try:
            self.model._meta.get_field('category')
            if sites is None:
                sites = models.applicable_sites(request.user, view_perm) + models.applicable_sites(request.user, change_perm)
            categories = models.applicable_categories(request.user, view_perm) + models.applicable_categories(request.user, change_perm)

            if sites or categories:
                # TODO: terrible hack for circumventing invalid Q(__in=[]) | Q(__in=[])
                q = q.filter(Q(category__site__in=sites) | Q(category__in=categories))
            else:
                q = query.EmptyQuerySet()
        except FieldDoesNotExist:
            pass

        return q

    def has_change_permission(self, request, obj):
        """
        Returns True if the given request has permission to change the given
        Django model instance.

        If `obj` is None, this should return True if the given request has
        permission to change *any* object of the given type.
        """
        from ella.ellaadmin import models
        if obj is None or not hasattr(obj, 'category'):
            return admin.ModelAdmin.has_change_permission(self, request, obj)
        opts = self.opts
        return models.has_permission(request.user, obj, obj.category, opts.get_change_permission())

class ExtendedModelAdmin(EllaAdminOptionsMixin, admin.ModelAdmin):
    pass


