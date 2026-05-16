from django.shortcuts import redirect, render


def category_list_view(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return redirect('/login/')
    return render(request, 'permissions/category_list.html')
