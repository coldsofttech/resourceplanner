from rest_framework.routers import DefaultRouter

from .api_views import (
    ForecastImportViewSet,
    ProjectFinanceTypeMappingViewSet,
    ProjectFinanceTypeViewSet,
    RechargeDetailViewSet,
    RechargeViewSet,
    SprintForecastRowViewSet,
)

router = DefaultRouter()
router.register(r'finance-types', ProjectFinanceTypeViewSet, basename='finance-type')
router.register(r'finance-type-mappings', ProjectFinanceTypeMappingViewSet, basename='finance-type-mapping')
router.register(r'sprint-forecast', ForecastImportViewSet, basename='sprint-forecast')
router.register(r'sprint-forecast-rows', SprintForecastRowViewSet, basename='sprint-forecast-row')
router.register(r'recharges', RechargeViewSet, basename='recharge')
router.register(r'recharge-details', RechargeDetailViewSet, basename='recharge-detail')

urlpatterns = router.urls
