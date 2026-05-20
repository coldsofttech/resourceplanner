from django.views.generic import View
from django.shortcuts import render


class RoadmapListView(View):
    def get(self, request):
        return render(request, 'roadmaps/roadmap_list.html')


class RoadmapDetailView(View):
    def get(self, request, pk):
        return render(request, 'roadmaps/roadmap_detail.html', {'roadmap_pk': pk})
