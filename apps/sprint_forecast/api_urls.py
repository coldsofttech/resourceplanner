from rest_framework.routers import DefaultRouter

from .api_views import (
    ProjectFinanceTypeMappingViewSet,
    ProjectFinanceTypeViewSet,
    RechargeDetailViewSet,
    RechargeViewSet,
    SprintActualsViewSet,
    SprintCompareViewSet,
    SprintConfirmedRowViewSet,
    SprintForecastViewSet,
)

router = DefaultRouter()
router.register(r'finance-types', ProjectFinanceTypeViewSet, basename='finance-type')
router.register(r'finance-type-mappings', ProjectFinanceTypeMappingViewSet, basename='finance-type-mapping')
router.register(r'sprint-forecast', SprintForecastViewSet, basename='sprint-forecast')
router.register(r'sprint-actuals', SprintActualsViewSet, basename='sprint-actuals')
router.register(r'sprint-confirmed-rows', SprintConfirmedRowViewSet, basename='sprint-confirmed-row')
router.register(r'recharges', RechargeViewSet, basename='recharge')
router.register(r'recharge-details', RechargeDetailViewSet, basename='recharge-detail')
router.register(r'sprint-compare', SprintCompareViewSet, basename='sprint-compare')

urlpatterns = router.urls
