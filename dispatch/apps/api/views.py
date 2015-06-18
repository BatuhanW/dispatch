from django.contrib.auth import get_user_model
from django.db.models import Q

from rest_framework import viewsets, generics, mixins, filters, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import api_view, detail_route, list_route
from rest_framework.generics import get_object_or_404
from rest_framework.exceptions import APIException

from dispatch.helpers import ThemeHelper
from dispatch.apps.core.models import Person
from dispatch.apps.frontend.models import Page, Component
from dispatch.apps.content.models import Article, Section, Tag, Image, ImageAttachment
from dispatch.apps.api.serializers import (ArticleSerializer, SectionSerializer, ImageSerializer,
                                           ImageAttachmentSerializer, FullImageAttachmentSerializer,
                                           TagSerializer, PersonSerializer)

class FrontpageViewSet(viewsets.GenericViewSet, mixins.ListModelMixin):
    """
    Viewset for frontpage views.
    """
    serializer_class = ArticleSerializer
    def fetch_frontpage(self, section_id=None, section_slug=None):
        """
        Return serialized frontpage listing, optionally filtered by section.
        """
        if section_id is not None:
            # Filter queryset by section_id if set
            queryset = Article.objects.get_frontpage(section_id=int(section_id))
        elif section_slug is not None:
            # Filter queryset by section_slug if set
            queryset = Article.objects.get_frontpage(section=section_slug)
        else:
            # Don't filter the results
            queryset = Article.objects.get_frontpage()

        # Cast RawQuerySet as list for pagination to work
        return list(queryset)

    def list(self, request):
        """
        Return resource listing representing the most recent and
        relevant articles, photos, and videos for the given timestamp.

        TODO: implement timestamp parameter
        """
        # Update the queryset with frontpage listing before calling super method
        self.queryset = self.fetch_frontpage()
        return super(FrontpageViewSet, self).list(self, request)

    def section(self, request, pk=None, slug=None):
        """
        Return resource listing representing the most recent and
        relevant articles, photos, and videos in the given section
        for the given timestamp.

        TODO: implement timestamp parameter
        """
        # Update the queryset with filtered frontpage listing before calling super method
        self.queryset = self.fetch_frontpage(section_id=pk, section_slug=slug)
        return super(FrontpageViewSet, self).list(self, request)

class SectionViewSet(viewsets.ModelViewSet):
    """
    Viewset for Section model views.
    """
    serializer_class = SectionSerializer

    queryset = Section.objects.all()

    def frontpage(self, request, pk=None, slug=None):
        """
        Extra method to return frontpage listing for the section.
        Uses FrontpageViewSet.section() to perform request.
        """
        view = FrontpageViewSet.as_view({'get': 'section'})
        return view(request, pk=pk, slug=slug)

class ImageAttachmentViewSet(viewsets.GenericViewSet, mixins.ListModelMixin):
    """
    Viewset for ImageAttachment model views.
    """
    model = ImageAttachment
    serializer_class = FullImageAttachmentSerializer
    paginate_by = 50
    queryset = ImageAttachment.objects.all()

    def article(self, request, pk=None):
        """
        Extra method to return ImageAttachments for given Article.

        TODO: add error handling for when pk is None
        """
        if pk is not None:
            # Update queryset to filter by given Article id
            self.queryset = self.queryset.filter(article__id=pk)
        return super(ImageAttachmentViewSet, self).list(self, request)

class ArticleViewSet(viewsets.ModelViewSet):
    """
    Viewset for Article model views.
    """
    serializer_class = ArticleSerializer

    def get_queryset(self):
        """
        Optionally restricts the returned articles by filtering
        against a `topic` query parameter in the URL.
        """
        queryset = Article.objects.filter(head=True).order_by('-published_at')
        tag = self.request.QUERY_PARAMS.get('tag', None)
        topic = self.request.QUERY_PARAMS.get('topic', None)
        q = self.request.QUERY_PARAMS.get('q', None)
        limit = self.request.QUERY_PARAMS.get('limit', None)
        if tag is not None:
            queryset = queryset.filter(tags__name=tag)
        if topic is not None:
            queryset = queryset.filter(topics__name=topic)
        if q is not None:
            queryset = queryset.filter(long_headline__icontains=q)
        if limit is not None:
            queryset = queryset[:limit]
        return queryset

    @detail_route(methods=['get'],)
    def revision(self, request, pk=None):
        revision_id = request.QUERY_PARAMS.get('revision_id', None)
        filter_kwargs = {
            'parent_id': pk,
            'revision_id': revision_id,
        }
        queryset = Article.objects.all()
        instance = get_object_or_404(queryset, **filter_kwargs)
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @detail_route(methods=['get'],)
    def attachments(self, request, pk=None):
        """
        Returns a list of the arictle's attachments.
        Uses ImageAttachmentViewSet.article() to perform request
        """
        view = ImageAttachmentViewSet.as_view({'get': 'article'})
        return view(request, pk)

class PersonViewSet(viewsets.ModelViewSet):
    """
    Viewset for Person model views.
    """
    serializer_class = PersonSerializer

    def get_queryset(self):
        queryset = Person.objects.all()
        q = self.request.QUERY_PARAMS.get('q', None)
        if q is not None:
            # If a search term (q) is present, filter queryset by term against `full_name`
            queryset = queryset.filter(full_name__icontains=q)
        return queryset

class TagViewSet(viewsets.ModelViewSet):
    """
    Viewset for Tag model views.
    """
    serializer_class = TagSerializer

    def get_queryset(self):
        queryset = Tag.objects.all()
        q = self.request.QUERY_PARAMS.get('q', None)
        if q is not None:
            # If a search term (q) is present, filter queryset by term against `full_name`
            queryset = queryset.filter(name__icontains=q)
        return queryset

    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            resource = serializer.save()
            status_code = status.HTTP_201_CREATED
        except APIException:
            instance = Tag.objects.get(name=request.data.get('name'))
            serializer = self.get_serializer(instance)
            status_code = status.HTTP_200_OK
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status_code, headers=headers)


class ImageViewSet(viewsets.ModelViewSet):
    """
    Viewset for Image model views.
    """
    model = Image
    serializer_class = ImageSerializer
    paginate_by = 30
    filter_backends = (filters.OrderingFilter,)
    ordering_fields = ('created_at',)

    def create(self, request, *args, **kwargs):
        authors = request.POST.get('authors', None)
        if authors is None:
            # Set author to current user if no authors are passed
            authors = [request.user.id]
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        resource = serializer.save()
        resource.save_authors(authors) # Handle author saving
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):

        authors = request.data.get('authors', False)

        partial = kwargs.pop('partial', False)

        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        resource = serializer.save()

        if authors:
            resource.save_authors(authors)

        return Response(serializer.data)

    def get_queryset(self):
        queryset = Image.objects.all()
        q = self.request.QUERY_PARAMS.get('q', None)
        if q is not None:
            queryset = queryset.filter(Q(title__icontains=q) | Q(img__icontains=q) )
        return queryset

class ComponentViewSet(viewsets.GenericViewSet):

    components = ThemeHelper.get_theme_components()
    pages = ThemeHelper.get_theme_pages()

    def detail(self, request, slug=None):
        spots_list = []
        components_dict = {}
        saved_dict = {}

        page = self.pages.get(slug)

        instance = Page.objects.get(slug=slug)
        for component in instance.components.all():
            component_class = self.components.get(component.slug)
            component_obj = component_class(instance=component)
            saved_dict[component.spot] = {
                'slug': component.slug,
                'fields': component_obj.field_data_as_json(),
            }



        for spot, name in page.component_spots:
            options = []
            for component in self.components.get_for_spot(spot):
                options.append({
                    'name': component.NAME,
                    'slug': component.SLUG,
                    })
                if component.SLUG not in components_dict:
                    component_obj = component()
                    components_dict[component.SLUG] = component_obj.fields_as_json()
            spots_list.append({
                'name': name,
                'slug': spot,
                'options': options,
            })

        data = {
            'spots': spots_list,
            'components': components_dict,
            'saved': saved_dict,
        }

        return Response(data)

    def update(self, request, slug=None):

        try:
            update_status = status.HTTP_200_OK
            instance = Page.objects.get(slug=slug)
        except:
            update_status = status.HTTP_201_CREATED
            instance = Page(slug=slug)
            instance.save()

        component_slug = request.POST.get('component')
        spot = request.POST.get('spot')

        component_class = self.components.get(component_slug)

        try:
            component_instance = Component.objects.get(page=instance, spot=spot)
            if component_instance.slug == component_slug:
                component_obj = component_class(request.POST, instance=component_instance, spot=spot)
            else:
                instance.components.remove(instance)
                raise Exception()
        except:
            component_obj = component_class(request.POST, spot=spot)

        component_instance = component_obj.save()

        instance.components.add(component_instance)

        instance.save()

        data = {
            'saved': True
        }

        return Response(data, status=update_status)